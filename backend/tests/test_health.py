import asyncio
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import health
from app.api.deps import get_session
from app.config import Settings
from app.main import create_app


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_database(client: AsyncClient, test_database: None) -> None:
    """Integration test: needs Postgres running (`docker compose up -d db`)."""
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_ready_returns_503_when_database_down(app: FastAPI, client: AsyncClient) -> None:
    class BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise ConnectionRefusedError

    async def broken_session() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


async def test_ready_returns_503_when_database_hangs(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class HangingSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            await asyncio.sleep(10)

    async def hanging_session() -> AsyncIterator[HangingSession]:
        yield HangingSession()

    monkeypatch.setattr(health, "READY_TIMEOUT_SECONDS", 0.01)
    app.dependency_overrides[get_session] = hanging_session

    response = await client.get("/health/ready")

    assert response.status_code == 503


async def test_cors_allows_configured_origin() -> None:
    app = create_app(Settings(database_url="x", cors_origins=["https://example.com"]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/chat",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.com"
