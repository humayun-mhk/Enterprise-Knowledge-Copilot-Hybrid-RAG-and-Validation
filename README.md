# Enterprise Knowledge Copilot

Hybrid RAG with citation verification for enterprise policy and knowledge documents.

This project is a production-style reference implementation of an internal knowledge assistant. It ingests enterprise documents, retrieves relevant evidence with dense and keyword retrieval, generates grounded answers, attaches page-level citations, validates the answer against retrieved passages, refuses unsupported questions, and measures whether each RAG upgrade improves the system.

The project includes a generated enterprise document corpus, a 248-question benchmark, a FastAPI backend, a React dashboard, Docker packaging, GitHub Actions, pytest coverage, deterministic evaluation scripts, and measured A-D experiment results. No performance numbers in this README are invented; the offline baseline metrics come from `evaluation/results/20260712T002710Z-python/metrics.json`, and the OpenAI nano metrics come from `evaluation/results/openai-nano-100-20260712T071454/metrics.json`.

## What This Builds

Enterprise Knowledge Copilot answers questions over internal documents such as policies, handbooks, runbooks, manuals, FAQs, and reports.

It supports:

- PDF, DOCX, TXT, and HTML ingestion.
- Metadata extraction with document id, name, page number, section, chunk text, checksum, and embedding metadata.
- Duplicate-document detection by SHA-256 checksum.
- Configurable chunking and chunk overlap.
- Dense vector retrieval.
- BM25 keyword retrieval with `rank_bm25`.
- Hybrid result fusion with weighted scoring or reciprocal-rank fusion.
- Reranking through a cross-encoder interface with an offline lexical fallback.
- Grounded answer generation.
- Citation generation with document name, page number, chunk id, and quoted evidence.
- LangGraph answer validation with `APPROVED`, `REVISE`, and `INSUFFICIENT_EVIDENCE` statuses.
- Refusal behavior when the indexed documents do not provide enough evidence.
- Experiment tracking, evaluation reports, structured logging, Docker, GitHub Actions, and user feedback collection.

## Architecture

