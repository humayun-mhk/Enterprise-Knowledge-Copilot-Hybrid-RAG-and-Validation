from __future__ import annotations

import logging
import time
import uuid

from ..config import Settings
from ..db import Database
from ..schemas import (
    EvidenceItem,
    Experiment,
    QueryRequest,
    QueryResponse,
    QueryTimings,
    TokenUsage,
    ValidationResult,
    ValidationStatus,
)
from .citations import generate_citations
from .generation import AnswerGenerator, REFUSAL_TEXT
from .metrics import MetricsRegistry
from .reranker import lexical_relevance
from .retrieval import RetrievalPipeline
from .validator import AnswerValidationAgent

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        retrieval: RetrievalPipeline,
        generator: AnswerGenerator,
        validator: AnswerValidationAgent,
        metrics: MetricsRegistry,
    ) -> None:
        self.settings = settings
        self.database = database
        self.retrieval = retrieval
        self.generator = generator
        self.validator = validator
        self.metrics = metrics

    def query(self, request: QueryRequest) -> QueryResponse:
        query_id = str(uuid.uuid4())
        total_start = time.perf_counter()
        try:
            outcome = self.retrieval.retrieve(
                request.question,
                experiment=request.experiment,
                top_k=request.top_k,
                document_ids=request.document_ids,
            )
            hits = outcome.hits
            best_alignment = max(
                (lexical_relevance(request.question, hit.chunk.chunk_text) for hit in hits),
                default=0.0,
            )
            best_dense = max((hit.dense_score or 0.0 for hit in hits), default=0.0)
            retrieval_strength = max((max(0.0, min(1.0, hit.score)) for hit in hits), default=0.0)
            confidence = round(min(1.0, 0.65 * best_alignment + 0.35 * retrieval_strength), 6)
            evidence_sufficient = bool(hits) and (
                best_alignment >= self.settings.min_retrieval_score or best_dense >= 0.35
            )

            generation_start = time.perf_counter()
            if evidence_sufficient:
                generated = self.generator.generate(request.question, hits)
            else:
                generated = self.generator.extractive.generate(request.question, [])
            generation_ms = (time.perf_counter() - generation_start) * 1000

            if request.experiment == Experiment.D:
                answer, citations = generate_citations(generated.text, hits if evidence_sufficient else [])
                validation_start = time.perf_counter()
                validation = self.validator.validate(
                    question=request.question,
                    answer=answer,
                    hits=hits if evidence_sufficient else [],
                    citations=citations,
                )
                validation_ms = (time.perf_counter() - validation_start) * 1000
                if validation.status == ValidationStatus.INSUFFICIENT_EVIDENCE:
                    answer, citations, confidence = REFUSAL_TEXT, [], 0.0
                elif validation.status == ValidationStatus.REVISE and validation.corrected_answer:
                    answer, citations = generate_citations(validation.corrected_answer, hits)
                    confidence = min(confidence, 0.75)
            else:
                answer = generated.text
                citations = []
                validation_ms = 0.0
                validation = ValidationResult(
                    status=ValidationStatus.NOT_RUN,
                    supported_claims=0,
                    unsupported_claims=0,
                    citation_coverage=0.0,
                    citation_precision=0.0,
                    corrected_answer=None,
                    reason="Citation generation and answer validation are disabled for experiments A-C.",
                )

            total_ms = (time.perf_counter() - total_start) * 1000
            timings = QueryTimings(
                preprocessing_ms=round(outcome.preprocessing_ms, 3),
                retrieval_ms=round(outcome.retrieval_ms, 3),
                reranking_ms=round(outcome.reranking_ms, 3),
                generation_ms=round(generation_ms, 3),
                validation_ms=round(validation_ms, 3),
                total_ms=round(total_ms, 3),
            )
            token_usage = TokenUsage(
                prompt_tokens=generated.prompt_tokens,
                completion_tokens=generated.completion_tokens,
                total_tokens=generated.prompt_tokens + generated.completion_tokens,
                estimated_cost_usd=round(generated.estimated_cost_usd, 8),
            )
            evidence = [EvidenceItem(**hit.to_dict()) for hit in hits] if request.include_evidence else []
            response = QueryResponse(
                query_id=query_id,
                answer=answer,
                citations=citations,
                validation=validation,
                confidence=confidence,
                experiment=request.experiment,
                route=outcome.route,
                evidence=evidence,
                timings=timings,
                token_usage=token_usage,
                model_provider=generated.provider,
                model_name=generated.model_name,
                prompt_version=self.settings.prompt_version,
                retrieval_config_version=self.settings.retrieval_config_version,
                component_backends={
                    "embedding": f"{self.retrieval.embeddings.provider_name}:{self.retrieval.embeddings.model_name}",
                    "vector_store": self.retrieval.vectors.backend_name,
                    "bm25": self.retrieval.bm25.backend_name,
                    "reranker": self.retrieval.reranker.backend_name,
                    "generator": f"{generated.provider}:{generated.model_name}",
                    "validator": self.validator.graph_backend if request.experiment == Experiment.D else "not_run",
                },
            )
            self.database.record_query(
                {
                    "query_id": query_id,
                    "question": request.question,
                    "experiment": request.experiment.value,
                    "status": validation.status.value,
                    "confidence": confidence,
                    "citation_coverage": validation.citation_coverage,
                    "retrieval_ms": timings.retrieval_ms,
                    "total_ms": timings.total_ms,
                    "prompt_tokens": token_usage.prompt_tokens,
                    "completion_tokens": token_usage.completion_tokens,
                    "estimated_cost_usd": token_usage.estimated_cost_usd,
                }
            )
            self.metrics.increment("total_queries")
            if validation.status == ValidationStatus.INSUFFICIENT_EVIDENCE:
                self.metrics.increment("insufficient_evidence_responses")
            if confidence < 0.5:
                self.metrics.increment("low_confidence_answers")
            return response
        except Exception as exc:
            total_ms = (time.perf_counter() - total_start) * 1000
            self.metrics.increment("query_errors")
            self.database.record_query(
                {
                    "query_id": query_id,
                    "question": request.question,
                    "experiment": request.experiment.value,
                    "status": "ERROR",
                    "confidence": 0,
                    "citation_coverage": 0,
                    "retrieval_ms": 0,
                    "total_ms": total_ms,
                    "error": str(exc),
                }
            )
            logger.exception("query_failed", extra={"query_id": query_id})
            raise
