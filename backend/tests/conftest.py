from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.types import Receive, Scope, Send

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # ASGITransport skips lifespan and its state, so do both by hand.
    async with app.router.lifespan_context(app) as state:

        async def app_with_state(scope: Scope, receive: Receive, send: Send) -> None:
            scope["state"] = dict(state or {})
            await app(scope, receive, send)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_state), base_url="http://test"
        ) as client:
            yield client
