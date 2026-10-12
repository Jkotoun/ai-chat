from collections.abc import AsyncIterator, Iterator

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import Receive, Scope, Send

from app.config import get_settings
from app.db.session import create_engine
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_logging() -> Iterator[None]:
    """configure_logging() is global; don't leak it (e.g. its level) into other tests."""
    yield
    structlog.reset_defaults()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # ASGITransport skips lifespan and its state, so do both by hand.
    async with app.router.lifespan_context(app) as state:

        async def app_with_state(scope: Scope, receive: Receive, send: Send) -> None:
            scope["state"] = dict(state or {})
            await app(scope, receive, send)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_state), base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Session inside a transaction that is rolled back, so tests leave the DB untouched."""
    engine = create_engine(get_settings().database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def db_session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Sessions that share db_session's rolled-back transaction."""
    return async_sessionmaker(bind=db_session.bind, join_transaction_mode="create_savepoint")
