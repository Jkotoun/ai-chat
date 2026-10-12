import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.config import BACKEND_DIR
from app.db.models import Document, DocumentSource
from app.services.embeddings import MAX_TOKENS, Embedder
from app.services.ingestion import (
    MAX_CHUNK_CHARS,
    Chunk,
    ingest,
    load_directory,
    load_faq,
    load_tos,
    split_text,
)
from tests.mocks import MockModel, make_embedder

FAQ, TOS = DocumentSource.FAQ, DocumentSource.TOS


def test_load_faq_embeds_question(tmp_path: Path) -> None:
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([{"question": "Q?", "answer": "A."}]))

    assert load_faq(path) == [Chunk(source=FAQ, title="Q?", content="A.", embed_text="Q?")]


def test_load_faq_rejects_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([{"question": "Q?"}]))

    with pytest.raises(ValidationError):
        load_faq(path)


def test_load_tos_one_chunk_per_section(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text("# Terms\n\nIntro.\n\n## 1. First\n\nOne.\n\nTwo.\n\n## 2. Second\nThree.\n")

    assert load_tos(path) == [
        Chunk(TOS, "1. First", "One.\n\nTwo.", "1. First\n\nOne.\n\nTwo."),
        Chunk(TOS, "2. Second", "Three.", "2. Second\n\nThree."),
    ]


def test_load_tos_ignores_headings_in_code_fences_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text("\ufeff## A\n```\n## not a heading\n```\n", encoding="utf-8")

    [chunk] = load_tos(path)

    assert chunk.title == "A"
    assert "## not a heading" in chunk.content


def test_load_tos_handles_commonmark_heading_and_fence_variants(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text(" ## A ##\n~~~\n## fake\n~~~\n##\tB\ntext\n")

    assert [(c.title, c.content) for c in load_tos(path)] == [
        ("A", "~~~\n## fake\n~~~"),
        ("B", "text"),
    ]


def test_load_tos_rejects_unclosed_fence(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text("## A\n```\nunclosed\n## B\nx\n")

    with pytest.raises(ValueError, match="unclosed code fence"):
        load_tos(path)


def test_load_faq_strips_and_rejects_blank_fields(tmp_path: Path) -> None:
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([{"question": "  ", "answer": "A."}]))

    with pytest.raises(ValidationError):
        load_faq(path)


def test_load_tos_rejects_empty_heading(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text("## \nBody.\n")

    with pytest.raises(ValueError, match="empty"):
        load_tos(path)


def test_load_tos_rejects_heading_too_long_for_column(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text(f"## {'x' * 513}\nBody.\n")

    with pytest.raises(ValueError, match="longer than"):
        load_tos(path)


def test_load_faq_rejects_question_too_long_for_column(tmp_path: Path) -> None:
    path = tmp_path / "faq.json"
    path.write_text(json.dumps([{"question": "x" * 513, "answer": "A."}]))

    with pytest.raises(ValidationError):
        load_faq(path)


def test_load_directory_reports_empty_source_files(tmp_path: Path) -> None:
    (tmp_path / "faq.json").write_text("[]")

    assert load_directory(tmp_path) == ({"faq"}, [])


def test_load_tos_numbers_parts_of_long_sections(tmp_path: Path) -> None:
    path = tmp_path / "tos.md"
    path.write_text("## Long\n\n" + "\n\n".join(["x" * 1000] * 3))

    assert [c.title for c in load_tos(path)] == ["Long (1/3)", "Long (2/3)", "Long (3/3)"]


def test_split_text_packs_paragraphs_up_to_limit() -> None:
    assert split_text("aaa\n\nbbb\n\nccc", max_chars=8) == ["aaa\n\nbbb", "ccc"]


def test_split_text_splits_oversized_paragraph_on_sentences() -> None:
    assert split_text("One one. Two two. Three.", max_chars=12) == [
        "One one.",
        "Two two.",
        "Three.",
    ]


def test_split_text_hard_splits_text_without_sentence_breaks() -> None:
    assert split_text("aaaa bbbb cccccccccc", max_chars=9) == ["aaaa bbbb", "ccccccccc", "c"]


def test_split_text_drops_blank_paragraphs() -> None:
    assert split_text("\n\na\n\n\n\n\nb\n\n", max_chars=100) == ["a\n\nb"]


async def test_sample_data_chunks_fit_the_model() -> None:
    """Uses the real tokenizer (downloads the model on first run)."""
    sources, chunks = load_directory(BACKEND_DIR / "data")
    embedder = await Embedder.load()

    tokens = await embedder.count_tokens([c.embed_text for c in chunks])

    assert sources == {c.source for c in chunks} == {"faq", "tos"}
    assert all(c.content and len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    assert max(tokens) < MAX_TOKENS


async def titles(session: AsyncSession, source: str) -> list[str]:
    stmt = select(Document.title).where(Document.source == source).order_by(Document.title)
    return list((await session.execute(stmt)).scalars())


async def test_ingest_replaces_only_given_sources(db_session: AsyncSession) -> None:
    """Integration test: needs Postgres with migrations applied."""
    embedder = make_embedder()
    faq = [Chunk(FAQ, f"Q{i}", "A", f"Q{i}") for i in range(3)]
    tos = [Chunk(TOS, "T", "C", "T\n\nC")]

    await ingest(db_session, embedder, {FAQ, TOS}, faq + tos)
    await ingest(db_session, embedder, {FAQ}, faq[1:2])

    assert await titles(db_session, "faq") == ["Q1"]
    assert await titles(db_session, "tos") == ["T"]


async def test_ingest_empty_source_clears_its_rows(db_session: AsyncSession) -> None:
    embedder = make_embedder()
    await ingest(db_session, embedder, {FAQ}, [Chunk(FAQ, "Q", "A", "Q")])

    await ingest(db_session, embedder, {FAQ}, [])

    assert await titles(db_session, "faq") == []


async def test_ingest_stores_embeddings(db_session: AsyncSession) -> None:
    model = MockModel()
    chunks = [Chunk(FAQ, "Q", "A", "embed me")]

    await ingest(db_session, make_embedder(model), {FAQ}, chunks)

    doc = (await db_session.execute(select(Document).where(Document.title == "Q"))).scalar_one()
    assert model.inputs == [["embed me"]]
    assert list(doc.embedding) == [1.0] * 384


async def test_ingest_warns_about_truncated_chunks(db_session: AsyncSession) -> None:
    chunks = [Chunk(FAQ, "Q", "A", "word " * MAX_TOKENS), Chunk(FAQ, "Q2", "A", "short")]

    with capture_logs() as logs:
        await ingest(db_session, make_embedder(), {FAQ}, chunks)

    assert [log["title"] for log in logs if log["event"] == "chunk_truncated"] == ["Q"]
