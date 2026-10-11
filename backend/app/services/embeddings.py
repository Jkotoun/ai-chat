import asyncio
from collections.abc import Sequence
from typing import Self

from fastembed import TextEmbedding

from app.db.models import EMBEDDING_DIM, EMBEDDING_MODEL, EMBEDDING_QUERY_INSTRUCTION

# Inputs are truncated to this many tokens; token_count() also caps at it.
MAX_TOKENS = 512


class Embedder:
    """Text embeddings via fastembed.

    Inference is sync and CPU-bound (onnxruntime releases the GIL), so it runs in a
    worker thread to keep the event loop free.
    """

    def __init__(self, model: TextEmbedding) -> None:
        if model.embedding_size != EMBEDDING_DIM:
            raise ValueError(
                f"{model.model_name} produces {model.embedding_size}-dim vectors, "
                f"the documents table expects {EMBEDDING_DIM}"
            )
        self._model = model

    @classmethod
    async def load(cls, model_name: str = EMBEDDING_MODEL) -> Self:
        """Load the model (downloads it on first use) without blocking the event loop."""
        model = await asyncio.to_thread(TextEmbedding, model_name)
        return cls(model)

    async def embed_query(self, query: str) -> list[float]:
        """Embed a search query, prefixed with the model's retrieval instruction."""
        return await asyncio.to_thread(self._embed_query, query)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts to be stored and searched over.

        The model truncates input at 512 tokens, so callers must chunk long texts.
        """
        if isinstance(texts, str):
            raise TypeError("embed_documents expects a sequence of texts, not a str")
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_documents, texts)

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        """Token count per text, capped at MAX_TOKENS (a count of MAX_TOKENS means truncated)."""
        return await asyncio.to_thread(lambda: [self._model.token_count(t) for t in texts])

    def _embed_query(self, query: str) -> list[float]:
        [vector] = self._model.embed([EMBEDDING_QUERY_INSTRUCTION + query])
        values: list[float] = vector.tolist()
        return values

    def _embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = [v.tolist() for v in self._model.embed(list(texts))]
        return vectors
