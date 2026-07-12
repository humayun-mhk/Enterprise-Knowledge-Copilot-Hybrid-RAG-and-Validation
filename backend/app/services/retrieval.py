from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Sequence

from ..config import Settings
from ..domain import RetrievalHit
from ..schemas import Experiment
from .bm25 import BM25Index, tokenize
from .embeddings import EmbeddingService
from .reranker import CrossEncoderReranker
from .vector_store import VectorStore


@dataclass(slots=True)
class ProcessedQuery:
    original: str
    normalized: str
    keywords: list[str]
    quoted_phrases: list[str]


@dataclass(slots=True)
class RetrievalOutcome:
    hits: list[RetrievalHit]
    route: str
    preprocessing_ms: float
    retrieval_ms: float
    reranking_ms: float


def preprocess_query(question: str) -> ProcessedQuery:
    normalized = re.sub(r"\s+", " ", question).strip()
    quoted = [item.strip() for item in re.findall(r'["“](.*?)["”]', normalized) if item.strip()]
    keywords = tokenize(normalized, remove_stopwords=True)
    return ProcessedQuery(
        original=question,
        normalized=normalized,
        keywords=list(dict.fromkeys(keywords)),
        quoted_phrases=quoted,
    )


class QueryRouter:
    def route(self, query: ProcessedQuery, experiment: Experiment) -> str:
        if experiment == Experiment.A:
            return "dense"
        has_identifier = bool(re.search(r"\b(?:[A-Z]{2,}[-_]?[0-9]{2,}|\d+(?:\.\d+){1,})\b", query.original))
        if query.quoted_phrases or has_identifier:
            return "exact_policy_hybrid"
        if len(query.keywords) <= 2:
            return "short_query_hybrid"
        return "hybrid"


def _normalize_positive(values: list[float]) -> list[float]:
    positives = [max(0.0, value) for value in values]
    maximum = max(positives, default=0.0)
    return [value / maximum if maximum else 0.0 for value in positives]


def weighted_fusion(
    dense_hits: Sequence[RetrievalHit],
    sparse_hits: Sequence[RetrievalHit],
    *,
    dense_weight: float,
    sparse_weight: float,
    top_k: int,
) -> list[RetrievalHit]:
    dense_normalized = _normalize_positive([hit.score for hit in dense_hits])
    sparse_normalized = _normalize_positive([hit.score for hit in sparse_hits])
    merged: dict[str, RetrievalHit] = {}
    scores: dict[str, float] = {}
    for hit, normalized in zip(dense_hits, dense_normalized):
        merged[hit.chunk.chunk_id] = hit
        hit.dense_score = hit.score
        scores[hit.chunk.chunk_id] = scores.get(hit.chunk.chunk_id, 0.0) + dense_weight * normalized
    for hit, normalized in zip(sparse_hits, sparse_normalized):
        existing = merged.get(hit.chunk.chunk_id)
        if existing:
            existing.sparse_score = hit.score
        else:
            merged[hit.chunk.chunk_id] = hit
        scores[hit.chunk.chunk_id] = scores.get(hit.chunk.chunk_id, 0.0) + sparse_weight * normalized
    output = list(merged.values())
    for hit in output:
        hit.score = scores[hit.chunk.chunk_id]
        hit.source = "hybrid_weighted"
    output.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
    for rank, hit in enumerate(output[:top_k], start=1):
        hit.rank = rank
    return output[:top_k]


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[RetrievalHit]], *, rrf_k: int = 60, top_k: int = 20
) -> list[RetrievalHit]:
    merged: dict[str, RetrievalHit] = {}
    scores: dict[str, float] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            chunk_id = hit.chunk.chunk_id
            if chunk_id not in merged:
                merged[chunk_id] = hit
            else:
                existing = merged[chunk_id]
                existing.dense_score = existing.dense_score if existing.dense_score is not None else hit.dense_score
                existing.sparse_score = existing.sparse_score if existing.sparse_score is not None else hit.sparse_score
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    output = list(merged.values())
    for hit in output:
        hit.score = scores[hit.chunk.chunk_id]
        hit.source = "hybrid_rrf"
    output.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
    for rank, hit in enumerate(output[:top_k], start=1):
        hit.rank = rank
    return output[:top_k]


class RetrievalPipeline:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingService,
        vectors: VectorStore,
        bm25: BM25Index,
        reranker: CrossEncoderReranker,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vectors = vectors
        self.bm25 = bm25
        self.reranker = reranker
        self.router = QueryRouter()

    def retrieve(
        self,
        question: str,
        *,
        experiment: Experiment,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> RetrievalOutcome:
        start = time.perf_counter()
        processed = preprocess_query(question)
        route = self.router.route(processed, experiment)
        preprocessing_ms = (time.perf_counter() - start) * 1000

        retrieval_start = time.perf_counter()
        query_embedding = self.embeddings.embed_query(processed.normalized)
        candidate_k = max(top_k, self.settings.retrieval_candidate_k)
        dense = self.vectors.search(query_embedding, top_k=candidate_k, document_ids=document_ids)

        if experiment == Experiment.A:
            hits = dense[:top_k]
            for rank, hit in enumerate(hits, start=1):
                hit.rank = rank
            retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
            return RetrievalOutcome(hits, route, preprocessing_ms, retrieval_ms, 0.0)

        sparse = self.bm25.search(processed.normalized, top_k=candidate_k, document_ids=document_ids)
        if experiment == Experiment.B:
            hits = weighted_fusion(
                dense,
                sparse,
                dense_weight=self.settings.dense_weight,
                sparse_weight=self.settings.sparse_weight,
                top_k=top_k,
            )
            retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
            return RetrievalOutcome(hits, route, preprocessing_ms, retrieval_ms, 0.0)

        fused = reciprocal_rank_fusion(
            [dense, sparse], rrf_k=self.settings.rrf_k, top_k=candidate_k
        )
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
        reranking_start = time.perf_counter()
        hits = self.reranker.rerank(
            processed.normalized,
            fused,
            top_n=min(top_k, self.settings.reranker_top_n),
        )
        reranking_ms = (time.perf_counter() - reranking_start) * 1000
        return RetrievalOutcome(hits, route, preprocessing_ms, retrieval_ms, reranking_ms)

