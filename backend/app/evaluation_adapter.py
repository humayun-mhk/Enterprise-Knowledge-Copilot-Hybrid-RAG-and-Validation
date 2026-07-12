"""In-process adapter used by the repository evaluation runner.

Example:
    python scripts/run_evaluation.py --adapter python \
      --target backend.app.evaluation_adapter:BackendEvaluationAdapter
"""

from __future__ import annotations

import json
import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from .config import Settings
from .db import Database
from .domain import ChunkRecord
from .schemas import Experiment, QueryRequest, model_dump_compat
from .services.bm25 import BM25Index
from .services.embeddings import build_embedding_service
from .services.generation import AnswerGenerator
from .services.metrics import MetricsRegistry
from .services.rag import RAGService
from .services.reranker import CrossEncoderReranker
from .services.retrieval import RetrievalPipeline
from .services.validator import AnswerValidationAgent
from .services.vector_store import InMemoryVectorStore


class BackendEvaluationAdapter:
    """Index canonical passages once and evaluate A-D without an HTTP server."""

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        temporary_parent = Path(
            os.getenv("EVALUATION_TEMP_DIR", root / "evaluation" / "tmp")
        ).resolve()
        temporary_parent.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = temporary_parent / f"run-{uuid.uuid4().hex}"
        self.runtime_dir.mkdir(parents=True, exist_ok=False)
        self.corpus_path = Path(
            os.getenv(
                "EVALUATION_CORPUS_PATH",
                root / "data" / "ground_truth" / "canonical_passages.jsonl",
            )
        ).resolve()
        offline = os.getenv("EVALUATION_OFFLINE", "true").strip().lower() in {"1", "true", "yes", "on"}
        embedding_provider = os.getenv("EVALUATION_EMBEDDING_PROVIDER", "hash" if offline else os.getenv("EMBEDDING_PROVIDER", "hash"))
        embedding_model = os.getenv("EVALUATION_EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        reranker_enabled = os.getenv("EVALUATION_RERANKER_ENABLED", "false" if offline else os.getenv("RERANKER_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
        settings = Settings(
            data_dir=self.runtime_dir,
            vector_backend="memory",
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider="extractive" if offline else os.getenv("LLM_PROVIDER", "extractive"),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0") or "0"),
            input_cost_per_million_tokens=float(os.getenv("INPUT_COST_PER_MILLION_TOKENS", "0") or "0"),
            output_cost_per_million_tokens=float(os.getenv("OUTPUT_COST_PER_MILLION_TOKENS", "0") or "0"),
            reranker_enabled=reranker_enabled,
            reranker_top_n=10,
            default_top_k=10,
        )
        settings.ensure_directories()
        self.settings = settings
        self.database = Database(settings.sqlite_path)
        self.database.initialize()
        self.embeddings = build_embedding_service(settings)
        self.vectors = InMemoryVectorStore()
        self.bm25 = BM25Index()
        self.reranker = CrossEncoderReranker(settings.reranker_model, settings.reranker_enabled)
        chunks = self._load_corpus(self.corpus_path)
        values = self.embeddings.embed_documents([chunk.chunk_text for chunk in chunks])
        for chunk, embedding in zip(chunks, values):
            chunk.embedding = embedding
        self.vectors.upsert(chunks)
        self.bm25.upsert(chunks)
        retrieval = RetrievalPipeline(settings, self.embeddings, self.vectors, self.bm25, self.reranker)
        self.service = RAGService(
            settings,
            self.database,
            retrieval,
            AnswerGenerator(settings),
            AnswerValidationAgent(settings),
            MetricsRegistry(),
        )
        self.chunk_count = len(chunks)
        self.effective_configs: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _load_corpus(path: Path) -> list[ChunkRecord]:
        if not path.is_file():
            raise FileNotFoundError(f"Canonical evaluation corpus not found: {path}")
        chunks: list[ChunkRecord] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                try:
                    chunks.append(
                        ChunkRecord(
                            chunk_id=str(value["chunk_id"]),
                            document_id=str(value["document_id"]),
                            document_name=str(value["document_name"]),
                            page_number=int(value["page_number"]),
                            section=str(value.get("section") or "") or None,
                            chunk_text=str(value["chunk_text"]),
                            metadata=dict(value.get("metadata") or {}),
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid canonical passage on line {line_number}: {exc}") from exc
        if not chunks:
            raise ValueError(f"Canonical evaluation corpus is empty: {path}")
        return chunks

    def query(self, item: Any, experiment: Mapping[str, Any]) -> Mapping[str, Any]:
        experiment_id = str(experiment.get("id", "D")).upper()
        shared = experiment.get("shared") if isinstance(experiment.get("shared"), Mapping) else {}
        pipeline = experiment.get("pipeline") if isinstance(experiment.get("pipeline"), Mapping) else {}
        final_k = int(shared.get("final_k", experiment.get("top_k", self.settings.default_top_k)))
        self.settings.retrieval_candidate_k = int(
            shared.get("candidate_k", self.settings.retrieval_candidate_k)
        )
        self.settings.reranker_top_n = max(
            final_k, int(pipeline.get("reranker_top_n", final_k))
        )
        self.settings.dense_weight = float(
            pipeline.get("dense_weight", self.settings.dense_weight)
        )
        self.settings.sparse_weight = float(
            pipeline.get("bm25_weight", self.settings.sparse_weight)
        )
        self.settings.rrf_k = int(pipeline.get("rrf_k", self.settings.rrf_k))
        self.effective_configs[experiment_id] = {
            "candidate_k": self.settings.retrieval_candidate_k,
            "final_k": final_k,
            "dense_weight": self.settings.dense_weight,
            "bm25_weight": self.settings.sparse_weight,
            "rrf_k": self.settings.rrf_k,
            "reranker_top_n": self.settings.reranker_top_n,
            "reranker_backend": self.reranker.backend_name,
        }
        response = self.service.query(
            QueryRequest(
                question=str(item.question),
                experiment=Experiment(experiment_id),
                top_k=final_k,
                include_evidence=True,
            )
        )
        return model_dump_compat(response)

    def metadata(self) -> Mapping[str, Any]:
        digest = hashlib.sha256(self.corpus_path.read_bytes()).hexdigest()
        return {
            "backend": "enterprise-knowledge-copilot",
            "corpus": str(self.corpus_path),
            "corpus_sha256": digest,
            "indexed_chunks": self.chunk_count,
            "vector_backend": self.vectors.backend_name,
            "embedding_provider": self.embeddings.provider_name,
            "embedding_model": self.embeddings.model_name,
            "bm25_backend": self.bm25.backend_name,
            "reranker_backend": self.reranker.backend_name,
            "llm_provider": self.settings.llm_provider,
            "offline": self.settings.llm_provider == "extractive",
            "effective_experiment_configs": self.effective_configs,
        }
