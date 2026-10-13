import json
from dataclasses import dataclass
from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chat import AnswerEvent, ChatService, build_messages
from app.services.conversation import ChatTurn
from app.services.llm import LLMClient, TextDelta, ToolCall
from app.services.retrieval import RetrievedDocument
from app.services.tools.base import Tool, ToolContext, ToolError, ToolEvent, ToolResult
from tests.db import add_documents
from tests.mocks import MockLLM, MockModel, make_embedder, unit_vector


async def test_answers_from_retrieved_documents(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Integration test: needs Postgres with migrations applied."""
    await add_documents(
        db_session, {"Reset password": unit_vector(1, 0), "Refunds": unit_vector(0, 1)}
    )
    embedder = make_embedder(MockModel(vectors={"How do I reset?": unit_vector(1, 0)}))
    llm = MockLLM(["Click ", "Forgot password."])
    service = ChatService(db_session_factory, embedder, cast(LLMClient, llm))

    documents = await service.find_sources("How do I reset?")
    events = [e async for e in service.stream_answer("How do I reset?", documents)]

    assert documents[0].title == "Reset password"
    assert texts(events) == ["Click ", "Forgot password."]
    assert "Reset password content" in str(llm.messages[0]["content"])
    assert llm.messages[-1] == {"role": "user", "content": "How do I reset?"}


def texts(events: list[AnswerEvent]) -> list[str]:
    return [e.text for e in events if isinstance(e, TextDelta)]


class EchoArgs(BaseModel):
    text: str


@dataclass(frozen=True)
class Echoed(ToolEvent):
    text: str


class EchoTool(Tool[EchoArgs]):
    """Repeats its argument; refuses to echo "fail"."""

    name = "echo"
    description = "Echo the text."
    instructions = "Use echo to repeat things."
    args_model = EchoArgs

    def __init__(self) -> None:
        self.contexts: list[ToolContext] = []

    async def execute(self, args: EchoArgs, context: ToolContext) -> ToolResult:
        self.contexts.append(context)
        if args.text == "fail":
            raise ToolError("cannot echo that")
        return ToolResult({"echoed": args.text}, event=Echoed(args.text))


def echo_call(text: str = "hi", id: str = "call_1") -> ToolCall:
    return ToolCall(id=id, name="echo", arguments=json.dumps({"text": text}))


def make_service(llm: MockLLM, tool: EchoTool) -> ChatService:
    session_factory = cast(async_sessionmaker[AsyncSession], None)  # retrieval isn't used
    return ChatService(session_factory, make_embedder(), cast(LLMClient, llm), [tool])


def tool_message_content(llm: MockLLM, index: int = -1) -> dict[str, str]:
    content: dict[str, str] = json.loads(str(llm.calls[1].messages[index]["content"]))
    return content


HISTORY = [ChatTurn("user", "Hi"), ChatTurn("assistant", "Hello!")]


async def test_answer_without_tool_calls_makes_one_llm_call() -> None:
    llm, tool = MockLLM(["Hi"]), EchoTool()

    events = [e async for e in make_service(llm, tool).stream_answer("Hi", [])]

    assert events == [TextDelta("Hi")]
    assert len(llm.calls) == 1
    assert llm.calls[0].tools == [tool.definition]
    assert tool.instructions in str(llm.messages[0]["content"])


async def test_tool_call_yields_its_event_and_continues_answer() -> None:
    llm, tool = MockLLM(["One moment. ", echo_call()], ["Done."]), EchoTool()

    events = [e async for e in make_service(llm, tool).stream_answer("Echo hi", [], HISTORY)]

    assert events == [TextDelta("One moment. "), Echoed("hi"), TextDelta("Done.")]
    assert tool.contexts == [ToolContext([*HISTORY, ChatTurn("user", "Echo hi")])]
    follow_up = llm.calls[1]
    assert follow_up.tool_choice == "none"
    assert follow_up.messages[-2] == {
        "role": "assistant",
        "content": "One moment. ",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "echo", "arguments": echo_call().arguments},
            }
        ],
    }
    assert follow_up.messages[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": json.dumps({"echoed": "hi"}),
    }


@pytest.mark.parametrize(
    ("call", "error"),
    [
        (echo_call("fail"), "cannot echo that"),
        (ToolCall("call_1", "echo", "{}"), "text: Field required"),
        (ToolCall("call_1", "echo", "not json"), "Invalid JSON"),
        (ToolCall("call_1", "delete_account", "{}"), "unknown tool 'delete_account'"),
    ],
)
async def test_rejected_tool_call_reports_error_to_model(call: ToolCall, error: str) -> None:
    llm = MockLLM([call], ["Sorry."])

    events = [e async for e in make_service(llm, EchoTool()).stream_answer("Hi", [])]

    assert events == [TextDelta("Sorry.")]
    assert error in tool_message_content(llm)["error"]


async def test_each_tool_succeeds_once_per_answer() -> None:
    llm = MockLLM([echo_call("a", id="call_1"), echo_call("b", id="call_2")], ["Done."])

    events = [e async for e in make_service(llm, EchoTool()).stream_answer("Hi", [])]

    assert [e for e in events if isinstance(e, Echoed)] == [Echoed("a")]
    assert tool_message_content(llm) == {"error": "echo already ran for this message"}


def test_build_messages_puts_documents_in_system_prompt() -> None:
    doc = RetrievedDocument(id=1, source="tos", title="6. Refunds", content="14 days.", score=0.9)

    system, user = build_messages("Refund?", [doc])

    assert 'title="6. Refunds"' in str(system["content"])
    assert "14 days." in str(system["content"])
    assert user == {"role": "user", "content": "Refund?"}


def test_build_messages_puts_history_before_question() -> None:
    history = [ChatTurn("user", "Hi"), ChatTurn("assistant", "Hello!")]

    _, *rest = build_messages("Refunds?", [], history)

    assert rest == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "Refunds?"},
    ]


def test_build_messages_without_documents() -> None:
    system, _ = build_messages("Hi", [])

    assert "(none)" in str(system["content"])


def test_build_messages_quotes_titles() -> None:
    doc = RetrievedDocument(id=1, source="faq", title='Say "hi"', content="Hi.", score=0.9)

    system, _ = build_messages("Hi", [doc])

    assert """title='Say "hi"'""" in str(system["content"])
