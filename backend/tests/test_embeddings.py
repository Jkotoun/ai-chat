import asyncio
import math
import threading

import pytest

from app.db.models import EMBEDDING_DIM
from app.services.embeddings import EMBEDDING_QUERY_INSTRUCTION, Embedder
from tests.mocks import MockModel, make_embedder


async def test_inference_runs_off_the_event_loop_thread() -> None:
    model = MockModel()
    embedder = make_embedder(model)

    query = await embedder.embed_query("hi")
    docs = await embedder.embed_documents(["a", "b"])

    assert query == [1.0] * EMBEDDING_DIM
    assert docs == [[1.0] * EMBEDDING_DIM, [2.0] * EMBEDDING_DIM]
    assert all(isinstance(x, float) for x in query)
    assert threading.get_ident() not in model.threads
    assert len(model.threads) == 2


async def test_query_gets_retrieval_instruction_documents_do_not() -> None:
    model = MockModel()
    embedder = make_embedder(model)

    await embedder.embed_query("hi")
    await embedder.embed_documents(["doc"])

    assert model.inputs == [[EMBEDDING_QUERY_INSTRUCTION + "hi"], ["doc"]]


async def test_embed_documents_empty_skips_model() -> None:
    model = MockModel()

    assert await make_embedder(model).embed_documents([]) == []
    assert model.threads == []


async def test_embed_documents_rejects_bare_string() -> None:
    with pytest.raises(TypeError):
        await make_embedder(MockModel()).embed_documents("hello")


def test_rejects_model_with_wrong_dimension() -> None:
    with pytest.raises(ValueError, match="768-dim"):
        make_embedder(MockModel(dim=768))


@pytest.fixture(scope="module")
def real_embedder() -> Embedder:
    return asyncio.run(Embedder.load())


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (math.hypot(*a) * math.hypot(*b))


async def test_real_model_ranks_relevant_passage_higher(real_embedder: Embedder) -> None:
    """Downloads the model on first run (~70 MB, cached afterwards)."""
    query = await real_embedder.embed_query("How do I reset my password?")
    relevant, unrelated = await real_embedder.embed_documents(
        [
            "To reset your password, click 'Forgot password' on the login page.",
            "Our offices are closed on public holidays.",
        ]
    )

    assert len(query) == EMBEDDING_DIM
    assert cosine(query, relevant) > cosine(query, unrelated)
