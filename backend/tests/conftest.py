import asyncio
import logging
from collections.abc import AsyncIterator, Iterator

import pytest
import structlog
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.types import Receive, Scope, Send

from app.config import BACKEND_DIR, Settings, get_settings
from app.db.session import create_engine
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_logging() -> Iterator[None]:
    """configure_logging() is global; don't leak it (e.g. its level) into other tests."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    structlog.reset_defaults()
    root.handlers, root.level = handlers, level


@pytest.fixture(scope="session")
def settings() -> Settings:
    """App settings with DATABASE_URL's database swapped for `<name>_test`."""
    url = make_url(get_settings().database_url)
    test_url = url.set(database=f"{url.database}_test").render_as_string(hide_password=False)
    return get_settings().model_copy(update={"database_url": test_url})


async def create_database(admin_url: str, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()


@pytest.fixture(scope="session")
def test_database(settings: Settings) -> None:
    """Create the test database if needed and migrate it to head, once per run."""
    name = make_url(settings.database_url).database
    assert name
    asyncio.run(create_database(get_settings().database_url, name))
    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = settings.database_url
    command.upgrade(config, "head")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


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
async def db_session(settings: Settings, test_database: None) -> AsyncIterator[AsyncSession]:
    """Session inside a transaction that is rolled back, so tests leave the DB untouched."""
    engine = create_engine(settings.database_url)
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
