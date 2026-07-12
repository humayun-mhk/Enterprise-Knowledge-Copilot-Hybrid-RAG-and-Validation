"""Optional MLflow logging for completed, measured evaluation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def log_report_to_mlflow(
    report: Mapping[str, Any],
    artifacts_dir: str | Path,
    *,
    experiment_name: str = "enterprise-knowledge-copilot-evaluation",
    tracking_uri: str | None = None,
) -> str:
    try:
        import mlflow
    except ImportError as exc:
        raise RuntimeError("MLflow logging requested but mlflow is not installed") from exc
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    metadata = report.get("metadata", {})
    with mlflow.start_run(run_name=str(metadata.get("run_id", "evaluation"))) as parent:
        mlflow.log_params({
            "dataset_sha256": str(metadata.get("dataset_sha256", "")),
            "config_version": str(metadata.get("config_version", "")),
            "adapter": str(metadata.get("adapter", {}).get("adapter", "")),
            "question_count": int(metadata.get("question_count", 0)),
        })
        mlflow.log_dict(dict(report), "metrics.json")
        for summary in report.get("experiments", []):
            with mlflow.start_run(run_name=str(summary["experiment_id"]), nested=True):
                mlflow.log_params({
                    "experiment_id": summary["experiment_id"],
                    "display_name": summary["display_name"],
                    "pipeline": json.dumps(summary.get("pipeline", {}), sort_keys=True),
                })
                mlflow.log_metrics({
                    key: float(value)
                    for key, value in summary.items()
                    if isinstance(value, (int, float)) and value is not None and key not in {"queries"}
                })
                mlflow.log_metric("queries", int(summary.get("queries", 0)))
        mlflow.log_artifacts(str(Path(artifacts_dir)))
        return parent.info.run_id
