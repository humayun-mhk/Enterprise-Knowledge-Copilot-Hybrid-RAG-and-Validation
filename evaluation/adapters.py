"""Adapters that isolate evaluation from the production backend implementation."""

from __future__ import annotations

import importlib
import inspect
import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping

from .schemas import BenchmarkItem, QueryResult


class EvaluationAdapter(ABC):
    """A synchronous adapter; each call must return the observable pipeline output."""

    name = "unknown"

    @abstractmethod
    def query(self, item: BenchmarkItem, experiment: Mapping[str, Any]) -> QueryResult:
        raise NotImplementedError

    def metadata(self) -> Mapping[str, Any]:
        return {"adapter": self.name}


class HttpAdapter(EvaluationAdapter):
    """Call a running FastAPI deployment using only the standard library.

    The request contains both a concise experiment ID and its explicit retrieval
    configuration.  A backend may ignore the latter, but it should echo its
    effective configuration in response metadata for reproducibility.
    """

    name = "http"

    def __init__(self, base_url: str, timeout_seconds: float = 120.0, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key

    def query(self, item: BenchmarkItem, experiment: Mapping[str, Any]) -> QueryResult:
        payload = {
            "question": item.question,
            "experiment": experiment["id"],
            "top_k": int(experiment.get("top_k", 10)),
            "include_evidence": True,
        }
        request = urllib.request.Request(
            f"{self.base_url}/query",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
            result = QueryResult.from_mapping(decoded)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            result = QueryResult(answer="", error=f"{type(exc).__name__}: {exc}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        if result.total_latency_ms is None:
            result.total_latency_ms = elapsed_ms
        return result

    def metadata(self) -> Mapping[str, Any]:
        return {"adapter": self.name, "base_url": self.base_url, "timeout_seconds": self.timeout_seconds}


class PythonAdapter(EvaluationAdapter):
    """Load ``module:attribute`` for in-process evaluation.

    The target can be (a) an object with ``query(item, experiment)``, (b) a
    function with that signature, or (c) a zero-argument factory returning either.
    Return values may be ``QueryResult`` or a JSON-compatible mapping.
    """

    name = "python"

    def __init__(self, target: str):
        if ":" not in target:
            raise ValueError("Python adapter target must use module:attribute syntax")
        module_name, attribute_name = target.split(":", 1)
        attribute = getattr(importlib.import_module(module_name), attribute_name)
        self.target_name = target
        self._callable: Any = attribute
        if isinstance(attribute, type):
            self._callable = attribute()
        elif callable(attribute):
            is_named_factory = attribute_name.startswith(("create_", "build_"))
            if getattr(attribute, "__evaluation_factory__", False) or (
                is_named_factory and not any(
                    parameter.default is inspect.Parameter.empty
                    and parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    for parameter in inspect.signature(attribute).parameters.values()
                )
            ):
                self._callable = attribute()

    def query(self, item: BenchmarkItem, experiment: Mapping[str, Any]) -> QueryResult:
        start = time.perf_counter()
        try:
            if hasattr(self._callable, "query"):
                value = self._callable.query(item, experiment)
            else:
                value = self._callable(item, experiment)
            result = value if isinstance(value, QueryResult) else QueryResult.from_mapping(value)
        except Exception as exc:  # Adapter errors are captured per item so a long run can finish.
            result = QueryResult(answer="", error=f"{type(exc).__name__}: {exc}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        if result.total_latency_ms is None:
            result.total_latency_ms = elapsed_ms
        return result

    def metadata(self) -> Mapping[str, Any]:
        extra = self._callable.metadata() if hasattr(self._callable, "metadata") else {}
        return {"adapter": self.name, "target": self.target_name, **dict(extra)}


class ReplayAdapter(EvaluationAdapter):
    """Evaluate previously captured outputs without calling a model again.

    Each JSONL record must contain ``experiment_id``, ``item_id`` and either a
    ``result`` object or the response fields at top level.  This is useful for
    reproducible report regeneration and human-review workflows.
    """

    name = "replay"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records: dict[tuple[str, str], Mapping[str, Any]] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                key = (str(value.get("experiment_id", "")), str(value.get("item_id", "")))
                if not all(key):
                    raise ValueError(f"Replay line {line_number} lacks experiment_id or item_id")
                self.records[key] = value.get("result", value)

    def query(self, item: BenchmarkItem, experiment: Mapping[str, Any]) -> QueryResult:
        key = (str(experiment["id"]), item.item_id)
        if key not in self.records:
            return QueryResult(answer="", error=f"Missing replay record for {key[0]}/{key[1]}")
        return QueryResult.from_mapping(self.records[key])

    def metadata(self) -> Mapping[str, Any]:
        return {"adapter": self.name, "path": str(self.path), "records": len(self.records)}


def build_adapter(kind: str, *, base_url: str | None = None, target: str | None = None, replay: str | None = None, timeout: float = 120.0, api_key: str | None = None) -> EvaluationAdapter:
    if kind == "http":
        if not base_url:
            raise ValueError("--base-url is required for the HTTP adapter")
        return HttpAdapter(base_url, timeout_seconds=timeout, api_key=api_key)
    if kind == "python":
        if not target:
            raise ValueError("--target is required for the Python adapter")
        return PythonAdapter(target)
    if kind == "replay":
        if not replay:
            raise ValueError("--replay is required for the replay adapter")
        return ReplayAdapter(replay)
    raise ValueError(f"Unknown adapter: {kind}")
