from __future__ import annotations

from app.services.evaluation import compare_experiments, evaluate_records, token_f1


def test_retrieval_and_generation_metrics_are_computed() -> None:
    records = [
        {
            "question": "How many leave days?",
            "answer": "Employees receive 20 annual leave days.",
            "expected_answer": "20 annual leave days",
            "answerable": True,
            "expected_keywords": ["20", "leave"],
            "relevant": ["c1"],
            "retrieved": ["c1", "c2"],
            "retrieval_latency_ms": 4.0,
            "latency_ms": 10.0,
            "validation": {"supported_claims": 1, "unsupported_claims": 0, "citation_coverage": 1.0},
            "citations": [{"document": "Handbook.pdf", "page": 14}],
            "expected_citations": [{"document": "Handbook.pdf", "page": 14}],
            "token_usage": {"total_tokens": 25, "estimated_cost_usd": 0.001},
        }
    ]
    metrics = evaluate_records(records)
    assert metrics["recall_at_3"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
    assert metrics["total_estimated_cost_usd"] == 0.001


def test_unanswerable_refusal_and_missing_results() -> None:
    records = [{"answer": "I don't have enough evidence in the indexed documents to answer that question.", "answerable": False}]
    assert evaluate_records(records)["refusal_accuracy"] == 1.0
    comparison = compare_experiments({"A": {"mrr": 0.5}, "C": {"mrr": 0.7}})
    assert comparison["missing_experiments"] == ["B", "D"]
    assert comparison["deltas"][0]["absolute_change"]["mrr"] == 0.2
    assert token_f1("twenty leave days", "twenty leave days") == 1.0
