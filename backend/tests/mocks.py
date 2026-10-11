import threading
from collections.abc import Iterable
from typing import Any, cast

import numpy as np
from fastembed import TextEmbedding

from app.db.models import EMBEDDING_DIM
from app.services.embeddings import Embedder


class MockModel:
    """Stand-in for fastembed's TextEmbedding; records inputs and the inference thread."""

    model_name = "mock"

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.embedding_size = dim
        self.threads: list[int] = []
        self.inputs: list[list[str]] = []

    def embed(self, texts: list[str]) -> Iterable[np.ndarray[Any, Any]]:
        self.threads.append(threading.get_ident())
        self.inputs.append(texts)
        for i, _ in enumerate(texts):
            yield np.full(self.embedding_size, i + 1, dtype=np.float32)

    def token_count(self, text: str) -> int:
        return len(text.split())


def make_embedder(model: MockModel | None = None) -> Embedder:
    return Embedder(cast(TextEmbedding, model or MockModel()))