```text
User Question
    |
    v
Query Preprocessing
    |
    v
Query Router
    |
    v
Hybrid Retrieval
    |-- Dense vector retrieval
    |-- BM25 keyword retrieval
    |
    v
Result Fusion
    |
    v
Cross-Encoder / Lexical Reranking
    |
    v
Answer Generator
    |
    v
Citation Generator
    |
    v
LangGraph Answer Validation Agent
    |-- Approve
    |-- Revise answer
    |-- Reject as insufficient evidence
    |
    v
Final Answer with Citations
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend API | Python, FastAPI, Pydantic |
| RAG orchestration | LangChain Core, LangGraph |
| Embeddings | Hash embeddings for offline baseline; configurable OpenAI, Ollama, Gemini-compatible providers |
| LLM generation | Deterministic extractive mode by default; configurable OpenAI, Claude, Gemini, or Ollama |
| Vector store | ChromaDB or in-memory store |
| Metadata store | SQLite in this reference implementation; environment-based configuration is isolated for production replacement |
| Sparse retrieval | `rank_bm25` |
| Reranker | Cross-encoder interface with `sentence-transformers`; offline lexical fallback used in the measured baseline |
| Frontend | React, Vite |
| MLOps | MLflow hooks, versioned retrieval configs, immutable reports, GitHub Actions |
| Testing | pytest, pytest-cov, Vitest, ESLint, Ruff, mypy |
| Packaging | Docker, Docker Compose, Nginx frontend proxy |

## Generated RAG Corpus

The repository includes generated enterprise documents created for this RAG project. They are stored in `data/source_documents/` and are safe to use as sample internal knowledge files.

| Document | Format | Pages | Purpose |
| --- | --- | ---: | --- |
| `Employee_Handbook_2026.pdf` | PDF | 4 | Leave, probation, performance, collaboration hours, time records |
| `Information_Security_Standard_2026.pdf` | PDF | 4 | Passwords, MFA, device encryption, phishing, vendor security |
| `Travel_and_Expense_Policy_2026.pdf` | PDF | 4 | Booking rules, hotel caps, meals, expense reports, preapproval |
| `Business_Continuity_Manual_2026.pdf` | PDF | 4 | RTO/RPO, incident activation, exercises, communications |
| `Procurement_and_Vendor_Standard_2026.docx` | DOCX | 4 | Quotes, RFP thresholds, vendor due diligence, contract authority |
| `Remote_Work_FAQ_2026.docx` | DOCX | 4 | Remote location, equipment, core hours, workspace security |
| `Benefits_Guide_2026.docx` | DOCX | 4 | Benefits enrollment, retirement match, wellness, parental leave |
| `Project_Governance_Playbook_2026.docx` | DOCX | 4 | Risk registers, steering approvals, status reports, closure |
| `Engineering_OnCall_Runbook_2026.txt` | TXT | 4 | Severity acknowledgements, escalation, post-incident reviews |
| `Facilities_Safety_Manual_2026.txt` | TXT | 4 | Fire alarms, visitors, incidents, weather closures |
| `Data_Retention_Schedule_2026.html` | HTML | 4 | Personnel, financial, support, legal hold retention |
| `Customer_Support_Playbook_2026.html` | HTML | 4 | Case response, escalations, refunds, customer documentation |

Corpus totals:

- Documents: 12
- Pages / canonical passages: 48
- Formats: 4 PDF, 4 DOCX, 2 TXT, 2 HTML
- Manifest: `data/ground_truth/corpus_manifest.json`
- Canonical passages: `data/ground_truth/canonical_passages.jsonl`

To regenerate the sample corpus:

```bash
python scripts/generate_enterprise_assets.py
python scripts/validate_evaluation_assets.py
```

## Benchmark Dataset

The benchmark is stored in:

- `data/benchmark/enterprise_qa_v1.jsonl`
- `data/benchmark/enterprise_qa_v1.csv`
- `data/benchmark/DATASHEET.md`

It contains 248 questions:

| Category | Count |
| --- | ---: |
| answerable | 18 |
| exact_policy | 78 |
| paraphrase | 96 |
| multi_document | 12 |
| ambiguous | 12 |
| adversarial | 16 |
| unanswerable | 16 |

Answerability split:

| Answerable | Count |
| --- | ---: |
| true | 213 |
| false | 35 |

Each benchmark row stores:

- `question`
- `expected_answer`
- `expected_document`
- `expected_page`
- `answerable`
- `expected_keywords`
- source passage and fact metadata where applicable

Validate the benchmark:

```bash
python scripts/validate_benchmark.py --minimum 200
```

## RAG Experiments

The controlled experiment definitions live in `evaluation/configs/experiments.v1.json`.

| Experiment | System | Dense | BM25 | Fusion | Reranker | Citations | Validator |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | Dense RAG | yes | no | none | no | no | no |
| B | Hybrid RAG | yes | yes | weighted score | no | no | no |
| C | Hybrid + Reranker | yes | yes | reciprocal-rank fusion | yes | no | no |
| D | Hybrid + Validator | yes | yes | reciprocal-rank fusion | yes | yes | yes |

Shared evaluation settings:

- Candidate pool: 20
- Final contexts: 10
- RRF `k`: 60
- Dense weight: 0.6
- BM25 weight: 0.4
- Temperature: 0.0
- Prompt version: `grounded-answer-v1`
- Retrieval config version: `retrieval-config-v1`

## Actual Evaluation Results

### Offline 248-Question Baseline

- Run id: `20260712T002710Z-python`
- Status: `COMPLETED`
- Adapter: in-process Python backend adapter
- Dataset: `data/benchmark/enterprise_qa_v1.jsonl`
- Questions: 248
- Predictions: 992
- Errors: 0
- Corpus indexed for evaluation: 48 canonical chunks
- Vector backend: memory
- Embedding provider: hash
- Embedding model: `feature-hash-384d-v1`
- BM25 backend: `rank_bm25`
- Reranker backend: `lexical-fallback`
- Generator: deterministic extractive
- LLM judge: not used
- RAGAS / DeepEval: not used in this measured run
- MLflow: optional integration available; not active in this measured run

Important: these are offline baseline results. They are not presented as OpenAI, Claude, Gemini, Ollama, Chroma production, or hosted cross-encoder numbers unless those components are actually enabled and a new report is generated.

#### Main Experiment Table

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 0.7355 | 0.6465 | 0.5847 | 1.0000 | 0.0000 | 0.0645 | 27.4901 |
| Hybrid RAG | 0.8498 | 0.7508 | 0.5645 | 1.0000 | 0.0000 | 0.0968 | 29.2533 |
| Hybrid + Reranker | 0.9139 | 0.7994 | 0.5974 | 1.0000 | 0.0000 | 0.0887 | 28.5126 |
| Hybrid + Validator | 0.9139 | 0.7994 | 0.5735 | 1.0000 | 0.9531 | 0.0887 | 39.8950 |

#### Retrieval Metrics

| System | Recall@3 | Recall@5 | Recall@10 | Precision@5 | MRR | nDCG@10 | Retrieval Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 0.7058 | 0.7355 | 0.8122 | 0.1549 | 0.6465 | 0.6835 | 23.4356 |
| Hybrid RAG | 0.8044 | 0.8498 | 0.9014 | 0.1793 | 0.7508 | 0.7847 | 24.9607 |
| Hybrid + Reranker | 0.8818 | 0.9139 | 0.9366 | 0.1934 | 0.7994 | 0.8322 | 24.8407 |
| Hybrid + Validator | 0.8818 | 0.9139 | 0.9366 | 0.1934 | 0.7994 | 0.8322 | 19.6086 |

#### Generation, Citation, and Refusal Metrics

| System | Answer Correctness | Answer Relevance | Faithfulness | Refusal Accuracy | Citation Coverage | Citation Precision | Citation Recall | Citation Misuse | Unsupported Claim Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 0.5847 | 0.4182 | 1.0000 | 0.8992 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Hybrid RAG | 0.5645 | 0.3509 | 1.0000 | 0.8871 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Hybrid + Reranker | 0.5974 | 0.4081 | 1.0000 | 0.8750 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Hybrid + Validator | 0.5735 | 0.4022 | 1.0000 | 0.8710 | 0.8020 | 0.9531 | 0.8271 | 0.0887 | 0.0000 |

#### Latency and Cost Metrics

| System | Base Retrieval ms | Reranking ms | Retrieval Total ms | Generation ms | Validation ms | Total Avg ms | p50 Total ms | p95 Total ms | Estimated Cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 23.4356 | 0.0000 | 23.4356 | 2.4816 | 0.0000 | 27.4901 | 25.3985 | 39.4927 | 0.0000 |
| Hybrid RAG | 24.9607 | 0.0000 | 24.9607 | 2.7702 | 0.0000 | 29.2533 | 27.5065 | 40.4717 | 0.0000 |
| Hybrid + Reranker | 22.5232 | 2.3175 | 24.8407 | 2.4333 | 0.0000 | 28.5126 | 27.8880 | 35.7114 | 0.0000 |
| Hybrid + Validator | 17.7857 | 1.8230 | 19.6086 | 1.8837 | 11.3408 | 39.8950 | 39.4605 | 57.6792 | 0.0000 |

Token usage is reported as `null` in the JSON report because the offline extractive generator does not consume paid LLM tokens. Cost is therefore `0.0` for this measured run.

#### Sequential Improvements

Positive improvement means the candidate system got better after applying the metric direction. For latency and hallucination, lower is better.

| Change | Recall@5 | MRR | Correctness | Citation Precision | Hallucination Improvement | Latency Improvement ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A to B | +0.1142 | +0.1043 | -0.0202 | +0.0000 | -0.0323 | -1.7632 |
| B to C | +0.0642 | +0.0486 | +0.0329 | +0.0000 | +0.0081 | +0.7407 |
| C to D | +0.0000 | +0.0000 | -0.0240 | +0.9531 | -0.0000 | -11.3824 |

Interpretation:

- Hybrid retrieval improved Recall@5 by 0.1142 over dense-only retrieval.
- RRF plus reranking improved Recall@5 by another 0.0642 and improved MRR by 0.0486 over basic hybrid retrieval.
- The validator did not change retrieval quality because it runs after retrieval.
- The validator added strong citation precision, measured at 0.9531.
- The validator increased total latency by 11.3824 ms in the offline baseline.
- Correctness decreased slightly in D because unsupported/ambiguous answers were revised or refused more conservatively.

### OpenAI Nano 100-Question Benchmark

This run used the OpenAI API after setting the environment to OpenAI. It is reported separately from the offline baseline because it used different model backends and only the first 100 benchmark questions.

- Run id: `openai-nano-100-20260712T071454`
- Report status: `FAILED`
- Reason for failed gate: one transient OpenAI connection/DNS error caused an error rate of `0.25%`; the configured gate required `0.00%`.
- Dataset slice: first 100 questions from `data/benchmark/enterprise_qa_v1.jsonl`
- Experiment rows: 400 total rows, 399 successful and 1 failed
- Failed item: experiment D, `qa_travel_rideshare_paraphrase`
- Error: `APIConnectionError: Connection error.`
- LLM provider: OpenAI
- LLM model: `gpt-4.1-nano`
- Embedding provider: OpenAI
- Embedding model: `text-embedding-3-small`
- Vector backend: memory
- BM25 backend: `rank_bm25`
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` for experiments C and D
- Validator: LangGraph in experiment D
- Total generation tokens reported by the application: `344,022`
- Reported generation cost estimate: `$0.036765`
- Note: embedding API charges are not included in the application `estimated_cost_usd` field.

