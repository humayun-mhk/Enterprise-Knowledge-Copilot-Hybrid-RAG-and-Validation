from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..db import Database
from .bm25 import BM25Index
from .embeddings import EmbeddingService, build_embedding_service
from .generation import AnswerGenerator
from .indexing import IndexingService
from .metrics import MetricsRegistry
from .rag import RAGService
from .reranker import CrossEncoderReranker
from .retrieval import RetrievalPipeline
from .validator import AnswerValidationAgent
from .vector_store import VectorStore, build_vector_store


@dataclass(slots=True)
class AppServices:
    settings: Settings
    database: Database
    embeddings: EmbeddingService
    vectors: VectorStore
    bm25: BM25Index
    reranker: CrossEncoderReranker
    indexing: IndexingService
    validator: AnswerValidationAgent
    generator: AnswerGenerator
    metrics: MetricsRegistry
    rag: RAGService

    @property
    def component_backends(self) -> dict[str, str]:
        return {
            "embedding_provider": self.embeddings.provider_name,
            "embedding_model": self.embeddings.model_name,
            "vector_backend": self.vectors.backend_name,
            "bm25_backend": self.bm25.backend_name,
            "reranker_backend": self.reranker.backend_name,
            "llm_provider": self.settings.llm_provider,
            "validator_backend": self.validator.graph_backend,
        }

    def close(self) -> None:
        self.database.close()


def build_services(settings: Settings) -> AppServices:
    settings.ensure_directories()
    database = Database(settings.sqlite_path)
    database.initialize()
    embeddings = build_embedding_service(settings)
    assert settings.chroma_dir is not None
    vectors = build_vector_store(settings.vector_backend, settings.chroma_dir)
    bm25 = BM25Index()
    reranker = CrossEncoderReranker(settings.reranker_model, settings.reranker_enabled)
    indexing = IndexingService(settings, database, embeddings, vectors, bm25)
    indexing.rehydrate()
    validator = AnswerValidationAgent(settings)
    generator = AnswerGenerator(settings)
    metrics = MetricsRegistry()
    retrieval = RetrievalPipeline(settings, embeddings, vectors, bm25, reranker)
    rag = RAGService(settings, database, retrieval, generator, validator, metrics)
    return AppServices(
        settings=settings,
        database=database,
        embeddings=embeddings,
        vectors=vectors,
        bm25=bm25,
        reranker=reranker,
        indexing=indexing,
        validator=validator,
        generator=generator,
        metrics=metrics,
        rag=rag,
    )
