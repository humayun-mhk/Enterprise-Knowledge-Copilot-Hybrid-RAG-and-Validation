from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Sequence

from .bm25 import tokenize
from .generation import REFUSAL_TEXT


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _round_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: round(value, 6) if isinstance(value, float) else value
        for key, value in metrics.items()
    }


def _identity(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if item.get("chunk_id"):
            return str(item["chunk_id"])
        return f"{item.get('document') or item.get('document_name')}::{item.get('page') or item.get('page_number')}"
    return str(item)


def retrieval_metrics(records: Sequence[dict[str, Any]], ks: Sequence[int] = (3, 5, 10)) -> dict[str, float]:
    """Compute binary relevance retrieval metrics from recorded ranked outputs."""

    recalls: dict[int, list[float]] = defaultdict(list)
    precisions: dict[int, list[float]] = defaultdict(list)
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []
    for record in records:
        relevant = {_identity(item) for item in record.get("relevant", record.get("expected_retrieval", []))}
        retrieved = [_identity(item) for item in record.get("retrieved", record.get("evidence", []))]
        if not relevant:
            continue
        for k in ks:
            top = retrieved[:k]
            matches = sum(item in relevant for item in top)
            recalls[k].append(matches / len(relevant))
            precisions[k].append(matches / k)
        first = next((rank for rank, item in enumerate(retrieved, 1) if item in relevant), None)
        reciprocal_ranks.append(1.0 / first if first else 0.0)
        gains = [1.0 if item in relevant else 0.0 for item in retrieved]
        dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
        ideal_count = min(len(relevant), len(retrieved))
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
        ndcgs.append(dcg / idcg if idcg else 0.0)
        if record.get("retrieval_latency_ms") is not None:
            latencies.append(float(record["retrieval_latency_ms"]))
    metrics: dict[str, float] = {}
    for k in ks:
        metrics[f"recall_at_{k}"] = _mean(recalls[k])
        metrics[f"precision_at_{k}"] = _mean(precisions[k])
    metrics.update(
        {
            "mrr": _mean(reciprocal_ranks),
            "ndcg": _mean(ndcgs),
            "retrieval_latency_ms": _mean(latencies),
            "evaluated_retrieval_questions": float(len(reciprocal_ranks)),
        }
    )
    return _round_metrics(metrics)


def token_f1(expected: str, actual: str) -> float:
    expected_tokens = tokenize(expected, remove_stopwords=True)
    actual_tokens = tokenize(actual, remove_stopwords=True)
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0
    expected_counts: dict[str, int] = defaultdict(int)
    actual_counts: dict[str, int] = defaultdict(int)
    for token in expected_tokens:
        expected_counts[token] += 1
    for token in actual_tokens:
        actual_counts[token] += 1
    overlap = sum(min(count, actual_counts[token]) for token, count in expected_counts.items())
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _citation_key(citation: dict[str, Any]) -> tuple[str, int | None]:
    document = str(citation.get("document") or citation.get("document_name") or "")
    page = citation.get("page", citation.get("page_number"))
    if page is None or page == "":
        return document, None
    return document, int(page)


def generation_metrics(records: Sequence[dict[str, Any]]) -> dict[str, float]:
    correctness: list[float] = []
    keyword_recall: list[float] = []
    relevance: list[float] = []
    faithfulness: list[float] = []
    hallucination: list[float] = []
    unsupported_rates: list[float] = []
    refusal_correct: list[float] = []
    citation_coverages: list[float] = []
    citation_precisions: list[float] = []
    citation_recalls: list[float] = []
    contextual_precisions: list[float] = []
    contextual_recalls: list[float] = []
    latencies: list[float] = []
    retrieval_latencies: list[float] = []
    token_totals: list[float] = []
    costs: list[float] = []

    for record in records:
        answer = str(record.get("answer", ""))
        expected = str(record.get("expected_answer", ""))
        answerable = bool(record.get("answerable", True))
        refused = answer.strip().casefold() == REFUSAL_TEXT.casefold() or "not enough evidence" in answer.casefold()
        refusal_correct.append(float((not answerable and refused) or (answerable and not refused)))
        if answerable:
            correctness.append(token_f1(expected, answer))
            expected_keywords = {str(item).casefold() for item in record.get("expected_keywords", [])}
            answer_tokens = set(tokenize(answer))
            if expected_keywords:
                keyword_recall.append(len(expected_keywords & answer_tokens) / len(expected_keywords))
            question_tokens = set(tokenize(str(record.get("question", "")), remove_stopwords=True))
            answer_token_set = set(tokenize(answer, remove_stopwords=True))
            relevance.append(
                len(question_tokens & answer_token_set) / len(question_tokens) if question_tokens else 0.0
            )

        validation = record.get("validation", {}) or {}
        supported = int(validation.get("supported_claims", record.get("supported_claims", 0)) or 0)
        unsupported = int(validation.get("unsupported_claims", record.get("unsupported_claims", 0)) or 0)
        claims = supported + unsupported
        if claims:
            grounded = supported / claims
            faithfulness.append(grounded)
            hallucination.append(unsupported / claims)
            unsupported_rates.append(unsupported / claims)
        coverage = validation.get("citation_coverage", record.get("citation_coverage"))
        if coverage is not None:
            citation_coverages.append(float(coverage))

        actual_citations = [item for item in record.get("citations", []) if isinstance(item, dict)]
        expected_citations = record.get("expected_citations")
        if expected_citations is None:
            expected_documents = record.get("expected_document", [])
            expected_pages = record.get("expected_page", [])
            if isinstance(expected_documents, str):
                expected_documents = [expected_documents]
            if not isinstance(expected_pages, list):
                expected_pages = [expected_pages]
            expected_citations = [
                {"document": document, "page": expected_pages[index] if index < len(expected_pages) else None}
                for index, document in enumerate(expected_documents or [])
            ]
        actual_keys = {_citation_key(item) for item in actual_citations}
        expected_keys = {_citation_key(item) for item in expected_citations if isinstance(item, dict)}
        if actual_keys:
            citation_precisions.append(len(actual_keys & expected_keys) / len(actual_keys))
        elif expected_keys:
            citation_precisions.append(0.0)
        if expected_keys:
            citation_recalls.append(len(actual_keys & expected_keys) / len(expected_keys))

        relevant = {_identity(item) for item in record.get("relevant", record.get("expected_retrieval", []))}
        retrieved = [_identity(item) for item in record.get("retrieved", record.get("evidence", []))]
        if retrieved and relevant:
            contextual_precisions.append(sum(item in relevant for item in retrieved) / len(retrieved))
            contextual_recalls.append(sum(item in relevant for item in retrieved) / len(relevant))
        if record.get("latency_ms") is not None:
            latencies.append(float(record["latency_ms"]))
        if record.get("retrieval_latency_ms") is not None:
            retrieval_latencies.append(float(record["retrieval_latency_ms"]))
        usage = record.get("token_usage", {}) or {}
        token_totals.append(float(usage.get("total_tokens", record.get("total_tokens", 0)) or 0))
        costs.append(float(usage.get("estimated_cost_usd", record.get("estimated_cost_usd", 0)) or 0))

    return _round_metrics(
        {
            "answer_correctness_token_f1": _mean(correctness),
            "expected_keyword_recall": _mean(keyword_recall),
            "answer_relevance_lexical": _mean(relevance),
            "faithfulness_claim_support": _mean(faithfulness),
            "contextual_precision": _mean(contextual_precisions),
            "contextual_recall": _mean(contextual_recalls),
            "hallucination_rate": _mean(hallucination),
            "refusal_accuracy": _mean(refusal_correct),
            "citation_coverage": _mean(citation_coverages),
            "citation_precision": _mean(citation_precisions),
            "citation_recall": _mean(citation_recalls),
            "unsupported_claim_rate": _mean(unsupported_rates),
            "average_latency_ms": _mean(latencies),
            "average_retrieval_latency_ms": _mean(retrieval_latencies),
            "average_token_usage": _mean(token_totals),
            "total_estimated_cost_usd": sum(costs),
            "evaluated_generation_questions": float(len(records)),
        }
    )


def evaluate_records(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    output = retrieval_metrics(records)
    output.update(generation_metrics(records))
    return output


def compare_experiments(results: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Return raw measured rows and adjacent deltas; never fills missing values."""

    order = ["A", "B", "C", "D"]
    labels = {
        "A": "Dense RAG",
        "B": "Hybrid RAG",
        "C": "Hybrid + Reranker",
        "D": "Hybrid + Validator",
    }
    rows: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []
    previous_key: str | None = None
    for key in order:
        if key not in results:
            continue
        rows.append({"experiment": key, "system": labels[key], **results[key]})
        if previous_key is not None:
            common = set(results[previous_key]) & set(results[key])
            delta = {
                metric: round(results[key][metric] - results[previous_key][metric], 6)
                for metric in sorted(common)
                if isinstance(results[key][metric], (int, float))
                and isinstance(results[previous_key][metric], (int, float))
            }
            deltas.append(
                {
                    "from_experiment": previous_key,
                    "to_experiment": key,
                    "absolute_change": delta,
                }
            )
        previous_key = key
    return {"rows": rows, "deltas": deltas, "missing_experiments": [key for key in order if key not in results]}


def log_to_mlflow(
    *,
    metrics: dict[str, float],
    parameters: dict[str, Any],
    tracking_uri: str,
    experiment_name: str,
    run_name: str,
) -> str | None:
    """Optionally track a measured run. Returns None when MLflow is not configured."""

    if not tracking_uri:
        return None
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params({key: str(value) for key, value in parameters.items()})
        mlflow.log_metrics(
            {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))}
        )
        return run.info.run_id
