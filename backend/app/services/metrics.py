from __future__ import annotations

import threading
from collections import Counter
from typing import Any

from ..db import Database


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Counter[str] = Counter()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def snapshot(self, database: Database, *, components: dict[str, Any] | None = None) -> dict[str, Any]:
        persisted = database.operational_metrics()
        with self._lock:
            runtime = dict(self._counters)
        return {
            **persisted,
            "runtime": runtime,
            "components": components or {},
        }

