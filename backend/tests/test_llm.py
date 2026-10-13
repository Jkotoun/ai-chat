import json
from typing import Any

import groq
import httpx
import pytest
from groq.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from app.services.llm import LLMClient, LLMEvent, TextDelta, ToolCall

TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {"name": "create_ticket", "parameters": {"type": "object"}},
}


async def test_llm_client_without_api_key_fails_clearly() -> None:
    async with groq.AsyncGroq(api_key="") as client:
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            [d async for d in LLMClient(client, "m").stream([])]


def groq_stream(*deltas: str | dict[str, Any]) -> str:
    """An SSE body of chunks; a str is a content delta, a dict is a raw delta."""
    chunks = [
        {
            "id": "c1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": d} if isinstance(d, str) else d,
                    "finish_reason": None,
                }
            ],
        }
        for d in deltas
    ]
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def tool_call_delta(index: int, **fields: Any) -> dict[str, Any]:
    return {"tool_calls": [{"index": index, **fields}]}


async def stream_events(
    body: str, tools: list[ChatCompletionToolParam] | None = None
) -> tuple[list[LLMEvent], dict[str, Any]]:
    """The events LLMClient yields for a Groq response `body`, and the request it sent."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with groq.AsyncGroq(api_key="test", http_client=http) as client:
        llm = LLMClient(client, model="test-model")
        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "hi"}]
        events = [e async for e in llm.stream(messages, tools or [])]
    return events, json.loads(requests[0].content)


async def test_llm_client_yields_deltas_from_groq_stream() -> None:
    events, request = await stream_events(groq_stream("Hel", "", "lo"))

    assert events == [TextDelta("Hel"), TextDelta("lo")]
    assert request["model"] == "test-model"
    assert request["stream"] is True
    assert "tools" not in request


async def test_llm_client_assembles_fragmented_tool_calls() -> None:
    body = groq_stream(
        "Sure. ",
        tool_call_delta(
            0, id="call_1", type="function", function={"name": "create_ticket", "arguments": ""}
        ),
        tool_call_delta(
            1, id="call_2", type="function", function={"name": "other", "arguments": "{}"}
        ),
        tool_call_delta(0, function={"arguments": '{"a": '}),
        tool_call_delta(0, function={"arguments": "1}"}),
    )

    events, request = await stream_events(body, tools=[TOOL])

    assert events == [
        TextDelta("Sure. "),
        ToolCall(id="call_1", name="create_ticket", arguments='{"a": 1}'),
        ToolCall(id="call_2", name="other", arguments="{}"),
    ]
    assert request["tools"] == [TOOL]