#### OpenAI Main Experiment Table

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency ms | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 1.0000 | 0.9725 | 0.8103 | 0.8622 | 0.0000 | 0.1400 | 1194.7301 | 0 |
| Hybrid RAG | 1.0000 | 0.9458 | 0.7912 | 0.8807 | 0.0000 | 0.1200 | 1207.4839 | 0 |
| Hybrid + Reranker | 1.0000 | 0.9725 | 0.8139 | 0.8729 | 0.0000 | 0.1400 | 2025.3248 | 0 |
| Hybrid + Validator | 0.9900 | 0.9625 | 0.6953 | 0.9451 | 0.7980 | 0.0505 | 4883.1959 | 1 |

#### OpenAI Generation, Citation, and Refusal Metrics

| System | Answer Correctness | Answer Relevance | Faithfulness | Refusal Accuracy | Citation Coverage | Citation Precision | Citation Recall | Citation Misuse | Unsupported Claim Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 0.8103 | 0.7838 | 0.8622 | 0.9800 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1378 |
| Hybrid RAG | 0.7912 | 0.7671 | 0.8807 | 0.9500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1193 |
| Hybrid + Reranker | 0.8139 | 0.7826 | 0.8729 | 0.9700 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1271 |
| Hybrid + Validator | 0.6953 | 0.6764 | 0.9451 | 0.8000 | 0.9557 | 0.7980 | 0.7800 | 0.0000 | 0.0549 |

