from __future__ import annotations

import re
from typing import Sequence

from ..domain import RetrievalHit
from ..schemas import Citation
from .generation import REFUSAL_TEXT, split_sentences
from .reranker import lexical_relevance

CITATION_PATTERN = re.compile(r"\s*\[[^\]]+?,\s*Page\s+[^\]]+\]", flags=re.IGNORECASE)


def strip_generated_citations(text: str) -> str:
    return CITATION_PATTERN.sub("", text).strip()


def best_evidence_sentence(claim: str, passage: str) -> str:
    sentences = split_sentences(passage) or [re.sub(r"\s+", " ", passage).strip()]
    best = max(sentences, key=lambda sentence: lexical_relevance(claim, sentence), default=passage)
    return best[:600].strip()


def generate_citations(
    answer: str,
    hits: Sequence[RetrievalHit],
    *,
    minimum_alignment: float = 0.18,
) -> tuple[str, list[Citation]]:
    answer = strip_generated_citations(answer)
    if not answer or answer == REFUSAL_TEXT or not hits:
        return answer or REFUSAL_TEXT, []
    cited_sentences: list[str] = []
    citations: list[Citation] = []
    seen_chunks: set[str] = set()
    for claim in split_sentences(answer) or [answer]:
        ranked = sorted(
            ((lexical_relevance(claim, hit.chunk.chunk_text), hit) for hit in hits),
            key=lambda item: (-item[0], item[1].rank),
        )
        best_score, best_hit = ranked[0]
        if best_score < minimum_alignment:
            cited_sentences.append(claim)
            continue
        page_label = best_hit.chunk.page_number if best_hit.chunk.page_number is not None else "N/A"
        marker = f"[{best_hit.chunk.document_name}, Page {page_label}]"
        cited_sentences.append(f"{claim} {marker}")
        if best_hit.chunk.chunk_id not in seen_chunks:
            citations.append(
                Citation(
                    document=best_hit.chunk.document_name,
                    page=best_hit.chunk.page_number,
                    chunk_id=best_hit.chunk.chunk_id,
                    quoted_evidence=best_evidence_sentence(claim, best_hit.chunk.chunk_text),
                    section=best_hit.chunk.section,
                )
            )
            seen_chunks.add(best_hit.chunk.chunk_id)
    return " ".join(cited_sentences), citations

