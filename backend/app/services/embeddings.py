from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from typing import Protocol, Sequence

from ..config import Settings

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'/-]*")


class EmbeddingService(Protocol):
    provider_name: str
    model_name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingService:
    """Deterministic local embeddings suitable for offline fallback and CI.

    Token and character n-gram feature hashing provides meaningful lexical
    similarity without downloading a model. It is not presented as a learned
    semantic embedding model.
    """

    provider_name = "hash"

    def __init__(self, dimension: int = 384):
        self.dimension = max(64, int(dimension))
        self.model_name = f"feature-hash-{self.dimension}d-v1"

    @staticmethod
    def _features(text: str) -> list[tuple[str, float]]:
        tokens = [token.casefold() for token in TOKEN_PATTERN.findall(text)]
        features: list[tuple[str, float]] = [(f"w:{token}", 1.0) for token in tokens]
        features.extend((f"b:{left}_{right}", 0.6) for left, right in zip(tokens, tokens[1:]))
        for token in tokens:
            if len(token) >= 5:
                features.extend((f"c:{token[index:index + 3]}", 0.15) for index in range(len(token) - 2))
        return features

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for feature, weight in self._features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "little") % self.dimension
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LangChainEmbeddingService:
    def __init__(self, provider: str, model: str, settings: Settings):
        self.provider_name = provider
        self.model_name = model
        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not configured")
            from langchain_openai import OpenAIEmbeddings

            self.client = OpenAIEmbeddings(model=model, check_embedding_ctx_length=False)
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings

            self.client = OllamaEmbeddings(model=model or "nomic-embed-text", base_url=settings.ollama_base_url)
        elif provider in {"gemini", "google"}:
            if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
                raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is not configured")
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            self.client = GoogleGenerativeAIEmbeddings(model=model or "models/text-embedding-004")
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(item) for item in self.client.embed_documents(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return list(self.client.embed_query(text))


class SentenceTransformerEmbeddingService:
    provider_name = "sentence_transformers"

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model or "all-MiniLM-L6-v2"
        self.client = SentenceTransformer(self.model_name)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        values = self.client.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [list(map(float, row)) for row in values]

    def embed_query(self, text: str) -> list[float]:
        value = self.client.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return list(map(float, value))


def build_embedding_service(settings: Settings) -> EmbeddingService:
    if settings.embedding_provider == "hash":
        return HashEmbeddingService(settings.embedding_dimension)
    try:
        if settings.embedding_provider in {"sentence_transformers", "sentence-transformers", "local"}:
            return SentenceTransformerEmbeddingService(settings.embedding_model)
        return LangChainEmbeddingService(settings.embedding_provider, settings.embedding_model, settings)
    except Exception as exc:
        logger.warning(
            "embedding_provider_fallback",
            extra={"provider": settings.embedding_provider, "reason": str(exc)},
        )
        return HashEmbeddingService(settings.embedding_dimension)
