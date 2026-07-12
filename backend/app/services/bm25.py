from __future__ import annotations

import math
import re
import threading
from collections import Counter
from typing import Sequence

from ..domain import ChunkRecord, RetrievalHit

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'/-]*")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def tokenize(text: str, *, remove_stopwords: bool = False) -> list[str]:
    tokens = [token.casefold().strip("_-/") for token in TOKEN_PATTERN.findall(text)]
    if remove_stopwords:
        return [token for token in tokens if token and token not in STOPWORDS]
    return [token for token in tokens if token]


class BM25Index:
    """Thread-safe BM25 index with no external service dependency."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._chunks: dict[str, ChunkRecord] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequencies: Counter[str] = Counter()
        self._lengths: dict[str, int] = {}
        self._average_length = 0.0
        self._ordered_ids: list[str] = []
        self._engine = None
        self.backend_name = "bm25-native-fallback"
        self._lock = threading.RLock()

    def _rebuild(self) -> None:
        self._term_frequencies.clear()
        self._document_frequencies.clear()
        self._lengths.clear()
        self._ordered_ids = list(self._chunks)
        corpus: list[list[str]] = []
        for chunk_id, chunk in self._chunks.items():
            tokens = tokenize(chunk.chunk_text)
            corpus.append(tokens)
            frequencies = Counter(tokens)
            self._term_frequencies[chunk_id] = frequencies
            self._lengths[chunk_id] = len(tokens)
            self._document_frequencies.update(frequencies.keys())
        self._average_length = (
            sum(self._lengths.values()) / len(self._lengths) if self._lengths else 0.0
        )
        try:
            from rank_bm25 import BM25Okapi

            self._engine = BM25Okapi(corpus, k1=self.k1, b=self.b) if corpus else None
            self.backend_name = "rank_bm25" if corpus else "rank_bm25-empty"
        except ImportError:
            self._engine = None
            self.backend_name = "bm25-native-fallback"

    def upsert(self, chunks: Sequence[ChunkRecord]) -> None:
        with self._lock:
            self._chunks.update({chunk.chunk_id: chunk for chunk in chunks})
            self._rebuild()

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            for key in [key for key, chunk in self._chunks.items() if chunk.document_id == document_id]:
                del self._chunks[key]
            self._rebuild()

    def _score(self, chunk_id: str, query_tokens: Sequence[str]) -> float:
        total_documents = len(self._chunks)
        if not total_documents or not self._average_length:
            return 0.0
        frequencies = self._term_frequencies[chunk_id]
        length = self._lengths[chunk_id]
        score = 0.0
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            document_frequency = self._document_frequencies.get(token, 0)
            inverse_document_frequency = math.log(
                1.0 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + self.k1 * (
                1.0 - self.b + self.b * length / self._average_length
            )
            score += inverse_document_frequency * frequency * (self.k1 + 1.0) / denominator
        return score

    def search(
        self, query: str, *, top_k: int, document_ids: Sequence[str] | None = None
    ) -> list[RetrievalHit]:
        query_tokens = tokenize(query, remove_stopwords=True) or tokenize(query)
        if not query_tokens:
            return []
        allowed = set(document_ids or [])
        with self._lock:
            if self._engine is not None:
                engine_scores = self._engine.get_scores(query_tokens)
                scored = [
                    (float(engine_scores[index]), self._chunks[chunk_id])
                    for index, chunk_id in enumerate(self._ordered_ids)
                    if not allowed or self._chunks[chunk_id].document_id in allowed
                ]
                # BM25Okapi's Robertson IDF can be non-positive when every
                # document contains a term (most visibly in a one-chunk index).
                # Returning no result for an exact match is unsafe for newly
                # created/small collections, so use the positive-IDF native
                # formula only when the library produces no positive matching
                # candidate. The normal multi-document path remains rank_bm25.
                matching = [
                    item
                    for item in scored
                    if any(
                        self._term_frequencies[item[1].chunk_id].get(token, 0)
                        for token in query_tokens
                    )
                ]
                if matching and not any(score > 0 for score, _ in matching):
                    scored = [
                        (self._score(chunk.chunk_id, query_tokens), chunk)
                        for _, chunk in matching
                    ]
            else:
                scored = [
                    (self._score(chunk_id, query_tokens), chunk)
                    for chunk_id, chunk in self._chunks.items()
                    if not allowed or chunk.document_id in allowed
                ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalHit(
                chunk=chunk,
                score=float(score),
                sparse_score=float(score),
                rank=rank,
                source="bm25",
            )
            for rank, (score, chunk) in enumerate(scored[: max(0, top_k)], start=1)
        ]

    def count(self) -> int:
        return len(self._chunks)
