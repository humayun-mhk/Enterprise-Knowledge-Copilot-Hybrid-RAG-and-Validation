from __future__ import annotations

from pathlib import Path

from app.services.ingestion import (
    ParsedBlock,
    ParsedDocument,
    build_chunks,
    chunk_text,
    clean_text,
    parse_html,
    parse_txt,
    safe_filename,
)


def test_clean_chunk_and_deduplicate() -> None:
    assert clean_text("A  policy\r\n\r\n  has\tspaces") == "A policy\n\nhas spaces"
    pieces = list(chunk_text("word " * 100, chunk_size=80, overlap=15))
    assert len(pieces) > 2
    assert all(len(piece) <= 85 for piece in pieces)

    parsed = ParsedDocument(
        blocks=[ParsedBlock("The same policy text."), ParsedBlock("The same policy text.")],
        page_count=1,
    )
    chunks, duplicates = build_chunks(
        parsed,
        document_id="doc-1",
        document_name="policy.txt",
        chunk_size=200,
        overlap=20,
    )
    assert len(chunks) == 1
    assert duplicates == 1
    assert chunks[0].chunk_id.startswith("chunk_")


def test_txt_form_feeds_preserve_pages(tmp_path: Path) -> None:
    path = tmp_path / "manual.txt"
    path.write_text("Page one heading\nFirst rule.\fPage two heading\nSecond rule.", encoding="utf-8")
    parsed = parse_txt(path)
    assert parsed.page_count == 2
    assert {block.page_number for block in parsed.blocks} == {1, 2}


def test_html_data_page_metadata(tmp_path: Path) -> None:
    path = tmp_path / "schedule.html"
    path.write_text(
        """<html><body>
        <article data-page-number="1" data-section="People"><p>Keep personnel files seven years.</p></article>
        <article data-page-number="2" data-section="Finance"><p>Keep invoices seven years.</p></article>
        </body></html>""",
        encoding="utf-8",
    )
    parsed = parse_html(path)
    assert parsed.page_count == 2
    assert [(block.page_number, block.section) for block in parsed.blocks] == [(1, "People"), (2, "Finance")]


def test_safe_filename_removes_traversal() -> None:
    assert safe_filename("../../bad<>policy.txt") == "bad_policy.txt"

