"""Load the knowledge base into the documents table.

Usage: python -m app.ingest data/
"""

import argparse
import asyncio
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db.session import create_engine
from app.logging_config import configure_logging
from app.services.embeddings import Embedder
from app.services.ingestion import FAQ_FILE, TOS_FILE, ingest, load_directory

logger = structlog.get_logger()


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
