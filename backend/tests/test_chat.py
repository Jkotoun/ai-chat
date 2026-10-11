import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import groq
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat import get_embedder, get_llm, get_session_factory
from app.main import app
from app.services.chat import build_messages
from app.services.llm import LLMClient
from app.services.retrieval import RetrievedDocument
from tests.db import add_documents
from tests.mocks import MockLLM, MockModel, make_embedder, unit_vector


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM(["Click ", "Forgot password."])


@pytest.fixture
def overrides(db_session: AsyncSession, mock_llm: MockLLM) -> Iterator[None]:
    """Mock embedder and LLM; DB access goes through the rolled-back test session."""

    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    model = MockModel(vectors={"How do I reset my password?": unit_vector(1, 0)})
    app.dependency_overrides[get_embedder] = lambda: make_embedder(model)
    app.dependency_overrides[get_llm] = lambda: mock_llm
    app.dependency_overrides[get_session_factory] = lambda: test_session
    yield
    app.dependency_overrides.clear()


async def test_streams_sources_then_tokens(
    client: AsyncClient, db_session: AsyncSession, mock_llm: MockLLM, overrides: None
) -> None:
    await add_documents(db_session, {"Reset password": unit_vector(1, 0)})

    response = await client.post("/chat", json={"question": " How do I reset my password? "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [e for e, _ in events] == ["sources", "token", "token", "done"]
    [source] = events[0][1]
    assert source["title"] == "Reset password"
    assert source["source"] == "faq"
    assert source["score"] == pytest.approx(1.0)
    assert "".join(data for event, data in events if event == "token") == "Click Forgot password."
    assert mock_llm.messages[-1] == {"role": "user", "content": "How do I reset my password?"}
    assert "Reset password content" in str(mock_llm.messages[0]["content"])


@pytest.mark.parametrize("mock_llm", [MockLLM(["Partial "], error=RuntimeError("boom"))])
async def test_llm_failure_ends_stream_with_error_event(
    client: AsyncClient, db_session: AsyncSession, overrides: None
) -> None:
    await add_documents(db_session, {"Doc": unit_vector(1, 0)})

    response = await client.post("/chat", json={"question": "How do I reset my password?"})

    events = parse_sse(response.text)
    assert [e for e, _ in events] == ["sources", "token", "error"]
    assert "boom" not in response.text


async def test_failure_before_sources_sends_only_error(
    client: AsyncClient, db_session: AsyncSession, overrides: None
) -> None:
    @asynccontextmanager
    async def broken_session() -> AsyncIterator[AsyncSession]:
        raise ConnectionRefusedError
        yield db_session

    app.dependency_overrides[get_session_factory] = lambda: broken_session

    response = await client.post("/chat", json={"question": "How do I reset my password?"})

    assert [e for e, _ in parse_sse(response.text)] == ["error"]


async def test_llm_client_without_api_key_fails_clearly() -> None:
    async with groq.AsyncGroq(api_key="") as client:
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            [d async for d in LLMClient(client, "m").stream([])]


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
async def test_rejects_invalid_question(client: AsyncClient, question: str) -> None:
    response = await client.post("/chat", json={"question": question})

    assert response.status_code == 422


def test_build_messages_puts_documents_in_system_prompt() -> None:
    doc = RetrievedDocument(id=1, source="tos", title="6. Refunds", content="14 days.", score=0.9)

    system, user = build_messages("Refund?", [doc])

    assert 'title="6. Refunds"' in str(system["content"])
    assert "14 days." in str(system["content"])
    assert user == {"role": "user", "content": "Refund?"}


def test_build_messages_without_documents() -> None:
    system, _ = build_messages("Hi", [])

    assert "(none)" in str(system["content"])


def groq_stream(*contents: str) -> str:
    chunks = [
        {
            "id": "c1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": {"content": c}, "finish_reason": None}],
        }
        for c in contents
    ]
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


async def test_llm_client_yields_deltas_from_groq_stream() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, text=groq_stream("Hel", "", "lo"), headers={"content-type": "text/event-stream"}
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with groq.AsyncGroq(api_key="test", http_client=http) as client:
        llm = LLMClient(client, model="test-model")
        deltas = [d async for d in llm.stream([{"role": "user", "content": "hi"}])]

    assert deltas == ["Hel", "lo"]
    body = json.loads(requests[0].content)
    assert body["model"] == "test-model"
    assert body["stream"] is True
