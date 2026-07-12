from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Experiment(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ValidationStatus(str, Enum):
    APPROVED = "APPROVED"
    REVISE = "REVISE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_RUN = "NOT_RUN"


class DocumentItem(BaseModel):
    document_id: str
    document_name: str
    content_type: str | None = None
    size_bytes: int
    checksum: str
    status: str
    page_count: int = 0
    chunk_count: int = 0
    duplicate: bool = False
    created_at: str
    indexed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    documents: list[DocumentItem]
    indexed: bool = False
    errors: list[dict[str, str]] = Field(default_factory=list)


class IndexRequest(BaseModel):
    document_ids: list[str] | None = None
    force: bool = False
    chunk_size: int | None = Field(default=None, ge=200, le=5000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)


class IndexResult(BaseModel):
    document_id: str
    document_name: str
    status: str
    chunks_indexed: int = 0
    duplicates_skipped: int = 0
    error: str | None = None


class IndexResponse(BaseModel):
    results: list[IndexResult]
    total_chunks_indexed: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    experiment: Experiment = Experiment.D
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[str] | None = None
    include_evidence: bool = True
    conversation_id: str | None = None


class Citation(BaseModel):
    document: str
    page: int | None
    chunk_id: str
    quoted_evidence: str
    section: str | None = None


class EvidenceItem(BaseModel):
    chunk_id: str
    document_id: str
    document: str
    document_name: str
    page: int | None
    page_number: int | None
    section: str | None = None
    passage: str
    text: str
    chunk_text: str
    score: float
    rank: int
    source: str
    dense_score: float | None = None
    sparse_score: float | None = None
    reranker_score: float | None = None


class ValidationResult(BaseModel):
    status: ValidationStatus
    supported_claims: int
    unsupported_claims: int
    citation_coverage: float
    citation_precision: float = 0.0
    corrected_answer: str | None = None
    reason: str
    unsupported_details: list[str] = Field(default_factory=list)
    contradictory_claims: list[str] = Field(default_factory=list)


class QueryTimings(BaseModel):
    preprocessing_ms: float = 0.0
    retrieval_ms: float = 0.0
    reranking_ms: float = 0.0
    generation_ms: float = 0.0
    validation_ms: float = 0.0
    total_ms: float = 0.0


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    citations: list[Citation]
    validation: ValidationResult
    confidence: float
    experiment: Experiment
    route: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    timings: QueryTimings
    token_usage: TokenUsage
    model_provider: str
    model_name: str
    prompt_version: str
    retrieval_config_version: str
    component_backends: dict[str, str] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    query_id: str
    rating: int | None = Field(default=None, ge=1, le=5)
    helpful: bool | None = None
    comment: str | None = Field(default=None, max_length=4000)
    selected_citation_chunk_id: str | None = None

    @model_validator(mode="after")
    def require_feedback_signal(self) -> "FeedbackRequest":
        if not any(
            value is not None and value != ""
            for value in (
                self.rating,
                self.helpful,
                self.comment,
                self.selected_citation_chunk_id,
            )
        ):
            raise ValueError("Provide a rating, helpful flag, comment, or selected citation")
        return self


class FeedbackResponse(BaseModel):
    feedback_id: str
    accepted: bool = True


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    vector_backend: str
    embedding_provider: str
    embedding_model: str
    bm25_backend: str
    reranker_backend: str
    llm_provider: str
    llm_model: str
    validator_backend: str
    indexed_chunks: int


def model_dump_compat(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()