#### OpenAI Latency and Cost Metrics

| System | Base Retrieval ms | Reranking ms | Retrieval Total ms | Generation ms | Validation ms | Total Avg ms | p50 Total ms | p95 Total ms | Tokens | Est. Generation Cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense RAG | 472.5461 | 0.0000 | 472.5461 | 721.1835 | 0.0000 | 1194.7301 | 1166.2640 | 1438.4217 | 86,530 | 0.0092488 |
| Hybrid RAG | 497.2496 | 0.0000 | 497.2496 | 709.0966 | 0.0000 | 1207.4839 | 1128.2035 | 1609.4460 | 86,422 | 0.0092308 |
| Hybrid + Reranker | 502.8613 | 821.8065 | 1324.6678 | 699.6491 | 0.0000 | 2025.3248 | 1703.9100 | 2470.9216 | 86,431 | 0.0092458 |
| Hybrid + Validator | 364.5217 | 679.8699 | 1044.3915 | 3864.9065 | 6.2576 | 4883.1959 | 1640.3645 | 2510.7225 | 84,639 | 0.0090396 |

#### OpenAI Sequential Improvements

| Change | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Improvement | Latency Improvement ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A to B | +0.0000 | -0.0267 | -0.0191 | +0.0185 | +0.0000 | +0.0200 | -12.7538 |
| B to C | +0.0000 | +0.0267 | +0.0228 | -0.0078 | +0.0000 | -0.0200 | -817.8408 |
| C to D | -0.0100 | -0.0100 | -0.1187 | +0.0723 | +0.7980 | +0.0895 | -2857.8712 |

OpenAI run interpretation:

- On this 100-question slice, OpenAI embeddings made retrieval very strong: Recall@5 was `1.0000` for A, B, and C.
- The reranker improved MRR back to `0.9725` after the basic hybrid setup dropped to `0.9458`, but it also added latency.
- The validator improved faithfulness from `0.8729` to `0.9451`, reduced hallucination from `0.1400` to `0.0505`, and introduced citation precision of `0.7980`.
- The validator reduced correctness and refusal accuracy on this slice because it refused or constrained some answers more aggressively.
- The run should not be treated as a clean deployment gate pass because it had one OpenAI API connection error.

## Metric Definitions

Retrieval metrics:

- Recall@K: fraction of expected document/page targets retrieved in the top K.
- Precision@K: fraction of top K contexts that match expected targets.
- MRR: reciprocal rank of the first relevant context.
- nDCG: ranking quality with higher credit for relevant contexts appearing earlier.
- Retrieval latency: exposed retrieval time; for reranked systems it includes reranking time.

Generation and validation metrics:

- Answer correctness: deterministic score. For answerable questions, it averages token F1 and expected keyword coverage. For unanswerable questions, it checks whether the system refused.
- Faithfulness: fraction of answer claims supported by retrieved passages, with exact numeric consistency required.
- Answer relevance: token-level relevance for answerable questions or refusal correctness for unanswerable questions.
- Hallucination rate: query-level indicator for answering unanswerable questions or producing unsupported claims.
- Refusal accuracy: whether refusal behavior matches `answerable=false`.
- Citation coverage: ratio of citations to answer claims, capped at 1.0.
- Citation precision: citation document/page/chunk must match a retrieved passage, and quoted evidence must match the passage.
- Citation recall: fraction of expected document/page targets covered by citations.
- Citation misuse: citations emitted for unanswerable questions.
- Unsupported claim rate: fraction of factual claims not supported by retrieved passages.

