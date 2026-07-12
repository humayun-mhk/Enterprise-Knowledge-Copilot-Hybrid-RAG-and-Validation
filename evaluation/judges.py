"""Optional LLM-as-judge support kept separate from deterministic metrics."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
from typing import Any, Mapping, Protocol

from .schemas import BenchmarkItem, QueryResult


JUDGE_SYSTEM_PROMPT = """You are evaluating an enterprise RAG response. Use only the supplied expected answer and retrieved passages. Score correctness, faithfulness, and answer relevance from 0.0 to 1.0. Do not reward fluent unsupported content. Return JSON only with numeric keys correctness, faithfulness, relevance and a short reason."""


class Judge(Protocol):
    name: str

    def evaluate(self, item: BenchmarkItem, result: QueryResult) -> Mapping[str, Any]: ...


class OpenAIJudge:
    """Optional OpenAI JSON judge; requires the ``openai`` package and API key."""

    name = "openai"

    def __init__(self, model: str, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the optional 'openai' package to enable --judge openai") from exc
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def evaluate(self, item: BenchmarkItem, result: QueryResult) -> Mapping[str, Any]:
        contexts = [
            {"document": passage.document, "page": passage.page, "text": passage.text}
            for passage in result.retrieved_passages
        ]
        prompt = json.dumps({
            "question": item.question,
            "answerable": item.answerable,
            "expected_answer": item.expected_answer,
            "assistant_answer": result.answer,
            "retrieved_passages": contexts,
            "citations": [citation.__dict__ for citation in result.citations],
        }, ensure_ascii=False)
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        value = json.loads(completion.choices[0].message.content)
        return {
            "llm_correctness": _unit(value.get("correctness")),
            "llm_faithfulness": _unit(value.get("faithfulness")),
            "llm_relevance": _unit(value.get("relevance")),
            "llm_judge_reason": str(value.get("reason", "")),
            "llm_judge_model": self.model,
        }


class CustomJudge:
    """Load a RAGAS, DeepEval, or organization-specific hook via module:attribute."""

    name = "custom"

    def __init__(self, target: str):
        module_name, attribute_name = target.split(":", 1)
        loaded = getattr(importlib.import_module(module_name), attribute_name)
        self.hook = loaded() if isinstance(loaded, type) else loaded
        self.target = target

    def evaluate(self, item: BenchmarkItem, result: QueryResult) -> Mapping[str, Any]:
        value = self.hook.evaluate(item, result) if hasattr(self.hook, "evaluate") else self.hook(item, result)
        if not isinstance(value, Mapping):
            raise TypeError("Custom judge must return a mapping")
        return value


def _unit(value: Any) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise ValueError(f"Judge score outside [0, 1]: {number}")
    return number


def optional_integration_versions() -> dict[str, str | None]:
    """Record availability without importing heavyweight optional packages."""
    versions: dict[str, str | None] = {}
    for package in ("ragas", "deepeval", "mlflow", "openai"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def build_judge(kind: str, *, model: str | None = None, target: str | None = None) -> Judge | None:
    if kind == "none":
        return None
    if kind == "openai":
        if not model:
            raise ValueError("--judge-model is required when --judge openai")
        return OpenAIJudge(model)
    if kind == "custom":
        if not target or ":" not in target:
            raise ValueError("--judge-target module:attribute is required for a custom judge")
        return CustomJudge(target)
    raise ValueError(f"Unknown judge kind: {kind}")
