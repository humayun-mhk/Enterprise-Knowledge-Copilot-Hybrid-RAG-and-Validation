# Contributing

Use Python 3.11+ and Node.js 20+. Create changes on a short-lived branch, keep provider calls out of unit tests, and add deterministic coverage for every retrieval, citation, or validation behavior change.

## Local checks

```bash
make setup
make lint
make test
python -m evaluation.run_experiments --config evaluation/configs/ci.yaml
```

If a change affects chunking, embeddings, retrieval, reranking, prompts, citations, or validation, run the complete A-D evaluation against an indexed service and attach the immutable report directory to the review. Never replace a missing metric with a guessed value.

## Data rules

Only fictional or appropriately authorized documents belong in this repository. Do not commit employee questions, proprietary passages, API keys, vector databases, raw model logs, or MLflow artifacts that may contain confidential content.

## Commit expectations

- Keep public schemas backward compatible or document the migration.
- Pin dependencies and explain model or prompt version changes.
- Preserve raw per-question evaluation artifacts for audited comparisons.
- Update the file guide when adding a new maintained file.