## Answer Validation Agent

The validator is implemented as a LangGraph workflow in `backend/app/services/validator.py`.

It receives:

- user question
- generated answer
- retrieved passages
- generated citations

It performs:

- claim extraction
- support checking against retrieved evidence
- citation-to-passage verification
- contradiction and unsupported-claim detection
- answer revision when possible
- refusal when the documents do not contain enough support

Structured output shape:

```json
{
  "status": "REVISE",
  "supported_claims": 3,
  "unsupported_claims": 1,
  "citation_coverage": 0.75,
  "citation_precision": 0.67,
  "corrected_answer": "Corrected grounded answer...",
  "reason": "One claim was not supported by the retrieved passages.",
  "unsupported_details": [],
  "contradictory_claims": []
}
```

Measured validation statuses in Experiment D:

| Status | Count |
| --- | ---: |
| APPROVED | 184 |
| REVISE | 41 |
| INSUFFICIENT_EVIDENCE | 23 |

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/documents/upload` | Upload PDF, DOCX, TXT, or HTML documents |
| `POST` | `/documents/index` | Parse, chunk, embed, and index uploaded documents |
| `GET` | `/documents` | List uploaded documents and indexing status |
| `POST` | `/query` | Ask a question and receive answer, citations, evidence, validation, timings |
| `POST` | `/query/stream` | Stream answer tokens and final metadata with server-sent events |
| `GET` | `/metrics` | Operational counters and component health |
| `GET` | `/evaluation/results` | Latest measured evaluation report for the dashboard |
| `GET` | `/health` | Service health and component backends |
| `POST` | `/feedback` | Store user feedback for answer quality and citation usefulness |

Example query:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many annual leave days does the company allow?",
    "experiment": "D",
    "top_k": 5,
    "include_evidence": true
  }'
```

Abbreviated response shape:

```json
{
  "query_id": "uuid",
  "answer": "Employees receive 20 annual leave days per calendar year. [Employee_Handbook_2026.pdf, Page 1]",
  "citations": [
    {
      "document": "Employee_Handbook_2026.pdf",
      "page": 1,
      "chunk_id": "employee-handbook-2026-p001",
      "quoted_evidence": "Employees receive 20 annual leave days per calendar year."
    }
  ],
  "retrieved_passages": [],
  "validation": {
    "status": "APPROVED"
  }
}
```

The response example shows the contract shape. Full API responses also include evidence, confidence, timing, usage, cost, and provenance fields measured per request.

## React Dashboard

The frontend in `frontend/` provides:

- document upload interface
- knowledge-base document list
- chat interface
- citations panel
- retrieved evidence viewer
- confidence and validation status display
- evaluation dashboard
- experiment comparison table
- latency and cost metrics
- feedback controls

Frontend scripts:

```bash
cd frontend
npm ci
npm run dev
npm run lint
npm test
npm run build
```

## Local Development

Install backend and frontend dependencies:

```bash
python -m pip install -r backend/requirements-dev.txt
cd frontend
npm ci
cd ..
```

Start the API:

```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Start the React app:

```bash
cd frontend
npm run dev
```

Open:

- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

## Docker

Create an environment file:

```bash
cp .env.example .env
```

Start the full stack:

```bash
docker compose up --build
```

Services:

- FastAPI backend: `http://localhost:8000`
- React/Nginx frontend: `http://localhost:3000`
- MLflow server: `http://localhost:5000`

Docker Compose mounts:

- persistent app storage to `copilot-storage`
- MLflow storage to `mlflow-data`
- generated sample documents read-only at `/app/sample_documents`
- evaluation reports read-only at `/app/evaluation-results`

## Configuration

Key environment variables are documented in `.env.example`.

