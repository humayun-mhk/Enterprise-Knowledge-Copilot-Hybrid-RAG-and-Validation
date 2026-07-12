"""Dataset and configuration loading with schema-level validation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schemas import BenchmarkItem


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_benchmark(path: str | Path) -> list[BenchmarkItem]:
    source = Path(path)
    records: list[Mapping[str, Any]] = []
    if source.suffix.casefold() == ".jsonl":
        with source.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {source}:{line_number}: {exc}") from exc
                if not isinstance(value, Mapping):
                    raise ValueError(f"Expected an object at {source}:{line_number}")
                records.append(value)
    elif source.suffix.casefold() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            records.extend(csv.DictReader(handle))
    else:
        raise ValueError("Benchmark must be JSONL or CSV")

    items = [BenchmarkItem.from_mapping(record) for record in records]
    duplicate_ids = {item.item_id for item in items if sum(other.item_id == item.item_id for other in items) > 1}
    if duplicate_ids:
        raise ValueError(f"Duplicate benchmark IDs: {sorted(duplicate_ids)[:5]}")
    for item in items:
        if not item.item_id or not item.question:
            raise ValueError("Every benchmark item requires an id and question")
        if item.answerable and not item.relevant_targets:
            raise ValueError(f"Answerable item {item.item_id} has no expected document/page target")
    return items


def load_experiment_config(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("experiments"), list):
        raise ValueError("Experiment config must contain an experiments array")
    ids = [experiment.get("id") for experiment in value["experiments"]]
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("Experiment IDs must be present and unique")
    return value


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

