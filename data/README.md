# Synthetic enterprise RAG data

Everything below this directory is fictional and generated for development; it is not a real organization's policy or employee data.

- `source_documents/` contains 12 ingestible documents: four PDF, four DOCX, two TXT, and two HTML files.
- `ground_truth/canonical_passages.jsonl` contains one stable page-level passage per logical source page, including document, page, section, text, and metadata.
- `ground_truth/corpus_manifest.json` records versions, owners, page counts, byte sizes, and SHA-256 hashes.
- `benchmark/enterprise_qa_v1.jsonl` is the canonical 248-question evaluation set; the CSV is an analyst-friendly mirror.

Rebuild these deterministic assets with `python scripts/generate_enterprise_assets.py` and validate them with `python scripts/validate_evaluation_assets.py`.

DOCX, TXT, and HTML documents contain explicit logical page markers. Ingestion should preserve these markers as `page_number`; otherwise page-level retrieval and citation metrics for those formats cannot be computed accurately.

