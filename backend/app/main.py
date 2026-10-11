from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import health
from app.config import get_settings
from app.db.session import create_engine


class State(TypedDict):
    session_factory: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    engine = create_engine(get_settings().database_url)
    try:
        yield {"session_factory": async_sessionmaker[AsyncSession](engine, expire_on_commit=False)}
    finally:
        await engine.dispose()


app = FastAPI(title="AI Chat", lifespan=lifespan)
app.include_router(health.router)
