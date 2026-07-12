"""Machine-readable, CSV, Markdown, and human-review report generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .metrics import aggregate_metrics


TABLE_COLUMNS = (
    ("System", "display_name"),
    ("Recall@5", "recall_at_5"),
    ("MRR", "mrr"),
    ("Correctness", "answer_correctness"),
    ("Faithfulness", "faithfulness"),
    ("Citation Precision", "citation_precision"),
    ("Hallucination Rate", "hallucination"),
    ("Latency (ms)", "total_latency_ms"),
)
LOWER_IS_BETTER = {"hallucination", "unsupported_claim_rate", "total_latency_ms", "retrieval_latency_ms", "estimated_cost_usd", "errors"}


def _format(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def compute_improvements(summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    improvements: list[dict[str, Any]] = []
    metric_names = [key for _, key in TABLE_COLUMNS if key != "display_name"] + [
        "recall_at_3", "recall_at_10", "precision_at_5", "ndcg_at_10", "citation_coverage",
        "citation_recall", "refusal_correct", "unsupported_claim_rate", "retrieval_latency_ms", "estimated_cost_usd",
    ]
    for previous, current in zip(summaries, summaries[1:]):
        for metric in metric_names:
            baseline, candidate = previous.get(metric), current.get(metric)
            if baseline is None or candidate is None:
                delta = relative = improvement = None
            else:
                delta = float(candidate) - float(baseline)
                relative = delta / abs(float(baseline)) * 100 if float(baseline) != 0 else None
                improvement = -delta if metric in LOWER_IS_BETTER else delta
            improvements.append({
                "from_experiment": previous["experiment_id"], "to_experiment": current["experiment_id"],
                "metric": metric, "baseline": baseline, "candidate": candidate, "delta": delta,
                "relative_change_percent": relative, "improvement": improvement,
                "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
            })
    return improvements


def build_report(
    *,
    experiment_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    experiments: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    summaries = []
    by_id = {experiment["id"]: experiment for experiment in experiments}
    category_summaries: dict[str, dict[str, Any]] = {}
    for experiment_id, rows in experiment_rows.items():
        summary = aggregate_metrics(rows)
        summary.update({
            "experiment_id": experiment_id,
            "display_name": by_id[experiment_id].get("display_name", experiment_id),
            "pipeline": by_id[experiment_id].get("pipeline", {}),
        })
        summaries.append(summary)
        categories = sorted({str(row.get("category", "unspecified")) for row in rows})
        category_summaries[experiment_id] = {
            category: aggregate_metrics([row for row in rows if row.get("category") == category])
            for category in categories
        }
    return {
        "report_schema_version": "1.0",
        "status": "COMPLETED",
        "metadata": dict(metadata),
        "metric_notes": {
            "answer_correctness": "For answerable items: mean of token F1 and expected-keyword coverage; for unanswerable items: correct refusal indicator.",
            "faithfulness": "Fraction of answer claims whose content-token coverage is >=0.55 in one retrieved passage, with exact numeric consistency required.",
            "retrieval_relevance": "First retrieved chunk for each ground-truth document/page target is relevant; duplicate chunks from the same target are not counted twice.",
            "citation_precision": "Citation document/page/chunk must match a retrieved passage and quoted evidence must match that passage.",
            "hallucination": "Query-level indicator: an unanswerable query was answered, or a non-refusal answer contained at least one unsupported claim.",
            "missing_values": "N/A/null means the adapter did not expose the required evidence, latency, token, cost, citation, or validation field; no value is imputed.",
        },
        "experiments": summaries,
        "category_summaries": category_summaries,
        "improvements": compute_improvements(summaries),
    }


def write_reports(report: Mapping[str, Any], output_dir: str | Path) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    summaries = report["experiments"]
    fieldnames = ["experiment_id", "display_name"] + sorted({key for row in summaries for key in row if key not in {"experiment_id", "display_name", "pipeline", "validation_status_counts"}})
    with (destination / "experiment_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)
    with (destination / "improvements.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["from_experiment", "to_experiment", "metric", "baseline", "candidate", "delta", "relative_change_percent", "improvement", "direction"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["improvements"])

    headers = [label for label, _ in TABLE_COLUMNS]
    markdown = ["# Measured experiment results", "", "These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.", "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for summary in summaries:
        markdown.append("| " + " | ".join(_format(summary.get(key)) for _, key in TABLE_COLUMNS) + " |")
    markdown.extend(["", "## Sequential improvements", "", "Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.", "", "| From | To | Metric | Delta | Relative change | Improvement |", "| --- | --- | --- | ---: | ---: | ---: |"])
    for row in report["improvements"]:
        markdown.append(f"| {row['from_experiment']} | {row['to_experiment']} | {row['metric']} | {_format(row['delta'])} | {_format(row['relative_change_percent'])} | {_format(row['improvement'])} |")
    (destination / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def write_human_review_sample(rows: Sequence[Mapping[str, Any]], path: str | Path, limit: int = 30) -> None:
    def risk_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            row.get("answer_correctness") if row.get("answer_correctness") is not None else 2.0,
            -(row.get("unsupported_claim_rate") or 0.0),
            str(row.get("item_id", "")),
        )

    # Deterministic round-robin sampling covers every experiment/category
    # stratum before adding a second row from any stratum. Within a stratum,
    # lower-correctness and higher-unsupported-claim cases are reviewed first.
    strata: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("experiment_id", "")), str(row.get("category", "unspecified")))
        strata.setdefault(key, []).append(row)
    for values in strata.values():
        values.sort(key=risk_key)

    ranked: list[Mapping[str, Any]] = []
    depth = 0
    while len(ranked) < limit:
        added = False
        for key in sorted(strata):
            values = strata[key]
            if depth < len(values):
                ranked.append(values[depth])
                added = True
                if len(ranked) >= limit:
                    break
        if not added:
            break
        depth += 1
    fields = [
        "experiment_id", "item_id", "category", "question", "expected_answer", "answer",
        "answer_correctness", "faithfulness", "citation_precision", "validation_status",
        "human_correctness_1_to_5", "human_faithfulness_1_to_5", "human_citation_valid", "reviewer_notes",
    ]
    destination = Path(path)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in ranked:
            writer.writerow({**row, "human_correctness_1_to_5": "", "human_faithfulness_1_to_5": "", "human_citation_valid": "", "reviewer_notes": ""})
