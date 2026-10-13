import threading
from collections.abc import AsyncIterator, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from fastembed import TextEmbedding
from groq.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolParam,
)

from app.db.models import EMBEDDING_DIM
from app.services.chat import AnswerEvent
from app.services.conversation import ChatTurn
from app.services.embeddings import EMBEDDING_QUERY_INSTRUCTION, Embedder
from app.services.llm import LLMEvent, TextDelta, ToolCall
from app.services.retrieval import RetrievedDocument


class MockModel:
    """Stand-in for fastembed's TextEmbedding; records inputs and the inference thread."""

    model_name = "mock"

    def __init__(self, dim: int = EMBEDDING_DIM, vectors: dict[str, list[float]] | None = None):
        self.embedding_size = dim
        self.vectors = vectors or {}  # fixed vectors by text (query instruction stripped)
        self.threads: list[int] = []
        self.inputs: list[list[str]] = []

    def embed(self, texts: list[str]) -> Iterable[np.ndarray[Any, Any]]:
        self.threads.append(threading.get_ident())
        self.inputs.append(texts)
        for i, text in enumerate(texts):
            if (key := text.removeprefix(EMBEDDING_QUERY_INSTRUCTION)) in self.vectors:
                yield np.array(self.vectors[key], dtype=np.float32)
            else:
                yield np.full(self.embedding_size, i + 1, dtype=np.float32)

    def token_count(self, text: str) -> int:
        return len(text.split())


def make_embedder(model: MockModel | None = None) -> Embedder:
    return Embedder(cast(TextEmbedding, model or MockModel()))


def unit_vector(*weights: float) -> list[float]:
    """Normalized EMBEDDING_DIM vector starting with `weights`, zero-padded."""
    norm = float(np.linalg.norm(weights))
    return [w / norm for w in weights] + [0.0] * (EMBEDDING_DIM - len(weights))


@dataclass
class LLMCall:
    messages: list[ChatCompletionMessageParam]
    tools: list[ChatCompletionToolParam]
    tool_choice: ChatCompletionToolChoiceOptionParam | None


class MockLLM:
    """Stand-in for LLMClient; each call streams the next scripted round, optionally failing."""

    def __init__(self, *rounds: list[str | ToolCall], error: Exception | None = None) -> None:
        self.rounds = list(rounds)
        self.error = error
        self.calls: list[LLMCall] = []

    @property
    def messages(self) -> list[ChatCompletionMessageParam]:
        """The messages of the first call."""
        return self.calls[0].messages

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        tools: Sequence[ChatCompletionToolParam] = (),
        tool_choice: ChatCompletionToolChoiceOptionParam | None = None,
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append(LLMCall(list(messages), list(tools), tool_choice))
        for event in self.rounds.pop(0):
            yield TextDelta(event) if isinstance(event, str) else event
        if self.error:
            raise self.error


class MockChatService:
    """Stand-in for ChatService; returns fixed sources and deltas, optionally failing."""

    def __init__(
        self,
        documents: list[RetrievedDocument] | None = None,
        deltas: list[str | AnswerEvent] | None = None,
        error: Exception | None = None,
        fail_at: Literal["sources", "answer"] = "answer",
    ) -> None:
        self.documents = documents or []
        self.deltas = deltas or []
        self.answer_error = error if fail_at == "answer" else None
        self.sources_error = error if fail_at == "sources" else None
        self.questions: list[str] = []
        self.histories: list[list[ChatTurn]] = []

    async def find_sources(self, question: str) -> list[RetrievedDocument]:
        self.questions.append(question)
        if self.sources_error:
            raise self.sources_error
        return self.documents

    def stream_answer(
        self,
        question: str,
        documents: Sequence[RetrievedDocument],
        history: Sequence[ChatTurn] = (),
    ) -> AsyncIterator[AnswerEvent]:
        self.histories.append(list(history))
        return self._stream()

    async def _stream(self) -> AsyncIterator[AnswerEvent]:
        for delta in self.deltas:
            yield TextDelta(delta) if isinstance(delta, str) else delta
        if self.answer_error:
            raise self.answer_error
