from collections.abc import AsyncIterator, Sequence
from typing import Any
from xml.sax.saxutils import quoteattr

from groq.types.chat import ChatCompletionMessageParam, ChatCompletionMessageToolCallParam
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.conversation import ChatTurn
from app.services.embeddings import Embedder
from app.services.llm import LLMClient, TextDelta, ToolCall
from app.services.retrieval import RetrievedDocument, retrieve
from app.services.tools.base import Tool, ToolContext, ToolEvent, ToolResult

SYSTEM_PROMPT = """\
You are a customer support assistant.
Answer the user's question using only the context documents below.
If the context does not contain the answer, say that you don't know. \
Do not make up information.
Keep answers short and friendly."""

type AnswerEvent = TextDelta | ToolEvent


def turn_message(turn: ChatTurn) -> ChatCompletionMessageParam:
    match turn.role:
        case "user":
            return {"role": "user", "content": turn.content}
        case "assistant":
            return {"role": "assistant", "content": turn.content}


def build_messages(
    question: str,
    documents: Sequence[RetrievedDocument],
    history: Sequence[ChatTurn] = (),
    instructions: Sequence[str] = (),
) -> list[ChatCompletionMessageParam]:
    """System prompt with tool `instructions` and the context, then history and question."""
    context = "\n\n".join(
        f"<document source={quoteattr(d.source)} title={quoteattr(d.title)}>\n"
        f"{d.content}\n</document>"
        for d in documents
    )
    system = "\n\n".join([SYSTEM_PROMPT, *instructions, f"Context:\n{context or '(none)'}"])
    return [
        {"role": "system", "content": system},
        *map(turn_message, history),
        {"role": "user", "content": question},
    ]


class ChatService:
    """Answers questions from the knowledge base, using `tools` when the model calls them."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: Embedder,
        llm: LLMClient,
        tools: Sequence[Tool[Any]] = (),
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._llm = llm
        self._tools = {tool.name: tool for tool in tools}

    async def find_sources(self, question: str) -> list[RetrievedDocument]:
        # Short-lived session, so no DB connection is held while the LLM streams.
        async with self._session_factory() as session:
            return await retrieve(session, self._embedder, question)

    async def stream_answer(
        self,
        question: str,
        documents: Sequence[RetrievedDocument],
        history: Sequence[ChatTurn] = (),
    ) -> AsyncIterator[AnswerEvent]:
        """Text deltas grounded in `documents`, plus the events of any tools the model calls.

        Allows one round of tool calls, then streams the model's answer to their results.
        """
        instructions = [tool.instructions for tool in self._tools.values()]
        definitions = [tool.definition for tool in self._tools.values()]
        messages = build_messages(question, documents, history, instructions)
        text = ""
        tool_calls: list[ToolCall] = []
        async for event in self._llm.stream(messages, definitions):
            match event:
                case TextDelta():
                    text += event.text
                    yield event
                case ToolCall():
                    tool_calls.append(event)
        if not tool_calls:
            return

        messages.append(assistant_tool_calls_message(text, tool_calls))
        context = ToolContext(transcript=[*history, ChatTurn("user", question)])
        succeeded: set[str] = set()
        for call in tool_calls:
            result = await self._run_tool(call, context, succeeded)
            if result.event:
                yield result.event
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result.to_json()})

        async for event in self._llm.stream(messages, definitions, tool_choice="none"):
            if isinstance(event, TextDelta):
                yield event

    async def _run_tool(
        self, call: ToolCall, context: ToolContext, succeeded: set[str]
    ) -> ToolResult:
        """Run the called tool; each tool may succeed once per answer."""
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult.error(f"unknown tool {call.name!r}")
        if call.name in succeeded:
            return ToolResult.error(f"{call.name} already ran for this message")
        result = await tool.run(call.arguments, context)
        if not result.is_error:
            succeeded.add(call.name)
        return result


def assistant_tool_calls_message(
    text: str, tool_calls: Sequence[ToolCall]
) -> ChatCompletionMessageParam:
    calls: list[ChatCompletionMessageToolCallParam] = [
        {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
        for c in tool_calls
    ]
    return {"role": "assistant", "content": text or None, "tool_calls": calls}
