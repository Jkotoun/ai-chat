from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from groq import AsyncGroq, omit
from groq.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolParam,
)
from groq.types.chat.chat_completion_chunk import ChoiceDelta, ChoiceDeltaToolCall


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON written by the model, not validated


type LLMEvent = TextDelta | ToolCall


@dataclass
class _ToolCallBuilder:
    """Assembles one tool call from its streamed fragments."""

    id: str = ""
    name: str = ""
    arguments: str = ""

    def add(self, fragment: ChoiceDeltaToolCall) -> None:
        # The id and name come once; the arguments come in pieces.
        self.id = fragment.id or self.id
        if fragment.function:
            self.name = fragment.function.name or self.name
            self.arguments += fragment.function.arguments or ""

    def build(self) -> ToolCall:
        return ToolCall(self.id, self.name, self.arguments)


class LLMClient:
    """Streams chat completions from Groq."""

    def __init__(self, client: AsyncGroq, model: str) -> None:
        self._client = client
        self._model = model

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        tools: Sequence[ChatCompletionToolParam] = (),
        tool_choice: ChatCompletionToolChoiceOptionParam | None = None,
    ) -> AsyncIterator[LLMEvent]:
        """Yield text deltas as they arrive, then the tool calls the model made, if any."""
        tool_calls: dict[int, _ToolCallBuilder] = {}
        async for delta in self._deltas(messages, tools, tool_choice):
            if delta.content:
                yield TextDelta(delta.content)
            for fragment in delta.tool_calls or []:
                tool_calls.setdefault(fragment.index, _ToolCallBuilder()).add(fragment)
        for _, call in sorted(tool_calls.items()):
            yield call.build()

    async def _deltas(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        tools: Sequence[ChatCompletionToolParam],
        tool_choice: ChatCompletionToolChoiceOptionParam | None,
    ) -> AsyncIterator[ChoiceDelta]:
        """The raw message deltas Groq streams back."""
        if not self._client.api_key:
            # Otherwise the SDK reports a misleading, retried "Connection error".
            raise RuntimeError("GROQ_API_KEY is not set")
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            tools=list(tools) or omit,
            tool_choice=tool_choice or omit,
            stream=True,
            temperature=0.2,
        )
        async with stream:
            async for chunk in stream:
                if chunk.choices:
                    yield chunk.choices[0].delta
