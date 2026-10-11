from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import httpx
import structlog
from fastapi import FastAPI
from groq import AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import chat, health
from app.config import get_settings
from app.db.session import create_engine
from app.logging_config import configure_logging
from app.services.embeddings import Embedder
from app.services.llm import LLMClient

logger = structlog.get_logger()


class State(TypedDict):
    session_factory: async_sessionmaker[AsyncSession]
    embedder: Embedder
    llm: LLMClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.groq_api_key:
        logger.warning("groq_api_key_missing")
    embedder = await Embedder.load()
    engine = create_engine(settings.database_url)
    groq = AsyncGroq(
        api_key=settings.groq_api_key,
        timeout=httpx.Timeout(settings.groq_read_timeout_seconds, connect=5),
        max_retries=1,
    )
    try:
        yield {
            "session_factory": async_sessionmaker[AsyncSession](engine, expire_on_commit=False),
            "embedder": embedder,
            "llm": LLMClient(groq, settings.groq_model),
        }
    finally:
        await groq.close()
        await engine.dispose()


# Operation IDs become the generated frontend client's function names.
app = FastAPI(
    title="AI Chat", lifespan=lifespan, generate_unique_id_function=lambda route: route.name
)
app.include_router(health.router)
app.include_router(chat.router)