| Variable | Purpose |
| --- | --- |
| `VECTOR_STORE` / `VECTOR_BACKEND` | `chroma`, `memory`, or `auto` |
| `CHROMA_PERSIST_DIR` | Chroma persistence directory |
| `METADATA_DB_URL` / `DATABASE_URL` | SQLite metadata database URL |
| `UPLOAD_DIR` | Uploaded document storage path |
| `EMBEDDING_PROVIDER` | `hash`, `openai`, `ollama`, or Gemini-compatible provider |
| `EMBEDDING_MODEL` | Embedding model name |
| `LLM_PROVIDER` | `extractive`, `openai`, `anthropic`, `gemini`, or `ollama` |
| `LLM_MODEL` | Generation model name |
| `OPENAI_API_KEY` | OpenAI key when using OpenAI embeddings or LLMs |
| `ANTHROPIC_API_KEY` | Claude provider key |
| `GOOGLE_API_KEY` | Gemini provider key |
| `OLLAMA_BASE_URL` | Ollama host |
| `RERANKER_ENABLED` | Enables cross-encoder reranking |
| `RERANKER_MODEL` | Cross-encoder model name |
| `CHUNK_SIZE` | Chunk size for document splitting |
| `CHUNK_OVERLAP` | Chunk overlap |
| `MIN_EVIDENCE_SCORE` | Minimum score used for evidence acceptance |
| `MLFLOW_TRACKING_URI` | MLflow server or local file URI |
| `PROMPT_VERSION` | Answer prompt version |
| `VALIDATOR_PROMPT_VERSION` | Validator prompt version |

Default mode is offline and deterministic so the project can run without API keys.

## Evaluation Commands

Smoke evaluation:

```bash
python -m evaluation.run_experiments --config evaluation/configs/ci.yaml
```

Full local offline benchmark:

```bash
python -m evaluation.run_experiments --config evaluation/configs/local.yaml
```

Full benchmark against the running FastAPI service:

```bash
python -m evaluation.run_experiments --config evaluation/configs/full.yaml
```

Direct runner:

```bash
python scripts/run_evaluation.py \
  --adapter python \
  --target backend.app.evaluation_adapter:BackendEvaluationAdapter
```

Generated artifacts:

- `metrics.json`: full machine-readable report
- `report.md`: Markdown summary table and improvements
- `experiment_comparison.csv`: comparison table
- `improvements.csv`: sequential deltas
- `predictions.jsonl`: every captured answer and retrieved passage
- `per_question_metrics.jsonl`: question-level metrics
- `human_review_sample.csv`: stratified sample for human review

Stable paths:

- `evaluation/results/latest.json`
- `evaluation/results/latest/metrics.json`
- `evaluation/results/latest/report.md`

Immutable measured run used in this README:

- `evaluation/results/20260712T002710Z-python/`

## MLOps and Monitoring

MLOps features:

- versioned experiment config in `evaluation/configs/experiments.v1.json`
- versioned retrieval config metadata in API responses
- prompt versioning through environment variables
- immutable evaluation run directories
- stable latest report paths for dashboards
- MLflow logging hooks in `evaluation/mlflow_tracking.py`
- automated CI benchmark validation
- release workflow requiring full local evaluation before release image build
- Dockerized API, frontend, and MLflow

Runtime monitoring tracks:

- total queries
- answer latency
- retrieval latency
- validation failures
- insufficient-evidence responses
- low-confidence answers
- citation coverage
- user feedback
- token usage when model providers return it
- estimated cost when token usage and cost settings are available
- API errors
- indexed chunk count
- component backends

Operational endpoints:

- `/health`
- `/metrics`
- `/evaluation/results`

## CI/CD

GitHub Actions workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

CI checks:

- backend Ruff linting
- backend mypy type checking
- backend pytest with coverage threshold
- evaluation tests
- frontend ESLint
- frontend Vitest
- frontend production build
- benchmark schema and minimum-size validation
- Docker image builds
- deterministic evaluation gate

Release workflow:

- runs full A-D local evaluation
- uploads evaluation artifacts
- builds release images when manually requested

## Testing

Backend:

```bash
python -m pytest backend/tests -q
```

Evaluation:

```bash
python -m pytest evaluation/tests -q
```

Frontend:

```bash
cd frontend
npm test
```

All project tests:

```bash
make test
```

Linting:

```bash
make lint
```

## Project Structure and File Purposes

```text
.
|-- README.md
|-- .env.example
|-- .gitignore
|-- .dockerignore
|-- docker-compose.yml
|-- Makefile
|-- LICENSE
|-- CONTRIBUTING.md
|-- SECURITY.md
|-- mypy.ini
|-- .github/
|   `-- workflows/
|-- backend/
|-- frontend/
|-- data/
|-- evaluation/
|-- scripts/
`-- docs/
```

Root files:

| File | Purpose |
| --- | --- |
| `README.md` | Complete project guide, metrics, setup, and architecture |
| `.env.example` | Runtime configuration template |
| `.gitignore` | Ignores local caches, runtime storage, logs, node modules, and generated temp files |
| `.dockerignore` | Keeps Docker build contexts small |
| `docker-compose.yml` | Runs API, frontend, and MLflow |
| `Makefile` | Common setup, test, lint, data generation, evaluation, and Docker commands |
| `LICENSE` | Project license |
| `CONTRIBUTING.md` | Contributor workflow |
| `SECURITY.md` | Security notes, limitations, and reporting process |
| `mypy.ini` | Python type-checking configuration |

