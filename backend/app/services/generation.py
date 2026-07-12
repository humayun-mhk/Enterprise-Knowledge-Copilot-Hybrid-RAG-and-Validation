from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Sequence

from ..config import Settings
from ..domain import RetrievalHit
from .reranker import lexical_relevance

logger = logging.getLogger(__name__)

REFUSAL_TEXT = "I don't have enough evidence in the indexed documents to answer that question."


@dataclass(slots=True)
class GenerationResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider: str = "extractive"
    model_name: str = "deterministic-extractive-v1"


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized) if part.strip()]


class ExtractiveAnswerGenerator:
    provider = "extractive"
    model_name = "deterministic-extractive-v1"

    def __init__(self, max_sentences: int = 5):
        self.max_sentences = max(1, max_sentences)

    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> GenerationResult:
        candidates: list[tuple[float, int, str]] = []
        for hit in hits:
            sentences = split_sentences(hit.chunk.chunk_text) or [hit.chunk.chunk_text.strip()]
            for sentence in sentences:
                relevance = lexical_relevance(question, sentence)
                if relevance > 0:
                    candidates.append((0.85 * relevance + 0.15 * max(0.0, hit.score), hit.rank, sentence))
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        selected: list[str] = []
        seen: set[str] = set()
        for score, _, sentence in candidates:
            key = re.sub(r"\W+", " ", sentence.casefold()).strip()
            if score < 0.12 or not key or key in seen:
                continue
            if any(key in existing or existing in key for existing in seen):
                continue
            selected.append(sentence)
            seen.add(key)
            if len(selected) >= self.max_sentences:
                break
        text = " ".join(selected) if selected else REFUSAL_TEXT
        return GenerationResult(text=text, provider=self.provider, model_name=self.model_name)


class LangChainAnswerGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm_provider
        self.model_name = settings.llm_model or self._default_model(self.provider)
        self._client: Any = None

    @staticmethod
    def _default_model(provider: str) -> str:
        return {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-latest",
            "gemini": "gemini-2.0-flash",
            "google": "gemini-2.0-flash",
            "ollama": "llama3.1",
        }.get(provider, "")

    def _load(self) -> Any:
        if self._client is not None:
            return self._client
        provider = self.provider
        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not configured")
            from langchain_openai import ChatOpenAI

            self._client = ChatOpenAI(model=self.model_name, temperature=self.settings.llm_temperature)
        elif provider == "anthropic":
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY is not configured")
            from langchain_anthropic import ChatAnthropic

            self._client = ChatAnthropic(model=self.model_name, temperature=self.settings.llm_temperature)
        elif provider in {"gemini", "google"}:
            if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
                raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is not configured")
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._client = ChatGoogleGenerativeAI(model=self.model_name, temperature=self.settings.llm_temperature)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama

            self._client = ChatOllama(
                model=self.model_name,
                temperature=self.settings.llm_temperature,
                base_url=self.settings.ollama_base_url,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        return self._client

    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> GenerationResult:
        context = "\n\n".join(
            f"<passage id=\"{hit.chunk.chunk_id}\" document=\"{hit.chunk.document_name}\" "
            f"page=\"{hit.chunk.page_number}\">\n{hit.chunk.chunk_text}\n</passage>"
            for hit in hits
        )
        prompt = f"""You are an enterprise knowledge assistant.
Answer the question using only the supplied passages. Do not use outside knowledge.
If the passages do not support an answer, reply exactly: {REFUSAL_TEXT}
Keep every factual claim directly supported. Do not create citations; the system adds verified citations later.

Question: {question}

Passages:
{context}
"""
        message = self._load().invoke(prompt)
        content = message.content if isinstance(message.content, str) else str(message.content)
        usage = getattr(message, "usage_metadata", None) or getattr(message, "response_metadata", {}).get("token_usage", {})
        prompt_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        completion_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        cost = (
            prompt_tokens * self.settings.input_cost_per_million_tokens
            + completion_tokens * self.settings.output_cost_per_million_tokens
        ) / 1_000_000
        return GenerationResult(
            text=content.strip(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost,
            provider=self.provider,
            model_name=self.model_name,
        )


class AnswerGenerator:
    """Provider gateway that falls back to a grounded extractive answer."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.extractive = ExtractiveAnswerGenerator(settings.max_answer_sentences)
        self.remote = None if settings.llm_provider == "extractive" else LangChainAnswerGenerator(settings)

    def generate(self, question: str, hits: Sequence[RetrievalHit]) -> GenerationResult:
        if not hits:
            return self.extractive.generate(question, hits)
        if self.remote is None:
            return self.extractive.generate(question, hits)
        try:
            return self.remote.generate(question, hits)
        except Exception as exc:
            logger.warning(
                "llm_generation_fallback",
                extra={"provider": self.settings.llm_provider, "reason": str(exc)},
            )
            return self.extractive.generate(question, hits)

