# API reference

The interactive OpenAPI specification is available at `http://localhost:8000/docs` while the API is running. All request and response bodies use JSON except document upload and the server-sent event stream.

## Documents

### `POST /documents/upload`

Upload one or more PDF, DOCX, TXT, HTML, or HTM files as `multipart/form-data` using repeated `files` fields. Optional query parameter `auto_index=true` indexes new, non-duplicate files immediately. The endpoint also accepts a raw body when `x-filename` is supplied.

```bash
curl -F "files=@data/source_documents/Employee_Handbook_2026.pdf" \
  "http://localhost:8000/documents/upload?auto_index=true"
```

The response includes stable document metadata, duplicate state, indexing state, and per-file errors. Upload size is bounded by `MAX_UPLOAD_MB`; unsupported or empty files are rejected before indexing.

### `POST /documents/index`

```json
{
  "document_ids": ["document-uuid"],
  "force": false,
  "chunk_size": 900,
  "chunk_overlap": 150
}
```

Omit `document_ids` to index all pending uploads. `force` rebuilds the selected documents. Chunk size and overlap are validated and recorded with document metadata.

### `GET /documents`

Returns indexed and pending documents. Optional `status` filters the result.

## Query

### `POST /query`

```json
{
  "question": "How many annual leave days do full-time employees receive?",
  "experiment": "D",
  "top_k": 8,
  "include_evidence": true,
  "conversation_id": "optional-client-id"
}
```

`experiment` is one of `A`, `B`, `C`, or `D`. The production default is D. A successful D response has this shape:

```json
{
  "query_id": "uuid",
  "answer": "Full-time employees receive 20 paid annual leave days per calendar year. [Employee_Handbook_2026.pdf, Page 1]",
  "citations": [
    {
      "document": "Employee_Handbook_2026.pdf",
      "page": 1,
      "chunk_id": "chunk_leave_annual_days",
      "quoted_evidence": "Full-time employees receive 20 paid annual leave days per calendar year.",
      "section": "Annual Leave"
    }
  ],
  "validation": {
    "status": "APPROVED",
    "supported_claims": 1,
    "unsupported_claims": 0,
    "citation_coverage": 1.0,
    "citation_precision": 1.0,
    "corrected_answer": null,
    "reason": "All factual claims and citations were supported by the retrieved passages."
  },
  "confidence": 0.91,
  "experiment": "D",
  "route": "hybrid",
  "evidence": [],
  "timings": {},
  "token_usage": {},
  "model_provider": "extractive",
  "model_name": "deterministic-extractive-v1",
  "prompt_version": "grounded-answer-v1",
  "retrieval_config_version": "hybrid-rrf-v1"
}
```

The values above illustrate the contract, not an evaluation result. Runtime confidence, timings, answer, and citations are always computed from the current query.

### `POST /query/stream`

Accepts the same body and returns `text/event-stream`. Events are `metadata`, `token`, `citations`, `validation`, and `done`. The final `done` event contains the complete query response and is authoritative; clients should tolerate proxy coalescing and reconnect at the application level.

## Evaluation and operations

### `GET /health`

Reports database/index readiness and the effective vector, embedding, BM25, reranker, generator, and validator backends. This disclosure is important when an offline fallback is active.

### `GET /metrics`

Returns process counters and database aggregates used by the observability dashboard: queries, latency, validation/refusal states, low-confidence answers, citation coverage, tokens, cost, feedback, uploads, and errors.

### `GET /evaluation/results`

Returns recorded evaluation rows and the latest immutable A-D aggregate report. A pristine checkout reports `NOT_RUN`; it never substitutes placeholder scores.

## Feedback

### `POST /feedback`

```json
{
  "query_id": "query-uuid",
  "rating": 5,
  "helpful": true,
  "comment": "The cited policy answered the question.",
  "selected_citation_chunk_id": "chunk_leave_annual_days"
}
```

At least one of rating, helpful, comment, or selected citation should be supplied by clients. Feedback is linked to the query identifier without copying document passages into the feedback record.

