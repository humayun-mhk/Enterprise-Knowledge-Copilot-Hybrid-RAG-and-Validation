# Operations guide

## Runtime modes

The default `.env.example` uses deterministic extractive generation and local embeddings so the project can be demonstrated without sending internal text to a third party. Provider adapters can be enabled with environment variables. For sensitive deployments, use a secrets manager instead of an `.env` file.

## Health and observability

`GET /health` is intended for container health checks. `GET /metrics` returns application-level aggregates for the dashboard. Structured logs include request and trace identifiers, duration, experiment, validation verdict, citation count, and error category; passage text and secrets should not be logged.

Operational alerts should cover:

- elevated API error rate;
- p95 query or retrieval latency regression;
- validator failure rate;
- rising insufficient-evidence or low-confidence rate;
- falling citation coverage;
- ingestion failures and index/document count mismatch;
- model token or estimated-cost anomalies.

## Model and prompt changes

Every evaluation records the generator model, embedding model, reranker model, prompt versions, chunking settings, retrieval top-K values, and fusion parameters. Change prompt/model versions explicitly; do not overwrite identifiers in place. Run the A-D benchmark before promotion.

## Backup and recovery

Back up the Chroma directory, metadata database, raw source registry, evaluation results, and MLflow artifacts together. After restoring, rebuild BM25 from stored chunks and run a known-answer smoke suite. Raw user uploads may be retained or deleted according to organizational policy, but the index must never outlive required deletion semantics.

## Scaling path

For larger deployments, move upload parsing and embedding into queued workers, use object storage for documents, replace the local metadata database with PostgreSQL, shard collections by tenant/security boundary, cache query embeddings, and autoscale generation separately from retrieval. Keep the API schemas and evaluator unchanged so before/after performance remains comparable.

## Security checklist

- Authenticate every endpoint and authorize document collections per user/group.
- Validate MIME type and file signature; enforce upload and decompression limits.
- Malware-scan uploads and render HTML without active content.
- Encrypt traffic, databases, vector storage, backups, and model-provider connections.
- Defend prompts against instructions embedded in retrieved documents; source text is data, not system policy.
- Apply deletion requests to raw files, metadata, embeddings, BM25 state, caches, and backups.
- Rate-limit expensive endpoints and cap model tokens/retries.
- Redact document contents, questions, and model credentials from telemetry.

