from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.ingestion import parse_document


ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "data" / "source_documents"


@pytest.mark.integration
def test_generated_multiformat_corpus_is_parseable() -> None:
    """Exercise the real generated assets, not only tiny unit-test strings."""

    expected_counts = {".pdf": 4, ".docx": 4, ".txt": 2, ".html": 2}
    actual_counts = {
        suffix: len(list(SOURCES.glob(f"*{suffix}")))
        for suffix in expected_counts
    }
    assert actual_counts == expected_counts

    for source in sorted(SOURCES.iterdir()):
        parsed = parse_document(source)
        assert parsed.blocks, f"No text extracted from {source.name}"
        assert all(block.text.strip() for block in parsed.blocks)
        if source.suffix.casefold() in {".pdf", ".docx"}:
            assert parsed.page_count == 4, source.name
        else:
            assert parsed.page_count >= 1, source.name

    handbook = parse_document(SOURCES / "Employee_Handbook_2026.pdf")
    first_page = " ".join(
        block.text for block in handbook.blocks if block.page_number == 1
    )
    assert "20 paid annual leave days" in first_page


@pytest.mark.integration
def test_generated_pdf_upload_index_query_round_trip(settings) -> None:
    source = SOURCES / "Employee_Handbook_2026.pdf"
    app = create_app(settings)

    with TestClient(app) as client, source.open("rb") as handle:
        upload = client.post(
            "/documents/upload",
            files={"files": (source.name, handle, "application/pdf")},
        )
        assert upload.status_code == 200, upload.text
        document_id = upload.json()["documents"][0]["document_id"]

        indexed = client.post(
            "/documents/index", json={"document_ids": [document_id]}
        )
        assert indexed.status_code == 200, indexed.text
        assert indexed.json()["total_chunks_indexed"] >= 4

        response = client.post(
            "/query",
            json={
                "question": "How many paid annual leave days do full-time employees receive?",
                "experiment": "D",
                "top_k": 5,
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert "20" in result["answer"]
        assert result["citations"]
        assert result["citations"][0]["document"] == source.name
        assert result["citations"][0]["page"] == 1
        assert "20 paid annual leave days" in result["citations"][0]["quoted_evidence"]
        assert result["validation"]["status"] in {"APPROVED", "REVISE"}
