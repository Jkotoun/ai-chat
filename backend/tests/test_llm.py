import json

import groq
import httpx
import pytest

from app.services.llm import LLMClient


async def test_llm_client_without_api_key_fails_clearly() -> None:
    async with groq.AsyncGroq(api_key="") as client:
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            [d async for d in LLMClient(client, "m").stream([])]


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
