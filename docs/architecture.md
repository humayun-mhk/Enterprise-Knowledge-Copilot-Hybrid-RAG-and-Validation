# System architecture

Enterprise Knowledge Copilot is organized as a modular monolith for local development and as independently deployable API, web, and experiment-tracking services in Docker. Retrieval, generation, and validation are exposed behind Python interfaces so individual providers can be replaced without changing the HTTP contract.

## Online query path

```mermaid
flowchart TD
    U[Employee question] --> P[Normalize and classify query]
    P --> R{Query router}
    R -->|Experiment A| D[Dense retrieval]
    R -->|Experiments B-D| H[Hybrid retrieval]
    H --> D
    H --> B[BM25 retrieval]
    D --> F[Weighted / reciprocal-rank fusion]
    B --> F
    F --> X{Reranking enabled?}
    X -->|C-D| CE[Cross-encoder reranker]
    X -->|A-B| G[Grounded answer generator]
    CE --> G
    G --> C[Citation builder]
    C --> V{Validation enabled?}
    V -->|D| LG[LangGraph claim and citation validator]
    V -->|A-C| O[Response]
    LG -->|APPROVED| O
    LG -->|REVISE| RW[Grounded rewrite]
    RW --> O
    LG -->|INSUFFICIENT_EVIDENCE| REF[Safe refusal]
    REF --> O
```

The API returns both a human-readable answer and machine-readable provenance. Retrieval candidates retain their original chunk metadata throughout fusion and reranking; citations are never reconstructed from model memory.

## Ingestion path

```mermaid
flowchart LR
    F[PDF / DOCX / TXT / HTML] --> P[Format parser]
    P --> N[Cleaning and normalization]
    N --> M[Page and section metadata]
    M --> C[Configurable chunks + overlap]
    C --> SHA[Content fingerprint]
    SHA -->|new| E[Embedding adapter]
    SHA -->|duplicate| SKIP[Deduplicate]
    E --> VS[(Chroma vector index)]
    C --> BM[(BM25 corpus)]
    C --> DB[(Metadata store)]
```

Documents receive stable identifiers based on content. Chunks carry `document_id`, `document_name`, `page_number`, `section`, `chunk_id`, text, and arbitrary metadata. A separate fingerprint prevents duplicate source passages from being inserted during repeated indexing.

## Retrieval experiments

| Version | Dense | BM25 | Fusion | Cross-encoder | Citations | Validator |
|---|---:|---:|---|---:|---:|---:|
| A — Dense RAG | Yes | No | — | No | Optional response metadata | No |
| B — Hybrid RAG | Yes | Yes | Weighted merge | No | Optional response metadata | No |
| C — Hybrid + reranker | Yes | Yes | Reciprocal-rank fusion | Yes | No | No |
| D — Hybrid + validator | Yes | Yes | Reciprocal-rank fusion | Yes | Yes | LangGraph |

The experiment name is part of each query and metric record. This prevents comparisons from silently using different parameters.

## Validation state machine

The LangGraph state contains the question, proposed answer, retrieved passages, citations, claim assessments, and terminal verdict.

```mermaid
stateDiagram-v2
    [*] --> ExtractClaims
    ExtractClaims --> VerifyClaimsAndCitations
    VerifyClaimsAndCitations --> Decide
    Decide --> Approved: every material claim supported
    Decide --> Revise: correction possible from evidence
    Decide --> Insufficient: evidence absent or contradictory
    Revise --> [*]: return corrected supported claims
    Approved --> [*]
    Insufficient --> [*]
```

The deterministic validator remains available when no LLM key is configured. It evaluates sentence-level lexical support, cited chunk identity, citation coverage, contradictions detectable from expected negations/numbers, and evidence thresholds. A `REVISE` verdict returns only supported claims; the caller rebuilds citations over that corrected answer.

## Storage boundaries

- Chroma stores embeddings and chunk metadata in a persistent volume.
- The metadata repository stores source-document state, feedback, and query audit records.
- The BM25 index is reconstructed from persisted chunks at startup or indexing time.
- MLflow stores versioned experiment parameters, metrics, and report artifacts.
- Raw uploads are isolated from public web assets and accepted only through the API.

## Production hardening notes

The reference implementation is deliberately provider-neutral. Before handling confidential documents, deploy behind enterprise identity, use per-tenant collections and row-level authorization, encrypt storage and backups, scan uploads for malware, redact sensitive logs, set provider data-retention controls, and place asynchronous ingestion on a job queue. The included deployment is a strong local/reference baseline, not a substitute for an organization's security review.
