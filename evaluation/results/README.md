# Evaluation results

This directory intentionally contains no fabricated benchmark scores. A measured run creates a timestamped subdirectory containing:

- `predictions.jsonl`: immutable adapter outputs used for scoring;
- `per_question_metrics.jsonl`: deterministic item-level measurements;
- `metrics.json`: aggregate and category-slice metrics plus provenance;
- `experiment_comparison.csv` and `report.md`: A-D comparison;
- `improvements.csv`: raw deltas and direction-aware improvements;
- `human_review_sample.csv`: a stratified review sheet.

The runner also refreshes `evaluation/results/latest.json` and `evaluation/results/latest/metrics.json` as stable dashboard/API discovery paths. The timestamped source run remains unchanged, and its run ID and corpus SHA-256 fingerprint are embedded in the report metadata.

Run all 248 benchmark questions against a live API:

```bash
python scripts/run_evaluation.py --adapter http --base-url http://localhost:8000
```

Regenerate the exact report from captured output without model calls:

```bash
python scripts/run_evaluation.py --adapter replay --replay evaluation/results/<run>/predictions.jsonl
```

`N/A` means the backend did not expose the field needed for that metric. Values are never imputed.
