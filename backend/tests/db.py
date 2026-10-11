from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


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
