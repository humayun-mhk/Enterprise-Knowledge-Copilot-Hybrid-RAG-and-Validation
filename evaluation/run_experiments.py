"""Compatibility/config-driven entry point for CI and full evaluation runs.

Configuration files use JSON-compatible YAML, so the lightweight CI path needs
no PyYAML installation.  Full runs delegate to :mod:`evaluation.runner`.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .runner import main as runner_main


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Non-JSON YAML config requires the optional PyYAML package") from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError("Run config must be an object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--base-url", help="Override the full-run API URL")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help=(
            "Enable the configured deployment gate. The reference configs gate "
            "on evaluation errors only until an organization accepts quality thresholds."
        ),
    )
    args, passthrough = parser.parse_known_args(argv)
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    mode = config.get("mode", "evaluate")
    if mode == "validate_assets":
        from scripts.validate_evaluation_assets import validate

        summary = validate()
        minimum = int(config.get("minimum_questions", 240))
        if int(summary["benchmark_questions"]) < minimum:
            raise RuntimeError(f"Benchmark has fewer than {minimum} questions")
        print(json.dumps({"mode": mode, "config": str(config_path), **summary}, indent=2))
        return 0
    if mode != "evaluate":
        raise ValueError(f"Unknown run mode: {mode}")

    if config.get("temp_dir"):
        temp_dir = (ROOT / str(config["temp_dir"])).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        # Managed CI sandboxes may expose an OS temp path that exists but is not
        # writable. Set all conventional variables and the already-imported
        # tempfile module's cache before constructing an in-process adapter.
        for variable in ("TMP", "TEMP", "TMPDIR", "EVALUATION_TEMP_DIR"):
            os.environ.setdefault(variable, str(temp_dir))
        tempfile.tempdir = str(temp_dir)

    adapter = config.get("adapter", {})
    kind = str(adapter.get("kind", "http"))
    runner_args = [
        "--adapter", kind,
        "--dataset", str((ROOT / config.get("dataset", "data/benchmark/enterprise_qa_v1.jsonl")).resolve()),
        "--config", str((ROOT / config.get("experiments_config", "evaluation/configs/experiments.v1.json")).resolve()),
        "--output-dir", str((ROOT / config.get("output_dir", "evaluation/results")).resolve()),
    ]
    if kind == "http":
        base_url = args.base_url or os.getenv(str(adapter.get("base_url_env", "EVALUATION_BASE_URL"))) or adapter.get("base_url", "http://127.0.0.1:8000")
        runner_args.extend(["--base-url", str(base_url)])
    elif kind == "python":
        runner_args.extend(["--target", str(adapter["target"])])
    elif kind == "replay":
        replay = os.getenv(str(adapter.get("path_env", "EVALUATION_REPLAY_PATH"))) or adapter.get("path")
        if not replay:
            raise ValueError("Replay path is missing; set the configured environment variable")
        runner_args.extend(["--replay", str(replay)])
    if args.limit is not None:
        runner_args.extend(["--limit", str(args.limit)])
    for experiment in config.get("experiments", []):
        runner_args.extend(["--experiment", str(experiment)])
    if config.get("max_error_rate") is not None:
        runner_args.extend(["--max-error-rate", str(config["max_error_rate"])])
    if config.get("mlflow", False):
        runner_args.append("--mlflow")
    return runner_main(runner_args + passthrough)


if __name__ == "__main__":
    raise SystemExit(main())
