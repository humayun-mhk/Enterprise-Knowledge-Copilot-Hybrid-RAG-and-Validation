from __future__ import annotations

import re
from typing import Any, Sequence, TypedDict

from ..config import Settings
from ..domain import RetrievalHit
from ..schemas import Citation, ValidationResult, ValidationStatus, model_dump_compat
from .bm25 import tokenize
from .citations import strip_generated_citations
from .generation import REFUSAL_TEXT, split_sentences
from .reranker import lexical_relevance


class ValidationState(TypedDict, total=False):
    question: str
    answer: str
    hits: list[RetrievalHit]
    citations: list[dict[str, Any]]
    claims: list[str]
    claim_checks: list[dict[str, Any]]
    supported_claims: int
    unsupported_claims: int
    citation_coverage: float
    citation_precision: float
    unsupported_details: list[str]
    contradictory_claims: list[str]
    status: str
    corrected_answer: str | None
    reason: str


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", text))


def _has_negation(text: str) -> bool:
    return bool(re.search(r"\b(?:no|not|never|cannot|can't|prohibited|forbidden)\b", text.casefold()))


def _meaningful_tokens(text: str) -> set[str]:
    return set(tokenize(text, remove_stopwords=True))


def _citation_dict(citation: Citation | dict[str, Any]) -> dict[str, Any]:
    if isinstance(citation, Citation):
        return model_dump_compat(citation)
    return dict(citation)


class _FallbackGraph:
    def __init__(self, owner: "AnswerValidationAgent") -> None:
        self.owner = owner

    def invoke(self, state: ValidationState) -> ValidationState:
        state = self.owner._extract_claims(state)
        state = self.owner._verify_claims(state)
        state = self.owner._decide(state)
        if state["status"] == ValidationStatus.REVISE.value:
            state = self.owner._rewrite(state)
        return state


