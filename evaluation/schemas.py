"""Stable, backend-agnostic schemas used by the evaluation runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        stripped = value.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, (str, int, float, bool)) or parsed is None:
                return [] if parsed is None else [parsed]
        except json.JSONDecodeError:
            pass
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return list(value)
    return [value]


@dataclass(frozen=True)
class BenchmarkItem:
    item_id: str
    category: str
    question: str
    expected_answer: str
    expected_documents: tuple[str, ...]
    expected_pages: tuple[int, ...]
    answerable: bool
    expected_keywords: tuple[str, ...]
    expected_fact_ids: tuple[str, ...] = ()
    source_passages: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BenchmarkItem":
        documents = tuple(str(item) for item in _as_list(value.get("expected_document")))
        pages = tuple(int(item) for item in _as_list(value.get("expected_page")) if str(item).strip())
        source = tuple(str(item) for item in _as_list(value.get("source_passage")))
        answerable = value.get("answerable", False)
        if isinstance(answerable, str):
            answerable = answerable.strip().lower() in {"1", "true", "yes"}
        return cls(
            item_id=str(_first(value, "id", "item_id")),
            category=str(value.get("category", "unspecified")),
            question=str(value.get("question", "")),
            expected_answer=str(value.get("expected_answer", "")),
            expected_documents=documents,
            expected_pages=pages,
            answerable=bool(answerable),
            expected_keywords=tuple(str(item) for item in _as_list(value.get("expected_keywords"))),
            expected_fact_ids=tuple(str(item) for item in _as_list(value.get("expected_fact_ids"))),
            source_passages=source,
        )

    @property
    def relevant_targets(self) -> set[tuple[str, int | None]]:
        if not self.expected_documents:
            return set()
        if len(self.expected_pages) == len(self.expected_documents):
            return {(document.casefold(), page) for document, page in zip(self.expected_documents, self.expected_pages)}
        page = self.expected_pages[0] if len(self.expected_pages) == 1 else None
        return {(document.casefold(), page) for document in self.expected_documents}


@dataclass(frozen=True)
class RetrievedPassage:
    chunk_id: str
    document: str
    page: int | None
    text: str
    score: float | None = None
    rank: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], rank: int | None = None) -> "RetrievedPassage":
        metadata = value.get("metadata") if isinstance(value.get("metadata"), Mapping) else {}
        document = _first(value, "document", "document_name", "source", "file_name")
        if not document:
            document = _first(metadata, "document", "document_name", "source", "file_name", default="")
        page = _first(value, "page", "page_number")
        if page is None:
            page = _first(metadata, "page", "page_number")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        score = _first(value, "score", "relevance_score", "rerank_score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return cls(
            chunk_id=str(_first(value, "chunk_id", "id", default="")),
            document=str(document),
            page=page,
            text=str(_first(value, "text", "chunk_text", "content", "passage", "quoted_evidence", default="")),
            score=score,
            rank=rank,
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class Citation:
    document: str
    page: int | None
    chunk_id: str
    quoted_evidence: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Citation":
        page = _first(value, "page", "page_number")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        return cls(
            document=str(_first(value, "document", "document_name", "source", default="")),
            page=page,
            chunk_id=str(_first(value, "chunk_id", "id", default="")),
            quoted_evidence=str(_first(value, "quoted_evidence", "quote", "evidence", "text", default="")),
        )


@dataclass
class QueryResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    retrieved_passages: list[RetrievedPassage] = field(default_factory=list)
    validation_status: str | None = None
    validation: Mapping[str, Any] = field(default_factory=dict)
    retrieval_latency_ms: float | None = None
    reranking_latency_ms: float | None = None
    generation_latency_ms: float | None = None
    validation_latency_ms: float | None = None
    total_latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryResult":
        retrieval = _first(value, "retrieved_passages", "retrieved_evidence", "evidence", "contexts", default=[])
        if isinstance(retrieval, Mapping):
            retrieval = _first(retrieval, "items", "passages", "results", default=[])
        citations = value.get("citations", [])
        validation = value.get("validation") if isinstance(value.get("validation"), Mapping) else {}
        latency_value = _first(value, "latency", "timings", default={})
        latency = latency_value if isinstance(latency_value, Mapping) else {}
        usage = _first(value, "usage", "token_usage", default={})
        usage = usage if isinstance(usage, Mapping) else {}
        cost = _first(value, "estimated_cost_usd", "cost_usd")
        if cost is None:
            cost = _first(usage, "estimated_cost_usd", "cost_usd")
        provenance_value = value.get("provenance")
        provenance = dict(provenance_value) if isinstance(provenance_value, Mapping) else {}
        for key in (
            "experiment",
            "route",
            "model_provider",
            "model_name",
            "prompt_version",
            "retrieval_config_version",
            "component_backends",
        ):
            if key in value and value[key] is not None:
                provenance[key] = value[key]

        def number(candidate: Any) -> float | None:
            try:
                return float(candidate) if candidate is not None else None
            except (TypeError, ValueError):
                return None

        def integer(candidate: Any) -> int | None:
            try:
                return int(candidate) if candidate is not None else None
            except (TypeError, ValueError):
                return None

        retrieved = [
            RetrievedPassage.from_mapping(item, rank=index)
            for index, item in enumerate(retrieval or [], start=1)
            if isinstance(item, Mapping)
        ]
        return cls(
            answer=str(_first(value, "answer", "response", "output", default="")),
            citations=[Citation.from_mapping(item) for item in citations or [] if isinstance(item, Mapping)],
            retrieved_passages=retrieved,
            validation_status=str(_first(validation, "status", default=value.get("validation_status")) or "") or None,
            validation=dict(validation),
            retrieval_latency_ms=number(_first(latency, "retrieval_ms", "retrieval_latency_ms", default=value.get("retrieval_latency_ms"))),
            reranking_latency_ms=number(_first(latency, "reranking_ms", "reranking_latency_ms", default=value.get("reranking_latency_ms"))),
            generation_latency_ms=number(_first(latency, "generation_ms", "generation_latency_ms", default=value.get("generation_latency_ms"))),
            validation_latency_ms=number(_first(latency, "validation_ms", "validation_latency_ms", default=value.get("validation_latency_ms"))),
            total_latency_ms=number(_first(latency, "total_ms", "total_latency_ms", default=value.get("total_latency_ms"))),
            prompt_tokens=integer(_first(usage, "prompt_tokens", "input_tokens", default=value.get("prompt_tokens"))),
            completion_tokens=integer(_first(usage, "completion_tokens", "output_tokens", default=value.get("completion_tokens"))),
            total_tokens=integer(_first(usage, "total_tokens", default=value.get("total_tokens"))),
            estimated_cost_usd=number(cost),
            provenance=provenance,
            raw=dict(value),
            error=str(value.get("error")) if value.get("error") else None,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [citation.__dict__ for citation in self.citations],
            "retrieved_passages": [dict(passage.__dict__) for passage in self.retrieved_passages],
            "validation_status": self.validation_status,
            "validation": dict(self.validation),
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "reranking_latency_ms": self.reranking_latency_ms,
            "generation_latency_ms": self.generation_latency_ms,
            "validation_latency_ms": self.validation_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "provenance": dict(self.provenance),
            "error": self.error,
        }
