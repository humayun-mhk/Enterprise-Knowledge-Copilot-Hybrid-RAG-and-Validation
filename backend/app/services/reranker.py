from __future__ import annotations

import logging
import math
import re
from typing import Sequence

from ..domain import RetrievalHit
from .bm25 import tokenize

logger = logging.getLogger(__name__)


def lexical_relevance(question: str, passage: str) -> float:
    query_tokens = set(tokenize(question, remove_stopwords=True))
    passage_tokens = set(tokenize(passage))
    if not query_tokens:
        return 0.0
    coverage = len(query_tokens & passage_tokens) / len(query_tokens)
    union = len(query_tokens | passage_tokens)
    jaccard = len(query_tokens & passage_tokens) / union if union else 0.0
    numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", question))
    number_coverage = len(numbers & set(re.findall(r"\b\d+(?:\.\d+)?%?\b", passage))) / len(numbers) if numbers else 0.0
    phrase_bonus = 0.15 if question.casefold().strip(" ?.!") in passage.casefold() else 0.0
    return min(1.0, 0.7 * coverage + 0.2 * jaccard + 0.1 * number_coverage + phrase_bonus)


class CrossEncoderReranker:
    """Cross-encoder reranker with a deterministic lexical fallback."""

    def __init__(self, model_name: str, enabled: bool = False):
        self.model_name = model_name
        self.enabled = enabled
        self._model = None
        self.backend_name = "lexical-fallback"

    def _load(self) -> None:
        if not self.enabled or self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            self.backend_name = self.model_name
        except Exception as exc:
            self.enabled = False
            self.backend_name = "lexical-fallback"
            logger.warning("cross_encoder_fallback", extra={"model": self.model_name, "reason": str(exc)})

    def rerank(self, question: str, hits: Sequence[RetrievalHit], *, top_n: int) -> list[RetrievalHit]:
        if not hits:
            return []
        self._load()
        if self._model is not None:
            raw_scores = self._model.predict([(question, hit.chunk.chunk_text) for hit in hits])
            scores = [1.0 / (1.0 + math.exp(-float(value))) for value in raw_scores]
        else:
            scores = [lexical_relevance(question, hit.chunk.chunk_text) for hit in hits]
        reranked: list[RetrievalHit] = []
        for hit, score in zip(hits, scores):
            hit.reranker_score = float(score)
            hit.score = 0.75 * float(score) + 0.25 * float(hit.score)
            hit.source = f"{hit.source}+reranker"
            reranked.append(hit)
        reranked.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        for rank, hit in enumerate(reranked[:top_n], start=1):
            hit.rank = rank
        return reranked[:top_n]
