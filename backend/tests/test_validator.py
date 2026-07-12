from __future__ import annotations

from app.domain import ChunkRecord, RetrievalHit
from app.schemas import ValidationStatus
from app.services.citations import generate_citations
from app.services.validator import AnswerValidationAgent


def _evidence() -> list[RetrievalHit]:
    chunk = ChunkRecord(
        "chunk_104",
        "employee-handbook",
        "Employee-Handbook.pdf",
        14,
        "Annual leave",
        "Full-time employees receive 20 paid annual leave days per calendar year. Employees may carry over 5 unused days.",
    )
    return [RetrievalHit(chunk=chunk, score=0.9, rank=1, source="hybrid")]


def test_validator_approves_supported_claim(settings) -> None:
    hits = _evidence()
    answer, citations = generate_citations(
        "Full-time employees receive 20 paid annual leave days per calendar year.", hits
    )
    result = AnswerValidationAgent(settings).validate(
        question="How many annual leave days are provided?",
        answer=answer,
        hits=hits,
        citations=citations,
    )
    assert result.status == ValidationStatus.APPROVED
    assert result.supported_claims == 1
    assert result.citation_coverage == 1.0
    assert result.citation_precision == 1.0


def test_validator_rejects_wrong_number(settings) -> None:
    hits = _evidence()
    answer, citations = generate_citations(
        "Full-time employees receive 30 paid annual leave days per calendar year.", hits
    )
    result = AnswerValidationAgent(settings).validate(
        question="How many annual leave days are provided?",
        answer=answer,
        hits=hits,
        citations=citations,
    )
    assert result.status == ValidationStatus.INSUFFICIENT_EVIDENCE
    assert result.unsupported_claims == 1
    assert "30" in result.unsupported_details[0]


def test_validator_revises_mixed_answer(settings) -> None:
    hits = _evidence()
    answer, citations = generate_citations(
        "Full-time employees receive 20 paid annual leave days per calendar year. The office is closed every Friday.",
        hits,
    )
    result = AnswerValidationAgent(settings).validate(
        question="Explain the annual leave policy and office schedule.",
        answer=answer,
        hits=hits,
        citations=citations,
    )
    assert result.status == ValidationStatus.REVISE
    assert "20 paid annual leave" in (result.corrected_answer or "")
    assert "closed" not in (result.corrected_answer or "")

