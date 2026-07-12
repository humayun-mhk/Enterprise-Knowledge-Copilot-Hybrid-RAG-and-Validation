from __future__ import annotations

import logging
import math
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from ..domain import ChunkRecord, RetrievalHit

logger = logging.getLogger(__name__)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


class VectorStore(ABC):
    backend_name = "abstract"

    @abstractmethod
    def upsert(self, chunks: Sequence[ChunkRecord]) -> None: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: Sequence[float], *, top_k: int, document_ids: Sequence[str] | None = None
    ) -> list[RetrievalHit]: ...

    @abstractmethod
    def count(self) -> int: ...


class InMemoryVectorStore(VectorStore):
    backend_name = "memory"

    def __init__(self) -> None:
        self._chunks: dict[str, ChunkRecord] = {}
        self._lock = threading.RLock()

    def upsert(self, chunks: Sequence[ChunkRecord]) -> None:
        with self._lock:
            for chunk in chunks:
                if chunk.embedding is None:
                    raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")
                self._chunks[chunk.chunk_id] = chunk

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            keys = [key for key, chunk in self._chunks.items() if chunk.document_id == document_id]
            for key in keys:
                del self._chunks[key]

    def search(
        self, query_embedding: Sequence[float], *, top_k: int, document_ids: Sequence[str] | None = None
    ) -> list[RetrievalHit]:
        allowed = set(document_ids or [])
        with self._lock:
            scored = [
                (cosine_similarity(query_embedding, chunk.embedding or []), chunk)
                for chunk in self._chunks.values()
                if not allowed or chunk.document_id in allowed
            ]
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalHit(chunk=chunk, score=float(score), dense_score=float(score), rank=rank, source="dense")
            for rank, (score, chunk) in enumerate(scored[: max(0, top_k)], start=1)
        ]

    def count(self) -> int:
        return len(self._chunks)


class ChromaVectorStore(VectorStore):
    backend_name = "chroma"

    def __init__(self, path: Path, collection_name: str = "enterprise_knowledge") -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._chunks: dict[str, ChunkRecord] = {}
        self._lock = threading.RLock()

    def upsert(self, chunks: Sequence[ChunkRecord]) -> None:
        if not chunks:
            return
        valid = [chunk for chunk in chunks if chunk.embedding is not None]
        if not valid:
            return
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in valid],
            embeddings=[chunk.embedding for chunk in valid],
            documents=[chunk.chunk_text for chunk in valid],
            metadatas=[chunk.vector_metadata() for chunk in valid],
        )
        with self._lock:
            for chunk in valid:
                self._chunks[chunk.chunk_id] = chunk

    def delete_document(self, document_id: str) -> None:
        try:
            self.collection.delete(where={"document_id": document_id})
        finally:
            with self._lock:
                for key in [key for key, value in self._chunks.items() if value.document_id == document_id]:
                    del self._chunks[key]

    def search(
        self, query_embedding: Sequence[float], *, top_k: int, document_ids: Sequence[str] | None = None
    ) -> list[RetrievalHit]:
        if top_k <= 0 or self.count() == 0:
            return []
        where: dict[str, object] | None = None
        if document_ids:
            where = (
                {"document_id": document_ids[0]}
                if len(document_ids) == 1
                else {"document_id": {"$in": list(document_ids)}}
            )
        result = self.collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=min(top_k, max(1, self.count())),
            where=where,
            include=["distances", "metadatas", "documents"],
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        hits: list[RetrievalHit] = []
        for rank, chunk_id in enumerate(ids, start=1):
            chunk = self._chunks.get(chunk_id)
            if chunk is None:
                metadata = metadatas[rank - 1] or {}
                chunk = ChunkRecord(
                    chunk_id=chunk_id,
                    document_id=str(metadata.get("document_id", "")),
                    document_name=str(metadata.get("document_name", "unknown")),
                    page_number=int(metadata.get("page_number") or 0) or None,
                    section=str(metadata.get("section") or "") or None,
                    chunk_text=str(documents[rank - 1] or ""),
                    metadata=dict(metadata),
                )
            score = 1.0 - float(distances[rank - 1])
            hits.append(
                RetrievalHit(chunk=chunk, score=score, dense_score=score, rank=rank, source="dense")
            )
        return hits

    def count(self) -> int:
        return int(self.collection.count())


def build_vector_store(backend: str, chroma_path: Path) -> VectorStore:
    backend = backend.lower()
    if backend == "memory":
        return InMemoryVectorStore()
    if backend not in {"auto", "chroma"}:
        logger.warning("unknown_vector_backend", extra={"requested_backend": backend})
        return InMemoryVectorStore()
    try:
        return ChromaVectorStore(chroma_path)
    except Exception as exc:
        logger.warning("chroma_fallback_to_memory", extra={"reason": str(exc)})
        return InMemoryVectorStore()