Backend files:

| File | Purpose |
| --- | --- |
| `backend/Dockerfile` | Backend container image |
| `backend/requirements.txt` | Runtime Python dependencies |
| `backend/requirements-dev.txt` | Development and test dependencies |
| `backend/pyproject.toml` | Ruff, pytest, and package tooling config |
| `backend/app/main.py` | FastAPI app, routes, middleware, health, metrics, query, upload, feedback |
| `backend/app/config.py` | Environment-driven settings |
| `backend/app/db.py` | SQLite metadata, documents, chunks, metrics, feedback, evaluation records |
| `backend/app/domain.py` | Domain records used by retrieval and indexing |
| `backend/app/schemas.py` | API request and response models |
| `backend/app/logging_config.py` | Structured logging setup |
| `backend/app/evaluation_adapter.py` | In-process backend adapter used by deterministic evaluation |
| `backend/app/services/container.py` | Service construction and dependency wiring |
| `backend/app/services/ingestion.py` | PDF, DOCX, TXT, HTML parsing, cleaning, chunking, metadata |
| `backend/app/services/indexing.py` | Document indexing, embedding generation, vector upsert, BM25 upsert |
| `backend/app/services/embeddings.py` | Hash/OpenAI/Ollama/Gemini-compatible embedding abstraction |
| `backend/app/services/vector_store.py` | Chroma and in-memory vector-store implementations |
| `backend/app/services/bm25.py` | BM25 keyword index |
| `backend/app/services/retrieval.py` | Query preprocessing, routing, dense/BM25 retrieval, fusion, reranking |
| `backend/app/services/reranker.py` | Cross-encoder reranker interface and lexical fallback |
| `backend/app/services/generation.py` | Grounded answer generation and deterministic extractive generator |
| `backend/app/services/citations.py` | Citation selection and quoted-evidence formatting |
| `backend/app/services/validator.py` | LangGraph answer validation agent |
| `backend/app/services/rag.py` | End-to-end RAG orchestration |
| `backend/app/services/metrics.py` | Runtime metrics registry |
| `backend/app/services/evaluation.py` | Evaluation-result persistence helpers |
| `backend/tests/*.py` | Backend unit, integration, API, retrieval, ingestion, validator, and corpus tests |

Frontend files:

| File | Purpose |
| --- | --- |
| `frontend/Dockerfile` | Frontend production image |
| `frontend/nginx.conf` | Nginx static hosting and `/api` proxy |
| `frontend/package.json` | React/Vite scripts and dependencies |
| `frontend/package-lock.json` | Locked npm dependency graph |
| `frontend/vite.config.js` | Vite and test configuration |
| `frontend/eslint.config.js` | ESLint configuration |
| `frontend/index.html` | Vite HTML entry |
| `frontend/src/main.jsx` | React app bootstrap |
| `frontend/src/App.jsx` | Main dashboard composition |
| `frontend/src/styles.css` | Application styling |
| `frontend/src/api/client.js` | API client for upload, query, metrics, evaluation, feedback |
| `frontend/src/api/client.test.js` | API client tests |
| `frontend/src/components/ChatWorkspace.jsx` | Chat, validation, citations, evidence, timing, feedback |
| `frontend/src/components/KnowledgeBase.jsx` | Upload and document index management |
| `frontend/src/components/EvaluationDashboard.jsx` | Experiment metrics and comparison dashboard |
| `frontend/src/components/EvaluationDashboard.test.jsx` | Evaluation dashboard tests |
| `frontend/src/components/SourcePanel.jsx` | Retrieved evidence and source display |
| `frontend/src/components/Icon.jsx` | Lightweight icon component |
| `frontend/src/components/ui.jsx` | Shared UI primitives |
| `frontend/src/test/setup.js` | Vitest setup |

Data files:

| File | Purpose |
| --- | --- |
| `data/README.md` | Dataset documentation |
| `data/source_documents/*` | Generated enterprise PDFs, DOCX, TXT, and HTML documents |
| `data/ground_truth/canonical_passages.jsonl` | Canonical page-level evidence passages used by evaluation |
| `data/ground_truth/corpus_manifest.json` | Document/page/checksum manifest |
| `data/benchmark/enterprise_qa_v1.jsonl` | Primary benchmark dataset |
| `data/benchmark/enterprise_qa_v1.csv` | CSV benchmark export |
| `data/benchmark/DATASHEET.md` | Benchmark datasheet |

Evaluation files:

