"""Deterministic retrieval, generation, refusal, and citation metrics.

The formulas in this module are deliberately transparent.  They do not present a
lexical heuristic as a human or LLM judgment.  Optional model-based judging lives
in :mod:`evaluation.judges` and is reported in separate fields.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

from .schemas import BenchmarkItem, QueryResult, RetrievedPassage


TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?%?", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![a-z])(?:usd\s*)?\d+(?:[.,]\d+)?%?", re.IGNORECASE)
CITATION_RE = re.compile(r"\[[^\]]+?(?:page|p\.?)[^\]]+?\]", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
REFUSAL_PATTERNS = (
    "insufficient evidence",
    "not enough evidence",
    "do not have enough evidence",
    "don't have enough evidence",
    "not enough information",
    "do not have enough information",
    "don't have enough information",
    "cannot answer from",
    "can't answer from",
    "unable to answer from",
    "documents do not contain",
    "documents don't contain",
    "not supported by the provided",
    "cannot find this information",
)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to", "up", "when",
    "which", "with", "within", "must", "may", "after", "each", "every", "than", "into", "its",
}


def tokens(value: str, *, content_only: bool = False) -> list[str]:
    output = [token.casefold() for token in TOKEN_RE.findall(value or "")]
    return [token for token in output if token not in STOPWORDS] if content_only else output


def normalized_text(value: str) -> str:
    return " ".join(tokens(value))


def token_f1(expected: str, actual: str) -> float:
    expected_tokens, actual_tokens = tokens(expected), tokens(actual)
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0
    overlap = sum((Counter(expected_tokens) & Counter(actual_tokens)).values())
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def exact_match(expected: str, actual: str) -> float:
    return float(normalized_text(expected) == normalized_text(actual))


def keyword_coverage(keywords: Sequence[str], answer: str) -> float | None:
    if not keywords:
        return None
    answer_normalized = normalized_text(answer)
    found = sum(normalized_text(keyword) in answer_normalized for keyword in keywords)
    return found / len(keywords)


def is_refusal(answer: str) -> bool:
    normalized = " ".join((answer or "").casefold().split())
    return any(pattern in normalized for pattern in REFUSAL_PATTERNS)


def _passage_target(passage: RetrievedPassage) -> tuple[str, int | None]:
    return passage.document.casefold(), passage.page


def _matches_target(passage: RetrievedPassage, target: tuple[str, int | None]) -> bool:
    document, page = target
    return passage.document.casefold() == document and (page is None or passage.page == page)


def retrieval_metrics(
    item: BenchmarkItem,
    passages: Sequence[RetrievedPassage],
    ks: Sequence[int] = (3, 5, 10),
) -> dict[str, float | None]:
    """Compute target-deduplicated binary retrieval metrics.

    A relevant target is a ground-truth (document, page) pair.  The first chunk
    retrieved from that target receives relevance 1 and duplicate chunks from the
    same page receive relevance 0.  This prevents small chunks from inflating
    recall or nDCG.
    """
    targets = item.relevant_targets
    output: dict[str, float | None] = {}
    if not targets:
        for k in ks:
            output[f"recall_at_{k}"] = None
            output[f"precision_at_{k}"] = None
            output[f"ndcg_at_{k}"] = None
        output["mrr"] = None
        return output

    relevance: list[int] = []
    seen_targets: set[tuple[str, int | None]] = set()
    for passage in passages:
        matched = next((target for target in targets if target not in seen_targets and _matches_target(passage, target)), None)
        if matched is None:
            relevance.append(0)
        else:
            relevance.append(1)
            seen_targets.add(matched)

    first_rank = next((rank for rank, relevant in enumerate(relevance, start=1) if relevant), None)
    output["mrr"] = 1.0 / first_rank if first_rank is not None else 0.0
    ideal_relevant = len(targets)
    for k in ks:
        rel_k = relevance[:k]
        hits = sum(rel_k)
        output[f"recall_at_{k}"] = hits / ideal_relevant
        output[f"precision_at_{k}"] = hits / k
        dcg = sum(rel / math.log2(rank + 1) for rank, rel in enumerate(rel_k, start=1))
        ideal_count = min(ideal_relevant, k)
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
        output[f"ndcg_at_{k}"] = dcg / idcg if idcg else None
    return output


def split_claims(answer: str) -> list[str]:
    without_citations = CITATION_RE.sub("", answer or "")
    claims = []
    for sentence in SENTENCE_RE.split(without_citations):
        sentence = sentence.strip(" -\t")
        if len(tokens(sentence, content_only=True)) >= 3 and not is_refusal(sentence):
            claims.append(sentence)
    return claims


def _normalized_numbers(value: str) -> set[str]:
    return {match.casefold().replace("usd", "").replace(",", "").strip() for match in NUMBER_RE.findall(value or "")}


def claim_support_score(claim: str, evidence: str) -> float:
    claim_tokens = set(tokens(claim, content_only=True))
    evidence_tokens = set(tokens(evidence, content_only=True))
    if not claim_tokens:
        return 1.0
    coverage = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    claim_numbers = _normalized_numbers(claim)
    evidence_numbers = _normalized_numbers(evidence)
    if claim_numbers and not claim_numbers.issubset(evidence_numbers):
        return 0.0
    return coverage


def claim_support(claim: str, passages: Sequence[RetrievedPassage], threshold: float = 0.55) -> tuple[bool, float]:
    scores = [claim_support_score(claim, passage.text) for passage in passages]
    best = max(scores, default=0.0)
    return best >= threshold, best


def citation_metrics(
    item: BenchmarkItem,
    result: QueryResult,
    claim_count: int,
) -> dict[str, float | None]:
    citations = result.citations
    targets = item.relevant_targets
    if not item.answerable:
        return {
            "citation_coverage": None,
            "citation_precision": None,
            "citation_recall": None,
            "citation_misuse": float(bool(citations)),
        }
    if not result.retrieved_passages:
        precision: float | None = None
    elif not citations:
        precision = 0.0
    else:
        valid = 0
        for citation in citations:
            matching_passages = [
                passage for passage in result.retrieved_passages
                if passage.document.casefold() == citation.document.casefold()
                and (citation.page is None or passage.page == citation.page)
                and (not citation.chunk_id or not passage.chunk_id or passage.chunk_id == citation.chunk_id)
            ]
            quote_valid = bool(citation.quoted_evidence) and any(
                normalized_text(citation.quoted_evidence) in normalized_text(passage.text)
                or token_f1(citation.quoted_evidence, passage.text) >= 0.72
                for passage in matching_passages
            )
            if matching_passages and quote_valid:
                valid += 1
        precision = valid / len(citations)

    cited_targets: set[tuple[str, int | None]] = set()
    for citation in citations:
        for target in targets:
            if citation.document.casefold() == target[0] and (target[1] is None or citation.page == target[1]):
                cited_targets.add(target)
    citation_recall = len(cited_targets) / len(targets) if targets else None
    coverage = min(len(citations) / claim_count, 1.0) if claim_count else (1.0 if citations else None)
    return {"citation_coverage": coverage, "citation_precision": precision, "citation_recall": citation_recall, "citation_misuse": 0.0}


def evaluate_item(item: BenchmarkItem, result: QueryResult) -> dict[str, Any]:
    retrieval = retrieval_metrics(item, result.retrieved_passages)
    # Citation markers are presentation/provenance, not answer content. Score
    # the same factual text equally in C and D while retaining the original
    # answer for citation precision/recall checks below.
    answer_content = CITATION_RE.sub("", result.answer or "").strip()
    refused = is_refusal(answer_content)
    lexical_f1 = token_f1(item.expected_answer, answer_content)
    keywords = keyword_coverage(item.expected_keywords, answer_content)
    deterministic_correctness = (
        float(refused) if not item.answerable else 0.5 * lexical_f1 + 0.5 * (keywords if keywords is not None else lexical_f1)
    )
    claims = split_claims(answer_content)
    support_results = [claim_support(claim, result.retrieved_passages) for claim in claims]
    supported = sum(1 for status, _ in support_results if status)
    faithfulness = supported / len(claims) if claims and result.retrieved_passages else None
    unsupported_rate = 1.0 - faithfulness if faithfulness is not None else None
    if not item.answerable:
        hallucination: float | None = float(not refused)
    elif refused:
        hallucination = 0.0
    elif unsupported_rate is None:
        hallucination = None
    else:
        hallucination = float(unsupported_rate > 0.0)
    refusal_correct = float(refused == (not item.answerable))

    retrieved_count = len(result.retrieved_passages[:10])
    precision_at_10 = retrieval.get("precision_at_10")
    contextual_precision = None
    if item.answerable and precision_at_10 is not None and retrieved_count:
        # precision@10 uses a fixed denominator; contextual precision uses returned contexts.
        target_hits = precision_at_10 * 10
        contextual_precision = min(target_hits / retrieved_count, 1.0)
    citation = citation_metrics(item, result, len(claims))
    total_tokens = result.total_tokens
    if total_tokens is None and result.prompt_tokens is not None and result.completion_tokens is not None:
        total_tokens = result.prompt_tokens + result.completion_tokens
    base_retrieval_latency = result.retrieval_latency_ms
    reranking_latency = result.reranking_latency_ms or 0.0
    pipeline_retrieval_latency = (
        base_retrieval_latency + reranking_latency
        if base_retrieval_latency is not None
        else None
    )
    return {
        **retrieval,
        "exact_match": exact_match(item.expected_answer, answer_content),
        "answer_token_f1": lexical_f1,
        "expected_keyword_coverage": keywords,
        "answer_correctness": deterministic_correctness,
        "answer_relevance": lexical_f1 if item.answerable else refusal_correct,
        "faithfulness": faithfulness,
        "unsupported_claim_rate": unsupported_rate,
        "hallucination": hallucination,
        "refused": float(refused),
        "refusal_correct": refusal_correct,
        "contextual_precision": contextual_precision,
        "contextual_recall": retrieval.get("recall_at_10"),
        **citation,
        "claim_count": len(claims),
        "supported_claim_count": supported,
        "retrieval_latency_ms": pipeline_retrieval_latency,
        "base_retrieval_latency_ms": base_retrieval_latency,
        "reranking_latency_ms": result.reranking_latency_ms,
        "generation_latency_ms": result.generation_latency_ms,
        "validation_latency_ms": result.validation_latency_ms,
        "total_latency_ms": result.total_latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": result.estimated_cost_usd,
        "validation_status": result.validation_status,
        "error": result.error,
    }


def mean_non_null(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return statistics.fmean(present) if present else None


def percentile(values: Iterable[float | int | None], quantile: float) -> float | None:
    present = sorted(float(value) for value in values if value is not None)
    if not present:
        return None
    if len(present) == 1:
        return present[0]
    position = (len(present) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return present[lower]
    return present[lower] + (present[upper] - present[lower]) * (position - lower)


AVERAGE_FIELDS = (
    "recall_at_3", "recall_at_5", "recall_at_10", "precision_at_3", "precision_at_5", "precision_at_10",
    "mrr", "ndcg_at_3", "ndcg_at_5", "ndcg_at_10", "exact_match", "answer_token_f1",
    "expected_keyword_coverage", "answer_correctness", "answer_relevance", "faithfulness",
    "contextual_precision", "contextual_recall", "hallucination", "refusal_correct", "citation_coverage",
    "citation_precision", "citation_recall", "citation_misuse", "unsupported_claim_rate", "retrieval_latency_ms",
    "base_retrieval_latency_ms", "reranking_latency_ms",
    "generation_latency_ms", "validation_latency_ms", "total_latency_ms",
    "llm_correctness", "llm_faithfulness", "llm_relevance",
)


def aggregate_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {field: mean_non_null(row.get(field) for row in rows) for field in AVERAGE_FIELDS}
    summary.update({
        "queries": len(rows),
        "errors": sum(bool(row.get("error")) for row in rows),
        "p50_total_latency_ms": percentile((row.get("total_latency_ms") for row in rows), 0.50),
        "p95_total_latency_ms": percentile((row.get("total_latency_ms") for row in rows), 0.95),
        "total_tokens": sum(int(row["total_tokens"]) for row in rows if row.get("total_tokens") is not None) or None,
        "estimated_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows if row.get("estimated_cost_usd") is not None) if any(row.get("estimated_cost_usd") is not None for row in rows) else None,
    })
    status_counts: dict[str, int] = {}
    for row in rows:
        status = row.get("validation_status")
        if status:
            status_counts[str(status).upper()] = status_counts.get(str(status).upper(), 0) + 1
    summary["validation_status_counts"] = status_counts
    return summary
