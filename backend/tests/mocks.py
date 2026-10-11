import threading
from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any, cast

import numpy as np
from fastembed import TextEmbedding
from groq.types.chat import ChatCompletionMessageParam

from app.db.models import EMBEDDING_DIM, EMBEDDING_QUERY_INSTRUCTION
from app.services.embeddings import Embedder


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


class MockLLM:
    """Stand-in for LLMClient; streams fixed deltas, optionally failing midway."""

    def __init__(self, deltas: list[str], error: Exception | None = None) -> None:
        self.deltas = deltas
        self.error = error
        self.messages: list[ChatCompletionMessageParam] = []

    async def stream(self, messages: Sequence[ChatCompletionMessageParam]) -> AsyncIterator[str]:
        self.messages = list(messages)
        for delta in self.deltas:
            yield delta
        if self.error:
            raise self.error
