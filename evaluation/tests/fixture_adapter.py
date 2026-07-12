"""Test-only oracle-shaped fixture used to exercise report plumbing, not benchmarking."""

from evaluation.schemas import Citation, QueryResult, RetrievedPassage


def adapter(item, experiment):
    passages = []
    citations = []
    for index, (document, page) in enumerate(zip(item.expected_documents, item.expected_pages), start=1):
        text = item.source_passages[min(index - 1, len(item.source_passages) - 1)] if item.source_passages else item.expected_answer
        chunk_id = f"fixture-{index}"
        passages.append(RetrievedPassage(chunk_id, document, page, text, rank=index))
        if experiment["id"] == "D":
            citations.append(Citation(document, page, chunk_id, item.expected_answer if len(item.expected_documents) == 1 else text))
    answer = item.expected_answer
    return QueryResult(
        answer=answer,
        retrieved_passages=passages,
        citations=citations,
        validation_status="APPROVED" if experiment["id"] == "D" else None,
        retrieval_latency_ms=1.0,
        generation_latency_ms=2.0,
        total_latency_ms=3.0,
    )


def failing_adapter(item, experiment):
    return QueryResult(answer="", error="deliberate fixture failure")
