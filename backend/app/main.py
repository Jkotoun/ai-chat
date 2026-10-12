from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import chat, health
from app.api.rate_limit import RateLimiter
from app.config import Settings, get_settings
from app.db.session import create_engine
from app.logging_config import configure_logging
from app.services.embeddings import Embedder
from app.services.llm import LLMClient

logger = structlog.get_logger()


class State(TypedDict):
    session_factory: async_sessionmaker[AsyncSession]
    embedder: Embedder
    llm: LLMClient
    chat_rate_limiter: RateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[State]:
        configure_logging(settings.log_level)
        if not settings.groq_api_key.get_secret_value():
            logger.warning("groq_api_key_missing")
        embedder = await Embedder.load()
        engine = create_engine(settings.database_url)
        groq = AsyncGroq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=httpx.Timeout(settings.groq_read_timeout_seconds, connect=5),
            max_retries=1,
        )
        try:
            yield {
                "session_factory": async_sessionmaker[AsyncSession](engine, expire_on_commit=False),
                "embedder": embedder,
                "llm": LLMClient(groq, settings.groq_model),
                "chat_rate_limiter": RateLimiter(settings.chat_rate_limit_per_minute),
            }
        finally:
            await groq.close()
            await engine.dispose()

    # Operation IDs become the generated frontend client's function names.
    app = FastAPI(
        title="AI Chat", lifespan=lifespan, generate_unique_id_function=lambda route: route.name
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app
