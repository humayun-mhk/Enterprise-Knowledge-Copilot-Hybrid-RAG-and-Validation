from evaluation.metrics import claim_support_score, evaluate_item, retrieval_metrics
from evaluation.schemas import BenchmarkItem, Citation, QueryResult, RetrievedPassage


def item(answerable: bool = True) -> BenchmarkItem:
    return BenchmarkItem(
        item_id="q1",
        category="exact_policy",
        question="How many leave days are provided?",
        expected_answer="Employees receive 20 annual leave days.",
        expected_documents=("Handbook.pdf",) if answerable else (),
        expected_pages=(14,) if answerable else (),
        answerable=answerable,
        expected_keywords=("20", "annual leave") if answerable else ("insufficient evidence",),
    )


def passage(document: str = "Handbook.pdf", page: int = 14, text: str = "Employees receive 20 annual leave days.") -> RetrievedPassage:
    return RetrievedPassage("chunk-1", document, page, text)


def test_retrieval_metrics_count_target_once() -> None:
    metrics = retrieval_metrics(item(), [passage(), passage(), passage("Other.pdf", 1, "unrelated")])
    assert metrics["recall_at_3"] == 1.0
    assert metrics["precision_at_3"] == 1 / 3
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg_at_3"] == 1.0


def test_numeric_contradiction_is_not_supported() -> None:
    assert claim_support_score("Employees receive 60 annual leave days.", "Employees receive 20 annual leave days.") == 0.0


def test_supported_answer_and_citation_score() -> None:
    evidence = passage()
    result = QueryResult(
        answer="Employees receive 20 annual leave days. [Handbook.pdf, Page 14]",
        retrieved_passages=[evidence],
        citations=[Citation("Handbook.pdf", 14, "chunk-1", "Employees receive 20 annual leave days.")],
    )
    metrics = evaluate_item(item(), result)
    assert metrics["faithfulness"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_recall"] == 1.0
    assert metrics["refusal_correct"] == 1.0


def test_unanswerable_question_rewards_refusal() -> None:
    result = QueryResult(answer="Insufficient evidence: the documents do not contain this information.")
    metrics = evaluate_item(item(False), result)
    assert metrics["answer_correctness"] == 1.0
    assert metrics["refusal_correct"] == 1.0
    assert metrics["hallucination"] == 0.0


def test_backend_refusal_wording_is_detected() -> None:
    result = QueryResult(answer="I don't have enough evidence in the indexed documents to answer that question.")
    metrics = evaluate_item(item(False), result)
    assert metrics["refused"] == 1.0
    assert metrics["refusal_correct"] == 1.0
    assert metrics["hallucination"] == 0.0


def test_query_result_accepts_backend_timings_contract() -> None:
    result = QueryResult.from_mapping({
        "answer": "ok",
        "evidence": [],
        "timings": {"retrieval_ms": 1.25, "generation_ms": 2.5, "validation_ms": 0.75, "total_ms": 5.0},
        "token_usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "estimated_cost_usd": 0.001},
    })
    assert result.retrieval_latency_ms == 1.25
    assert result.generation_latency_ms == 2.5
    assert result.validation_latency_ms == 0.75
    assert result.total_latency_ms == 5.0
    assert result.total_tokens == 14