class AnswerValidationAgent:
    """Claim and citation validator implemented as a LangGraph workflow.

    The checks are deterministic by default, making validator decisions
    reproducible and testable. LangGraph provides the state transitions; a tiny
    compatible executor is used only when the optional dependency is absent.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.graph = self._build_graph()
        self.graph_backend = "langgraph" if self.graph.__class__.__name__ != "_FallbackGraph" else "fallback"

    def _build_graph(self) -> Any:
        try:
            from langgraph.graph import END, START, StateGraph

            workflow = StateGraph(ValidationState)
            workflow.add_node("extract_claims", self._extract_claims)
            workflow.add_node("verify_claims", self._verify_claims)
            workflow.add_node("decide", self._decide)
            workflow.add_node("rewrite", self._rewrite)
            workflow.add_edge(START, "extract_claims")
            workflow.add_edge("extract_claims", "verify_claims")
            workflow.add_edge("verify_claims", "decide")
            workflow.add_conditional_edges(
                "decide",
                lambda state: "rewrite" if state["status"] == ValidationStatus.REVISE.value else "finish",
                {"rewrite": "rewrite", "finish": END},
            )
            workflow.add_edge("rewrite", END)
            return workflow.compile()
        except ImportError:
            return _FallbackGraph(self)

    def _extract_claims(self, state: ValidationState) -> ValidationState:
        clean_answer = strip_generated_citations(state.get("answer", ""))
        if clean_answer.casefold() == REFUSAL_TEXT.casefold():
            claims: list[str] = []
        else:
            claims = [
                sentence
                for sentence in split_sentences(clean_answer) or ([clean_answer] if clean_answer else [])
                if len(_meaningful_tokens(sentence)) >= 2
            ]
        return {**state, "claims": claims}

    @staticmethod
    def _valid_citations(
        citations: Sequence[dict[str, Any]], hits: Sequence[RetrievalHit]
    ) -> tuple[dict[str, RetrievalHit], int]:
        by_id = {hit.chunk.chunk_id: hit for hit in hits}
        valid: dict[str, RetrievalHit] = {}
        valid_count = 0
        for citation in citations:
            hit = by_id.get(str(citation.get("chunk_id", "")))
            if hit is None:
                continue
            page_matches = citation.get("page") == hit.chunk.page_number
            document_matches = citation.get("document") == hit.chunk.document_name
            quote = str(citation.get("quoted_evidence", "")).strip()
            quote_tokens = _meaningful_tokens(quote)
            passage_tokens = _meaningful_tokens(hit.chunk.chunk_text)
            quote_matches = bool(quote) and (
                quote.casefold() in hit.chunk.chunk_text.casefold()
                or (quote_tokens and len(quote_tokens & passage_tokens) / len(quote_tokens) >= 0.9)
            )
            if page_matches and document_matches and quote_matches:
                valid[hit.chunk.chunk_id] = hit
                valid_count += 1
        return valid, valid_count

    def _verify_claims(self, state: ValidationState) -> ValidationState:
        claims = state.get("claims", [])
        hits = state.get("hits", [])
        citations = state.get("citations", [])
        valid_citations, valid_citation_count = self._valid_citations(citations, hits)
        checks: list[dict[str, Any]] = []
        unsupported_details: list[str] = []
        contradictions: list[str] = []
        cited_claims = 0

        for claim in claims:
            ranked = sorted(
                ((lexical_relevance(claim, hit.chunk.chunk_text), hit) for hit in hits),
                key=lambda item: (-item[0], item[1].rank),
            )
            best_score, best_hit = ranked[0] if ranked else (0.0, None)
            claim_numbers = _numbers(claim)
            evidence_numbers = _numbers(best_hit.chunk.chunk_text) if best_hit else set()
            numbers_supported = claim_numbers.issubset(evidence_numbers)
            claim_tokens = _meaningful_tokens(claim)
            evidence_tokens = _meaningful_tokens(best_hit.chunk.chunk_text) if best_hit else set()
            token_coverage = len(claim_tokens & evidence_tokens) / len(claim_tokens) if claim_tokens else 0.0
            supported = bool(
                best_hit
                and best_score >= self.settings.validation_support_threshold
                and token_coverage >= 0.4
                and numbers_supported
            )
            contradictory = False
            if best_hit and token_coverage >= 0.5:
                if claim_numbers and evidence_numbers and claim_numbers.isdisjoint(evidence_numbers):
                    contradictory = True
                elif _has_negation(claim) != _has_negation(best_hit.chunk.chunk_text) and best_score >= 0.65:
                    contradictory = True
            cited = bool(
                best_hit
                and best_hit.chunk.chunk_id in valid_citations
                and lexical_relevance(claim, best_hit.chunk.chunk_text) >= self.settings.validation_support_threshold
            )
            if cited:
                cited_claims += 1
            check = {
                "claim": claim,
                "supported": supported and not contradictory,
                "contradictory": contradictory,
                "score": round(best_score, 6),
                "token_coverage": round(token_coverage, 6),
                "chunk_id": best_hit.chunk.chunk_id if best_hit else None,
                "cited": cited,
            }
            checks.append(check)
            if not check["supported"]:
                unsupported_details.append(claim)
            if contradictory:
                contradictions.append(claim)

        supported_count = sum(1 for item in checks if item["supported"])
        total_claims = len(claims)
        citation_coverage = cited_claims / total_claims if total_claims else 0.0
        citation_precision = valid_citation_count / len(citations) if citations else 0.0
        return {
            **state,
            "claim_checks": checks,
            "supported_claims": supported_count,
            "unsupported_claims": total_claims - supported_count,
            "citation_coverage": round(citation_coverage, 6),
            "citation_precision": round(citation_precision, 6),
            "unsupported_details": unsupported_details,
            "contradictory_claims": contradictions,
        }

    def _decide(self, state: ValidationState) -> ValidationState:
        claims = state.get("claims", [])
        supported = int(state.get("supported_claims", 0))
        unsupported = int(state.get("unsupported_claims", 0))
        coverage = float(state.get("citation_coverage", 0.0))
        contradictions = state.get("contradictory_claims", [])
        answer = strip_generated_citations(state.get("answer", ""))

        if not claims or answer.casefold() == REFUSAL_TEXT.casefold():
            status = ValidationStatus.INSUFFICIENT_EVIDENCE
            reason = "The retrieved passages did not provide enough evidence for an answer."
            corrected = REFUSAL_TEXT
        elif supported == 0 or supported / len(claims) < 0.5:
            status = ValidationStatus.INSUFFICIENT_EVIDENCE
            reason = "Most factual claims could not be supported by the retrieved passages."
            corrected = REFUSAL_TEXT
        elif unsupported or contradictions or coverage < self.settings.validation_min_coverage:
            status = ValidationStatus.REVISE
            if contradictions:
                reason = "One or more claims contradicted the retrieved passages and were removed."
            elif unsupported:
                reason = "One or more claims were not supported by the retrieved passages and were removed."
            else:
                reason = "The answer was supported but citation coverage was incomplete."
            corrected = None
        else:
            status = ValidationStatus.APPROVED
            reason = "All factual claims and citations were supported by the retrieved passages."
            corrected = None
        return {
            **state,
            "status": status.value,
            "reason": reason,
            "corrected_answer": corrected,
        }

    def _rewrite(self, state: ValidationState) -> ValidationState:
        supported_claims = [
            item["claim"] for item in state.get("claim_checks", []) if item.get("supported")
        ]
        corrected = " ".join(supported_claims).strip()
        if not corrected:
            return {
                **state,
                "status": ValidationStatus.INSUFFICIENT_EVIDENCE.value,
                "corrected_answer": REFUSAL_TEXT,
                "reason": "No supported claims remained after validation.",
            }
        return {**state, "corrected_answer": corrected}

    def validate(
        self,
        *,
        question: str,
        answer: str,
        hits: Sequence[RetrievalHit],
        citations: Sequence[Citation | dict[str, Any]],
    ) -> ValidationResult:
        result: ValidationState = self.graph.invoke(
            {
                "question": question,
                "answer": answer,
                "hits": list(hits),
                "citations": [_citation_dict(citation) for citation in citations],
            }
        )
        return ValidationResult(
            status=ValidationStatus(result["status"]),
            supported_claims=int(result.get("supported_claims", 0)),
            unsupported_claims=int(result.get("unsupported_claims", 0)),
            citation_coverage=float(result.get("citation_coverage", 0.0)),
            citation_precision=float(result.get("citation_precision", 0.0)),
            corrected_answer=result.get("corrected_answer"),
            reason=result.get("reason", "Validation completed."),
            unsupported_details=list(result.get("unsupported_details", [])),
            contradictory_claims=list(result.get("contradictory_claims", [])),
        )

