import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR
from app.db.models import Document
from app.ingest import ingest, load_directory
from app.services.embeddings import Embedder
from app.services.retrieval import MAX_K, TOP_K, retrieve
from tests.mocks import MockModel, make_embedder, unit_vector


async def clear_documents(session: AsyncSession) -> None:
    """Empty the table within the test's rolled-back transaction, so dev data doesn't interfere.

    HNSW would still visit the deleted (invisible) dev rows and return fewer than k
    results, so force exact search.
    """
    await session.execute(text("SET LOCAL enable_indexscan = off"))
    await session.execute(delete(Document))


async def add_documents(session: AsyncSession, embeddings: dict[str, list[float]]) -> None:
    await clear_documents(session)
    session.add_all(
        Document(source="faq", title=title, content=f"{title} content", embedding=embedding)
        for title, embedding in embeddings.items()
    )
    await session.flush()


async def test_returns_top_k_by_cosine_similarity(db_session: AsyncSession) -> None:
    """Integration test: needs Postgres with migrations applied."""
    await add_documents(
        db_session,
        {
            "exact": unit_vector(1, 0),
            "close": unit_vector(1, 1),
            "orthogonal": unit_vector(0, 1),
            "opposite": unit_vector(-1, 0),
        },
    )
    embedder = make_embedder(MockModel(vectors={"question": unit_vector(1, 0)}))

    results = await retrieve(db_session, embedder, "question", k=3)

    assert [r.title for r in results] == ["exact", "close", "orthogonal"]
    assert [r.score for r in results] == pytest.approx([1.0, 2**-0.5, 0.0], abs=1e-6)
    assert results[0].content == "exact content"
    assert results[0].source == "faq"


async def test_defaults_to_top_5(db_session: AsyncSession) -> None:
    await add_documents(db_session, {f"doc{i}": unit_vector(1, i) for i in range(TOP_K + 2)})
    embedder = make_embedder(MockModel(vectors={"q": unit_vector(1, 0)}))

    results = await retrieve(db_session, embedder, "q")

    assert [r.title for r in results] == [f"doc{i}" for i in range(TOP_K)]


@pytest.mark.parametrize(("query", "k"), [("q", 0), ("q", MAX_K + 1), ("  ", TOP_K)])
async def test_rejects_invalid_arguments(db_session: AsyncSession, query: str, k: int) -> None:
    with pytest.raises(ValueError):
        await retrieve(db_session, make_embedder(), query, k=k)


async def test_sample_data_answers_paraphrased_questions(db_session: AsyncSession) -> None:
    """End to end with the real model over the sample data."""
    embedder = await Embedder.load()
    await clear_documents(db_session)
    await ingest(db_session, embedder, *load_directory(BACKEND_DIR / "data"))

    refund = await retrieve(db_session, embedder, "Can I get my money back?")
    deleted = await retrieve(db_session, embedder, "I removed a file by accident, help")

    assert "Can I get a refund?" in [r.title for r in refund[:2]]
    assert deleted[0].title == "Can I restore a deleted file?"
