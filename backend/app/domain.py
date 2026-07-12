from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int | None
    section: str | None
    chunk_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    content_hash: str = ""

    def vector_metadata(self) -> dict[str, str | int | float | bool]:
        output: dict[str, str | int | float | bool] = {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page_number": self.page_number or 0,
            "section": self.section or "",
        }
        for key, value in self.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                output[key] = value
        return output


@dataclass(slots=True)
class RetrievalHit:
    chunk: ChunkRecord
    score: float
    rank: int = 0
    source: str = "dense"
    dense_score: float | None = None
    sparse_score: float | None = None
    reranker_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "document": self.chunk.document_name,
            "document_name": self.chunk.document_name,
            "page": self.chunk.page_number,
            "page_number": self.chunk.page_number,
            "section": self.chunk.section,
            "passage": self.chunk.chunk_text,
            "text": self.chunk.chunk_text,
            "chunk_text": self.chunk.chunk_text,
            "score": round(float(self.score), 6),
            "rank": self.rank,
            "source": self.source,
            "dense_score": None if self.dense_score is None else round(float(self.dense_score), 6),
            "sparse_score": None if self.sparse_score is None else round(float(self.sparse_score), 6),
            "reranker_score": None if self.reranker_score is None else round(float(self.reranker_score), 6),
        }
