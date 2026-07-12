"""Run experiments A-D and persist every prediction used to compute a report."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .adapters import build_adapter
from .io_utils import file_sha256, load_benchmark, load_experiment_config, write_jsonl
from .judges import build_judge, optional_integration_versions
from .metrics import evaluate_item
from .mlflow_tracking import log_report_to_mlflow
from .reporting import build_report, write_human_review_sample, write_reports


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "benchmark" / "enterprise_qa_v1.jsonl"
DEFAULT_CONFIG = ROOT / "evaluation" / "configs" / "experiments.v1.json"
DEFAULT_RESULTS = ROOT / "evaluation" / "results"
DEFAULT_CORPUS_MANIFEST = ROOT / "data" / "ground_truth" / "corpus_manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_run_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value)


def atomic_copy(source: Path, destination: Path) -> None:
    """Copy through a same-directory temporary file then atomically replace."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def run(args: argparse.Namespace) -> Path:
    dataset_path = Path(args.dataset).resolve()
    config_path = Path(args.config).resolve()
    items = load_benchmark(dataset_path)
    if args.category:
        allowed = set(args.category)
        items = [item for item in items if item.category in allowed]
    if args.limit is not None:
        items = items[: args.limit]
    if not items:
        raise ValueError("No benchmark items remain after filtering")

    config = load_experiment_config(config_path)
    selected_ids = set(args.experiment or [])
    shared_config = dict(config.get("shared", {}))
    experiments = [
        {
            **experiment,
            "shared": shared_config,
            "top_k": int(shared_config.get("final_k", 10)),
        }
        for experiment in config["experiments"]
        if not selected_ids or experiment["id"] in selected_ids
    ]
    missing_ids = selected_ids - {experiment["id"] for experiment in experiments}
    if missing_ids:
        raise ValueError(f"Unknown experiment IDs: {sorted(missing_ids)}")
    adapter = build_adapter(
        args.adapter,
        base_url=args.base_url,
        target=args.target,
        replay=args.replay,
        timeout=args.timeout,
        api_key=os.getenv(args.api_key_env) if args.api_key_env else None,
    )
    judge = build_judge(args.judge, model=args.judge_model, target=args.judge_target)
    started_at = utc_now()
    generated_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.adapter}"
    run_id = safe_run_id(args.run_id or generated_run_id)
    output_dir = Path(args.output_dir).resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    rows_by_experiment: dict[str, list[dict[str, Any]]] = {}
    prediction_records: list[dict[str, Any]] = []
    for experiment in experiments:
        experiment_id = str(experiment["id"])
        rows: list[dict[str, Any]] = []
        for position, item in enumerate(items, start=1):
            result = adapter.query(item, experiment)
            metrics = evaluate_item(item, result)
            if judge is not None and not result.error:
                try:
                    metrics.update(judge.evaluate(item, result))
                except Exception as exc:
                    metrics["llm_judge_error"] = f"{type(exc).__name__}: {exc}"
            row = {
                "experiment_id": experiment_id,
                "display_name": experiment.get("display_name", experiment_id),
                "item_id": item.item_id,
                "category": item.category,
                "answerable": item.answerable,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "expected_documents": list(item.expected_documents),
                "expected_pages": list(item.expected_pages),
                "answer": result.answer,
                **metrics,
            }
            rows.append(row)
            prediction_records.append({
                "experiment_id": experiment_id,
                "item_id": item.item_id,
                "position": position,
                "result": result.to_mapping(),
            })
            if args.progress_every and position % args.progress_every == 0:
                print(f"{experiment_id}: completed {position}/{len(items)}", file=sys.stderr)
        rows_by_experiment[experiment_id] = rows

    write_jsonl(output_dir / "predictions.jsonl", prediction_records)
    all_rows = [row for rows in rows_by_experiment.values() for row in rows]
    write_jsonl(output_dir / "per_question_metrics.jsonl", all_rows)
    metadata: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": utc_now(),
        "dataset": str(dataset_path),
        "dataset_sha256": file_sha256(dataset_path),
        "question_count": len(items),
        "categories": sorted({item.category for item in items}),
        "config": str(config_path),
        "config_sha256": file_sha256(config_path),
        "config_version": config.get("version"),
        "adapter": dict(adapter.metadata()),
        "judge": getattr(judge, "name", None),
        "optional_integrations": optional_integration_versions(),
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
    }
    observed_provenance: dict[str, list[dict[str, Any]]] = {}
    for record in prediction_records:
        provenance = record["result"].get("provenance") or {}
        if not provenance:
            continue
        experiment_id = str(record["experiment_id"])
        values = observed_provenance.setdefault(experiment_id, [])
        if provenance not in values:
            values.append(provenance)
    metadata["observed_provenance"] = observed_provenance
    corpus_manifest_path = Path(args.corpus_manifest).resolve()
    if corpus_manifest_path.is_file():
        corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
        metadata["corpus"] = {
            "manifest": str(corpus_manifest_path),
            "manifest_sha256": file_sha256(corpus_manifest_path),
            "document_count": corpus_manifest.get("document_count"),
            "page_count": corpus_manifest.get("page_count"),
            "document_sha256": {
                document.get("document_name"): document.get("sha256")
                for document in corpus_manifest.get("documents", [])
            },
        }
    errors = sum(bool(row.get("error")) for row in all_rows)
    error_rate = errors / len(all_rows) if all_rows else 0.0
    gate_failed = args.max_error_rate is not None and error_rate > args.max_error_rate
    report = build_report(experiment_rows=rows_by_experiment, experiments=experiments, metadata=metadata)
    if gate_failed:
        report["status"] = "FAILED"
        report["metadata"]["gate_failure"] = {
            "metric": "error_rate",
            "actual": error_rate,
            "maximum": args.max_error_rate,
        }
    write_reports(report, output_dir)
    write_human_review_sample(all_rows, output_dir / "human_review_sample.csv", limit=args.human_review_sample)
    if not gate_failed:
        # The run directory is immutable. Only a run that passes configured
        # gates may replace the API/dashboard discovery contract.
        latest_dir = Path(args.output_dir).resolve() / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("metrics.json", "report.md", "experiment_comparison.csv", "improvements.csv"):
            atomic_copy(output_dir / filename, latest_dir / filename)
        atomic_copy(output_dir / "metrics.json", Path(args.output_dir).resolve() / "latest.json")
    if args.mlflow and not gate_failed:
        mlflow_run_id = log_report_to_mlflow(
            report,
            output_dir,
            experiment_name=args.mlflow_experiment,
            tracking_uri=args.mlflow_tracking_uri,
        )
        (output_dir / "mlflow_run_id.txt").write_text(mlflow_run_id + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "output_dir": str(output_dir), "predictions": len(all_rows), "errors": errors, "error_rate": error_rate}, indent=2))
    if gate_failed:
        raise RuntimeError(f"Evaluation error rate {error_rate:.2%} exceeds {args.max_error_rate:.2%}")
    return output_dir


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--dataset", default=str(DEFAULT_DATASET))
    value.add_argument("--config", default=str(DEFAULT_CONFIG))
    value.add_argument("--corpus-manifest", default=str(DEFAULT_CORPUS_MANIFEST))
    value.add_argument("--output-dir", default=str(DEFAULT_RESULTS))
    value.add_argument("--run-id")
    value.add_argument("--adapter", choices=("http", "python", "replay"), required=True)
    value.add_argument("--base-url", help="FastAPI base URL for --adapter http")
    value.add_argument("--target", help="module:attribute for --adapter python")
    value.add_argument("--replay", help="Captured JSONL for --adapter replay")
    value.add_argument("--timeout", type=float, default=120.0)
    value.add_argument("--api-key-env", default="COPILOT_API_KEY", help="Environment variable read for HTTP bearer authentication")
    value.add_argument("--experiment", action="append", choices=("A", "B", "C", "D"), help="Repeat to select experiments; default is all")
    value.add_argument("--category", action="append", help="Repeat to select benchmark categories")
    value.add_argument("--limit", type=int, help="Deterministic prefix limit for smoke runs")
    value.add_argument("--progress-every", type=int, default=25)
    value.add_argument("--judge", choices=("none", "openai", "custom"), default="none")
    value.add_argument("--judge-model")
    value.add_argument("--judge-target", help="module:attribute for a RAGAS, DeepEval, or custom judge hook")
    value.add_argument("--human-review-sample", type=int, default=30)
    value.add_argument("--mlflow", action="store_true")
    value.add_argument("--mlflow-tracking-uri")
    value.add_argument("--mlflow-experiment", default="enterprise-knowledge-copilot-evaluation")
    value.add_argument("--max-error-rate", type=float)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
