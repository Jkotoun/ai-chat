"""Load the knowledge base into the documents table.

Usage: python -m app.ingest data/

Each source file found (faq.json, tos.md) replaces all rows of that source, so
re-running is idempotent and removed entries disappear.
"""

import argparse
import asyncio
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

import structlog
from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.models import TITLE_MAX_LENGTH, Document, DocumentSource
from app.db.session import create_engine
from app.logging_config import configure_logging
from app.services.embeddings import MAX_TOKENS, Embedder

logger = structlog.get_logger()

FAQ_FILE = "faq.json"
TOS_FILE = "tos.md"
# Keeps typical English well under MAX_TOKENS; ingest() checks the real token counts.
MAX_CHUNK_CHARS = 1500


@dataclass(frozen=True)
class Chunk:
    source: DocumentSource
    title: str
    content: str
    embed_text: str


class FaqEntry(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    answer: str = Field(min_length=1)


def load_faq(path: Path) -> list[Chunk]:
    """One chunk per Q&A pair; the question is embedded."""
    entries = TypeAdapter(list[FaqEntry]).validate_json(path.read_bytes())
    return [
        Chunk(source=DocumentSource.FAQ, title=e.question, content=e.answer, embed_text=e.question)
        for e in entries
    ]


def load_tos(path: Path) -> list[Chunk]:
    """One chunk per `## ` section; long sections are split into numbered parts.

    Text before the first `## ` heading (document title, intro) is skipped.
    """
    chunks = []
    try:
        sections = markdown_sections(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    for heading, body in sections:
        if not heading:
            raise ValueError(f"{path}: empty `## ` heading")
        parts = split_text(body, MAX_CHUNK_CHARS)
        if not parts:
            logger.warning("empty_section_skipped", file=str(path), heading=heading)
        for i, part in enumerate(parts, start=1):
            title = heading if len(parts) == 1 else f"{heading} ({i}/{len(parts)})"
            if len(title) > TITLE_MAX_LENGTH:
                raise ValueError(f"{path}: heading longer than {TITLE_MAX_LENGTH} chars: {title}")
            embed_text = f"{title}\n\n{part}"
            chunks.append(Chunk(DocumentSource.TOS, title, content=part, embed_text=embed_text))
    return chunks


def markdown_sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) per level-2 heading, parsed as CommonMark."""
    lines = text.splitlines()
    tokens = MarkdownIt("commonmark").parse(text)
    # An unclosed fence would silently swallow the rest of the document.
    for tok in tokens:
        if tok.type != "fence" or not tok.map:
            continue
        start, end = tok.map
        if end == len(lines) and not lines[-1].strip().startswith(tok.markup):
            raise ValueError(f"unclosed code fence at line {start + 1}")

    headings = [
        (tokens[i + 1].content.strip(), tok.map)
        for i, tok in enumerate(tokens)
        if tok.type == "heading_open" and tok.tag == "h2" and tok.map
    ]
    ends = [m[0] for _, m in headings[1:]] + [len(lines)]
    return [
        (heading, "\n".join(lines[m[1] : end]))
        for (heading, m), end in zip(headings, ends, strict=True)
    ]


def split_text(text: str, max_chars: int) -> list[str]:
    """Pack paragraphs into parts of <= max_chars, splitting oversized ones finer."""
    pieces: list[tuple[str, str]] = []  # (text, separator to join it to the previous piece)
    for paragraph in filter(None, (p.strip() for p in re.split(r"\n\s*\n", text))):
        if len(paragraph) <= max_chars:
            pieces.append((paragraph, "\n\n"))
            continue
        for i, piece in enumerate(split_oversized(paragraph, max_chars)):
            pieces.append((piece, " " if i else "\n\n"))

    parts: list[str] = []
    for piece, sep in pieces:
        if parts and len(parts[-1]) + len(sep) + len(piece) <= max_chars:
            parts[-1] += sep + piece
        else:
            parts.append(piece)
    return parts


def split_oversized(paragraph: str, max_chars: int) -> list[str]:
    """Split on sentences, then words, then hard character cuts."""
    pieces = []
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        for word in sentence.split() if len(sentence) > max_chars else [sentence]:
            pieces += [word[i : i + max_chars] for i in range(0, len(word), max_chars)]
    return pieces


def load_directory(data_dir: Path) -> tuple[set[DocumentSource], list[Chunk]]:
    """Sources whose files exist (even if empty) and their chunks."""
    sources: set[DocumentSource] = set()
    chunks = []
    if (faq := data_dir / FAQ_FILE).exists():
        sources.add(DocumentSource.FAQ)
        chunks += load_faq(faq)
    if (tos := data_dir / TOS_FILE).exists():
        sources.add(DocumentSource.TOS)
        chunks += load_tos(tos)
    return sources, chunks


async def ingest(
    session: AsyncSession,
    embedder: Embedder,
    sources: Collection[DocumentSource],
    chunks: Sequence[Chunk],
) -> None:
    """Replace all rows of `sources` with `chunks`. The caller commits."""
    texts = [c.embed_text for c in chunks]
    for chunk, tokens in zip(chunks, await embedder.count_tokens(texts), strict=True):
        if tokens >= MAX_TOKENS:  # counts are capped, so this means "at or over the limit"
            logger.warning("chunk_truncated", source=chunk.source, title=chunk.title)
    vectors = await embedder.embed_documents(texts)

    # Serializes concurrent runs (they would otherwise both keep their inserts) without
    # blocking readers. Relies on READ COMMITTED: the DELETE must see rows committed while waiting.
    await session.execute(text(f"LOCK TABLE {Document.__tablename__} IN SHARE ROW EXCLUSIVE MODE"))
    await session.execute(delete(Document).where(Document.source.in_(sources)))
    session.add_all(
        Document(source=c.source, title=c.title, content=c.content, embedding=v)
        for c, v in zip(chunks, vectors, strict=True)
    )
    await session.flush()


async def main(data_dir: Path) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    sources, chunks = load_directory(data_dir)
    if not sources:
        raise SystemExit(f"no {FAQ_FILE} or {TOS_FILE} found in {data_dir}")

    embedder = await Embedder.load()
    engine = create_engine(settings.database_url).execution_options(
        isolation_level="READ COMMITTED"
    )
    try:
        async with async_sessionmaker(engine).begin() as session:
            await ingest(session, embedder, sources, chunks)
    finally:
        await engine.dispose()

    logger.info("ingest_done", **{s: sum(c.source == s for c in chunks) for s in sorted(sources)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load the knowledge base into the database.")
    parser.add_argument("data_dir", type=Path, help="directory with faq.json and/or tos.md")
    asyncio.run(main(parser.parse_args().data_dir))
