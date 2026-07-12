from __future__ import annotations

from app.domain import ChunkRecord, RetrievalHit
from app.schemas import Experiment
from app.services.bm25 import BM25Index
from app.services.embeddings import HashEmbeddingService
from app.services.reranker import CrossEncoderReranker
from app.services.retrieval import RetrievalPipeline, reciprocal_rank_fusion, weighted_fusion
from app.services.vector_store import InMemoryVectorStore


def _chunks() -> list[ChunkRecord]:
    return [
        ChunkRecord("c1", "d1", "Handbook.pdf", 14, "Leave", "Employees receive 20 annual leave days."),
        ChunkRecord("c2", "d2", "Security.pdf", 2, "Passwords", "Passwords must contain at least 14 characters."),
        ChunkRecord("c3", "d3", "Travel.pdf", 4, "Meals", "The dinner reimbursement cap is USD 55."),
    ]


def test_pipeline_runs_controlled_ablation(settings) -> None:
    embeddings = HashEmbeddingService(128)
    chunks = _chunks()
    for chunk, vector in zip(chunks, embeddings.embed_documents([item.chunk_text for item in chunks])):
        chunk.embedding = vector
    vectors = InMemoryVectorStore()
    vectors.upsert(chunks)
    sparse = BM25Index()
    sparse.upsert(chunks)
    pipeline = RetrievalPipeline(
        settings,
        embeddings,
        vectors,
        sparse,
        CrossEncoderReranker("unused", enabled=False),
    )
    for experiment in Experiment:
        outcome = pipeline.retrieve("How many annual leave days do employees receive?", experiment=experiment, top_k=2)
        assert outcome.hits[0].chunk.chunk_id == "c1"
        assert outcome.hits[0].rank == 1
    assert pipeline.retrieve("annual leave", experiment=Experiment.A, top_k=2).route == "dense"


def test_fusion_preserves_component_scores() -> None:
    chunks = _chunks()
    dense = [RetrievalHit(chunks[0], 0.8, rank=1, dense_score=0.8), RetrievalHit(chunks[1], 0.5, rank=2, dense_score=0.5)]
    sparse = [RetrievalHit(chunks[1], 4.0, rank=1, sparse_score=4.0), RetrievalHit(chunks[0], 2.0, rank=2, sparse_score=2.0)]
    weighted = weighted_fusion(dense, sparse, dense_weight=0.6, sparse_weight=0.4, top_k=2)
    assert len(weighted) == 2
    assert all(hit.source == "hybrid_weighted" for hit in weighted)
    fused = reciprocal_rank_fusion([dense, sparse], rrf_k=60, top_k=2)
    assert {hit.chunk.chunk_id for hit in fused} == {"c1", "c2"}
    assert all(hit.source == "hybrid_rrf" for hit in fused)

