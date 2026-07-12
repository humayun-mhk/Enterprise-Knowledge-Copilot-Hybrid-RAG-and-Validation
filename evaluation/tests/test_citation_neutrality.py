from __future__ import annotations

from evaluation.metrics import evaluate_item
from evaluation.schemas import BenchmarkItem, QueryResult


def test_inline_citation_markers_do_not_reduce_answer_correctness() -> None:
    item = BenchmarkItem(
        item_id="citation-neutrality",
        category="exact_policy",
        question="How many annual leave days are provided?",
        expected_answer="Employees receive 20 annual leave days.",
        expected_documents=("handbook.pdf",),
        expected_pages=(14,),
        answerable=True,
        expected_keywords=("20", "annual leave"),
    )
    plain = QueryResult(answer="Employees receive 20 annual leave days.")
    cited = QueryResult(
        answer="Employees receive 20 annual leave days. [handbook.pdf, Page 14]"
    )

    plain_metrics = evaluate_item(item, plain)
    cited_metrics = evaluate_item(item, cited)

    assert cited_metrics["answer_token_f1"] == plain_metrics["answer_token_f1"]
    assert cited_metrics["answer_correctness"] == plain_metrics["answer_correctness"]
    assert cited_metrics["answer_relevance"] == plain_metrics["answer_relevance"]

