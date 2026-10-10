from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.config import get_settings
from app.db.session import engine
from app.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    yield
    await engine.dispose()


app = FastAPI(title="AI Chat", lifespan=lifespan)
app.include_router(health.router)
