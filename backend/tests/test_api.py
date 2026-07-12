from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.main import create_app


def test_full_api_flow(settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["embedding_provider"] == "hash"

        content = b"Annual Leave Policy\nFull-time employees receive 20 paid annual leave days per calendar year."
        upload = client.post(
            "/documents/upload",
            content=content,
            headers={"x-filename": "Employee-Handbook.txt", "content-type": "text/plain"},
        )
        assert upload.status_code == 200, upload.text
        document_id = upload.json()["documents"][0]["document_id"]
        duplicate = client.post(
            "/documents/upload",
            content=content,
            headers={"x-filename": "copy.txt", "content-type": "text/plain"},
        )
        assert duplicate.json()["documents"][0]["duplicate"] is True

        indexed = client.post("/documents/index", json={"document_ids": [document_id]})
        assert indexed.status_code == 200, indexed.text
        assert indexed.json()["total_chunks_indexed"] == 1

        answer = client.post(
            "/query",
            json={"question": "How many paid annual leave days do full-time employees receive?", "experiment": "D", "top_k": 3},
        )
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert "20" in body["answer"]
        assert body["citations"][0]["document"] == "Employee-Handbook.txt"
        assert body["validation"]["status"] in {"APPROVED", "REVISE"}
        assert body["component_backends"]["vector_store"] == "memory"
        evidence = body["evidence"][0]
        assert evidence["text"] == evidence["passage"] == evidence["chunk_text"]

        ablation = client.post(
            "/query",
            json={"question": "How many paid annual leave days?", "experiment": "B", "top_k": 3},
        ).json()
        assert ablation["citations"] == []
        assert ablation["validation"]["status"] == "NOT_RUN"

        feedback = client.post("/feedback", json={"query_id": body["query_id"], "rating": 5, "helpful": True})
        assert feedback.status_code == 200
        metrics = client.get("/metrics").json()
        assert metrics["total_queries"] == 2
        assert metrics["feedback_count"] == 1
        evaluations = client.get("/evaluation/results").json()
        assert evaluations["has_measured_results"] == bool(evaluations["latest"] or evaluations["runs"])
        assert isinstance(evaluations["experiments"], list)


def test_query_stream_is_sse(settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post("/query/stream", json={"question": "Unknown policy?", "experiment": "D"})
        assert response.status_code == 200
        assert "event: token" in response.text
        assert "event: done" in response.text
