# Evaluation system

This package measures the four controlled pipeline ablations defined in `configs/experiments.v1.json`. It keeps inference separate from scoring, records every raw output, and never substitutes guessed metrics for missing telemetry.

## Commands

API-free CI checks:

```bash
python -m evaluation.run_experiments --config evaluation/configs/ci.yaml
python scripts/validate_benchmark.py
python -m pytest evaluation/tests -q
```

Full A-D run against FastAPI:

```bash
EVALUATION_BASE_URL=http://localhost:8000 \
python -m evaluation.run_experiments --config evaluation/configs/full.yaml
```

Reproducible offline run through the backend's in-process adapter (no API key or model download):

```bash
python -m evaluation.run_experiments --config evaluation/configs/local.yaml
```

The local adapter's report metadata discloses its effective hash-embedding, in-memory store, BM25 implementation, reranker fallback, and extractive generator. Treat those measured scores as an offline engineering baseline, not as scores for a hosted embedding, cross-encoder, or generative model that was not actually executed.

Direct runner forms are available for an in-process backend or immutable replay:

```bash
python scripts/run_evaluation.py --adapter python --target my_package.evaluation:create_adapter
python scripts/run_evaluation.py --adapter replay --replay evaluation/results/<run>/predictions.jsonl
```

The HTTP adapter sends the production request contract: `question`, `experiment`, `top_k`, and `include_evidence`. A Python adapter receives `(BenchmarkItem, experiment_config)` and returns either `QueryResult` or a mapping shaped like the API response.

## Metric policy

Retrieval relevance is a ground-truth document/page pair. Only the first returned chunk from a relevant page counts, preventing duplicate chunks from inflating recall. The evaluator reports Recall@3/5/10, Precision@3/5/10, MRR, nDCG@3/5/10, and exposed retrieval latency.

Generation metrics combine deterministic answer/keyword matching, numeric-consistent claim support, refusal classification, citation-to-passage checks, and contextual ground truth. The exact formulas are embedded in each report under `metric_notes`. Human-review samples are always exported. `--judge openai --judge-model <model>` adds separate LLM-judge fields; `--judge custom --judge-target module:hook` supports RAGAS, DeepEval, or an internal evaluator without coupling the default CI path to those packages.

Token usage and estimated cost are aggregated only when returned by the backend. MLflow logging is opt-in with `--mlflow`; a missing package or tracking service fails explicitly rather than silently dropping the run.

## File map

- `schemas.py` normalizes benchmark, passage, citation, and API response shapes.
- `adapters.py` provides HTTP, Python, and replay inference adapters.
- `metrics.py` implements deterministic per-question and aggregate metrics.
- `judges.py` contains optional OpenAI/custom judge hooks and dependency provenance.
- `reporting.py` writes JSON, CSV, Markdown, improvement deltas, and human-review sheets.
- `runner.py` orchestrates measured runs and captures predictions.
- `run_experiments.py` translates lightweight/full YAML configs into runner commands.
- `mlflow_tracking.py` logs completed measurements and artifacts when requested.
- `configs/experiments.v1.json` versions A-D retrieval and validation settings.
- `configs/ci.yaml` validates assets without models or credentials; `configs/local.yaml` runs the disclosed offline backend; `configs/full.yaml` runs the live service.
- `results/latest.json` and `results/latest/metrics.json` are stable API/dashboard paths; timestamped directories are immutable evidence for each run.
