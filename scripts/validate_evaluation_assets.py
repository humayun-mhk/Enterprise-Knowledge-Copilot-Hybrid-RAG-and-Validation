"""Fast, API-free integrity check for generated corpus and benchmark assets."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REQUIRED_FIELDS = {
    "question", "expected_answer", "expected_document", "expected_page", "answerable", "expected_keywords"
}
REQUIRED_CATEGORIES = {
    "answerable", "multi_document", "ambiguous", "unanswerable", "exact_policy", "adversarial", "paraphrase"
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, object]:
    manifest_path = DATA / "ground_truth" / "corpus_manifest.json"
    benchmark_path = DATA / "benchmark" / "enterprise_qa_v1.jsonl"
    csv_path = DATA / "benchmark" / "enterprise_qa_v1.csv"
    passages_path = DATA / "ground_truth" / "canonical_passages.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("synthetic"):
        raise AssertionError("Corpus must be explicitly marked synthetic")

    extensions: Counter[str] = Counter()
    logical_pages = 0
    for record in manifest["documents"]:
        path = DATA / "source_documents" / record["document_name"]
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Missing or empty source document: {path}")
        if sha256(path) != record["sha256"]:
            raise AssertionError(f"Hash mismatch: {path}")
        extensions[path.suffix.casefold()] += 1
        logical_pages += int(record["page_count"])
        if path.suffix.casefold() == ".pdf":
            data = path.read_bytes()
            if not data.startswith(b"%PDF-") or len(re.findall(rb"/Type\s*/Page\b", data)) != record["page_count"]:
                raise AssertionError(f"Invalid PDF or page count: {path}")
        elif path.suffix.casefold() == ".docx":
            if not zipfile.is_zipfile(path):
                raise AssertionError(f"Invalid DOCX container: {path}")
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise AssertionError(f"DOCX lacks word/document.xml: {path}")
    for extension, minimum in {".pdf": 2, ".docx": 2, ".txt": 2, ".html": 2}.items():
        if extensions[extension] < minimum:
            raise AssertionError(f"Need at least {minimum} {extension} source documents")

    passage_records = [json.loads(line) for line in passages_path.read_text(encoding="utf-8").splitlines() if line]
    if len(passage_records) != logical_pages:
        raise AssertionError("Canonical passage count does not match manifest logical pages")
    if len({record["chunk_id"] for record in passage_records}) != len(passage_records):
        raise AssertionError("Canonical chunk IDs are not unique")

    benchmark = [json.loads(line) for line in benchmark_path.read_text(encoding="utf-8").splitlines() if line]
    if len(benchmark) < 240:
        raise AssertionError(f"Benchmark has only {len(benchmark)} questions")
    if len({record["id"] for record in benchmark}) != len(benchmark):
        raise AssertionError("Benchmark IDs are not unique")
    for record in benchmark:
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            raise AssertionError(f"{record.get('id')} lacks {sorted(missing)}")
        if record["answerable"] and (not record["expected_document"] or not record["expected_page"]):
            raise AssertionError(f"Answerable item lacks retrieval ground truth: {record['id']}")
    category_counts = Counter(record["category"] for record in benchmark)
    if REQUIRED_CATEGORIES - category_counts.keys():
        raise AssertionError(f"Missing categories: {sorted(REQUIRED_CATEGORIES - category_counts.keys())}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != len(benchmark):
        raise AssertionError("CSV and JSONL benchmark row counts differ")
    return {
        "documents": len(manifest["documents"]),
        "formats": dict(sorted(extensions.items())),
        "logical_pages": logical_pages,
        "benchmark_questions": len(benchmark),
        "categories": dict(sorted(category_counts.items())),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))

