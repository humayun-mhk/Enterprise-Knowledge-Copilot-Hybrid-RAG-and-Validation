from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from ..config import Settings
from ..db import Database
from ..schemas import IndexRequest, IndexResult
from .bm25 import BM25Index
from .embeddings import EmbeddingService
from .ingestion import build_chunks, parse_document
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        embeddings: EmbeddingService,
        vectors: VectorStore,
        bm25: BM25Index,
    ) -> None:
        self.settings = settings
        self.database = database
        self.embeddings = embeddings
        self.vectors = vectors
        self.bm25 = bm25

    def rehydrate(self) -> int:
        chunks = self.database.list_chunks()
        if not chunks:
            return 0
        missing = [chunk for chunk in chunks if chunk.embedding is None]
        if missing:
            embeddings = self._embed([chunk.chunk_text for chunk in missing])
            for chunk, embedding in zip(missing, embeddings):
                chunk.embedding = embedding
            # Persisting the full documents is avoided here; a forced re-index is
            # the migration path when an embedding model/config version changes.
        self.vectors.upsert(chunks)
        self.bm25.upsert(chunks)
        logger.info("indexes_rehydrated", extra={"chunk_count": len(chunks)})
        return len(chunks)

    def _embed(self, texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
        output: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            output.extend(self.embeddings.embed_documents(texts[start : start + batch_size]))
        return output

    def _select_documents(self, request: IndexRequest) -> list[dict]:
        if request.document_ids is not None:
            documents = []
            for document_id in request.document_ids:
                document = self.database.get_document(document_id, include_private=True)
                if document:
                    documents.append(document)
            return documents
        documents = []
        for item in self.database.list_documents():
            if not request.force and item["status"] == "indexed":
                continue
            document = self.database.get_document(item["document_id"], include_private=True)
            if document:
                documents.append(document)
        return documents

    def index(self, request: IndexRequest) -> list[IndexResult]:
        results: list[IndexResult] = []
        chunk_size = request.chunk_size or self.settings.chunk_size
        overlap = request.chunk_overlap if request.chunk_overlap is not None else self.settings.chunk_overlap
        if overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        for document in self._select_documents(request):
            if not document:
                continue
            document_id = document["document_id"]
            document_name = document["document_name"]
            if document["status"] == "indexed" and not request.force:
                results.append(
                    IndexResult(
                        document_id=document_id,
                        document_name=document_name,
                        status="already_indexed",
                        chunks_indexed=int(document.get("chunk_count", 0)),
                    )
                )
                continue
            self.database.set_document_status(document_id, "indexing")
            try:
                parsed = parse_document(Path(document["stored_path"]), document["extension"])
                chunks, in_document_duplicates = build_chunks(
                    parsed,
                    document_id=document_id,
                    document_name=document_name,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
                embeddings = self._embed([chunk.chunk_text for chunk in chunks])
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding

                if request.force:
                    self.vectors.delete_document(document_id)
                    self.bm25.delete_document(document_id)
                inserted, database_duplicates = self.database.save_chunks(
                    chunks,
                    replace_document_id=document_id if request.force else None,
                )
                persisted = self.database.list_chunks([document_id])
                self.vectors.upsert(persisted)
                self.bm25.upsert(persisted)
                self.database.update_document_metadata(
                    document_id,
                    {
                        **parsed.metadata,
                        "chunk_size": chunk_size,
                        "chunk_overlap": overlap,
                        "embedding_provider": self.embeddings.provider_name,
                        "embedding_model": self.embeddings.model_name,
                    },
                )
                self.database.set_document_status(
                    document_id,
                    "indexed",
                    page_count=parsed.page_count,
                    chunk_count=len(persisted),
                )
                results.append(
                    IndexResult(
                        document_id=document_id,
                        document_name=document_name,
                        status="indexed",
                        chunks_indexed=inserted,
                        duplicates_skipped=in_document_duplicates + database_duplicates,
                    )
                )
                logger.info(
                    "document_indexed",
                    extra={"document_id": document_id, "chunk_count": inserted},
                )
            except Exception as exc:
                self.database.set_document_status(document_id, "failed", error=str(exc))
                results.append(
                    IndexResult(
                        document_id=document_id,
                        document_name=document_name,
                        status="failed",
                        error=str(exc),
                    )
                )
                logger.exception("document_index_failed", extra={"document_id": document_id})
        return results
