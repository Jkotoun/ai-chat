import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_chat_rate_limiter, get_chat_service
from app.api.rate_limit import RateLimiter
from app.services.retrieval import RetrievedDocument
from tests.mocks import MockChatService

DOC = RetrievedDocument(id=1, source="faq", title="Reset password", content="...", score=0.9)


def parse_sse(body: str) -> list[dict[str, Any]]:
    """The JSON `data` of each event."""
    return [json.loads(block.removeprefix("data: ")) for block in body.strip().split("\n\n")]


def event_types(body: str) -> list[str]:
    return [event["type"] for event in parse_sse(body)]


@pytest.fixture
def chat_service() -> MockChatService:
    return MockChatService([DOC], ["Click ", "Forgot password."])


@pytest.fixture(autouse=True)
def override_chat_service(app: FastAPI, chat_service: MockChatService) -> None:
    app.dependency_overrides[get_chat_service] = lambda: chat_service


async def test_streams_sources_then_tokens(
    client: AsyncClient, chat_service: MockChatService
) -> None:
    response = await client.post("/chat", json={"question": " How do I reset my password? "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_types(response.text) == ["sources", "token", "token", "done"]
    events = parse_sse(response.text)
    assert events[0]["sources"] == [
        {"id": 1, "source": "faq", "title": "Reset password", "score": 0.9}
    ]
    tokens = [event["text"] for event in events if event["type"] == "token"]
    assert "".join(tokens) == "Click Forgot password."
    assert chat_service.questions == ["How do I reset my password?"]


@pytest.mark.parametrize(
    "chat_service", [MockChatService([DOC], ["Partial "], error=RuntimeError("boom"))]
)
async def test_answer_failure_ends_stream_with_error_event(client: AsyncClient) -> None:
    response = await client.post("/chat", json={"question": "Hi"})

    assert event_types(response.text) == ["sources", "token", "error"]
    assert "boom" not in response.text


@pytest.mark.parametrize(
    "chat_service", [MockChatService(error=ConnectionRefusedError(), fail_at="sources")]
)
async def test_failure_before_sources_sends_only_error(client: AsyncClient) -> None:
    response = await client.post("/chat", json={"question": "Hi"})

    assert event_types(response.text) == ["error"]


async def test_rate_limits_questions_per_client(app: FastAPI, client: AsyncClient) -> None:
    limiter = RateLimiter(limit=2)
    app.dependency_overrides[get_chat_rate_limiter] = lambda: limiter

    statuses = [(await client.post("/chat", json={"question": "Hi"})).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
async def test_rejects_invalid_question(client: AsyncClient, question: str) -> None:
    response = await client.post("/chat", json={"question": question})

    assert response.status_code == 422


def test_openapi_lists_stream_event_types(app: FastAPI) -> None:
    """Client generators read the 3.1 `schema`, not FastAPI's 3.2 `itemSchema`."""
    content = app.openapi()["paths"]["/chat"]["post"]["responses"]["200"]["content"]

    refs = [schema["$ref"] for schema in content["text/event-stream"]["schema"]["oneOf"]]

    events = ["SourcesEvent", "TokenEvent", "DoneEvent", "ErrorEvent"]
    assert refs == [f"#/components/schemas/{name}" for name in events]