| File | Purpose |
| --- | --- |
| `evaluation/schemas.py` | Benchmark, retrieved passage, citation, and query result schemas |
| `evaluation/adapters.py` | HTTP, Python, and replay adapters |
| `evaluation/metrics.py` | Deterministic retrieval, generation, citation, refusal, and latency metrics |
| `evaluation/judges.py` | Optional OpenAI/custom judge hooks |
| `evaluation/io_utils.py` | Dataset/config reading and hashing helpers |
| `evaluation/reporting.py` | JSON, Markdown, CSV, improvement, and human-review report writers |
| `evaluation/runner.py` | Main experiment runner |
| `evaluation/run_experiments.py` | YAML config wrapper for CI/local/full runs |
| `evaluation/mlflow_tracking.py` | MLflow artifact and metric logging |
| `evaluation/configs/experiments.v1.json` | Versioned A-D experiment definitions |
| `evaluation/configs/ci.yaml` | Fast smoke evaluation config |
| `evaluation/configs/local.yaml` | Full local in-process evaluation config |
| `evaluation/configs/full.yaml` | Full HTTP-service evaluation config |
| `evaluation/results/latest.*` | Stable latest report paths |
| `evaluation/results/20260712T002710Z-python/*` | Immutable measured report used by this README |
| `evaluation/tests/*.py` | Evaluation metric, runner, report, asset, and citation-neutrality tests |

Script files:

| File | Purpose |
| --- | --- |
| `scripts/generate_enterprise_assets.py` | Generates the sample enterprise corpus and benchmark assets |
| `scripts/validate_evaluation_assets.py` | Validates generated source documents and manifest consistency |
| `scripts/validate_benchmark.py` | Validates benchmark schema, size, and coverage |
| `scripts/run_evaluation.py` | Thin wrapper for direct evaluation runner usage |

Documentation files:

| File | Purpose |
| --- | --- |
| `docs/architecture.md` | Architecture notes |
| `docs/api.md` | API contract notes |
| `docs/evaluation.md` | Evaluation methodology notes |
| `docs/operations.md` | Operations and deployment notes |

GitHub Actions:

| File | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Lint, type-check, tests, benchmark validation, Docker builds, evaluation gate |
| `.github/workflows/release.yml` | Full evaluation before optional release image build |

## Security and Production Notes

This is a production-style reference project, not a finished enterprise security boundary.

Current limitations to address before real internal deployment:

- add authentication and authorization
- add tenant or document-level access control
- enforce MIME sniffing, malware scanning, and archive bomb protection
- add upload quarantine and DLP checks
- add prompt-injection hardening for hostile documents
- move metadata persistence to a managed database such as PostgreSQL
- configure real secret management
- add production observability such as OpenTelemetry traces
- add backup and retention policies for uploaded documents and vector stores

The code is structured so these concerns can be added without rewriting the RAG pipeline.

## Resume-Ready Bullets

- Built an enterprise hybrid RAG copilot with FastAPI, React, LangChain, LangGraph, Chroma-compatible vector retrieval, BM25, reranking, citation generation, and answer validation.
- Implemented document ingestion for PDF, DOCX, TXT, and HTML with metadata extraction, chunking, duplicate detection, embeddings, vector indexing, and BM25 indexing.
- Designed a LangGraph validation agent that verifies factual claims and citations, revises unsupported answers, and refuses insufficient-evidence queries with structured JSON output.
- Created a generated enterprise policy corpus with 12 documents, 48 page-level passages, and a 248-question benchmark covering exact policy, paraphrase, multi-document, ambiguous, adversarial, and unanswerable questions.
- Built an evaluation framework comparing Dense RAG, Hybrid RAG, Hybrid + Reranker, and Hybrid + Validator using Recall@K, Precision@K, MRR, nDCG, correctness, faithfulness, citation precision/recall, hallucination rate, refusal accuracy, latency, and cost fields.
- Produced measured offline evaluation results showing Recall@5 improved from 0.7355 to 0.9139 after hybrid retrieval plus reranking, and citation precision reached 0.9531 with the validator enabled.
- Added MLOps workflows with Docker Compose, MLflow hooks, versioned retrieval configs, immutable evaluation reports, GitHub Actions CI, pytest, mypy, Ruff, Vitest, and frontend build checks.

## Honest Project Takeaway

The strongest measured gain is retrieval quality: dense-only Recall@5 of 0.7355 improved to 0.9139 with hybrid retrieval, reciprocal-rank fusion, and reranking. The validator added citation precision of 0.9531 and structured evidence checks, but it increased latency and slightly reduced deterministic correctness in the offline baseline because it revised or refused more conservatively. That is the point of the project: the evaluation pipeline makes the tradeoff visible instead of hiding it behind a polished demo.
