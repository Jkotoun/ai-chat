from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


async def use_exact_search(session: AsyncSession) -> None:
    """Rolled-back test inserts leave dead HNSW entries that can cut results below k."""
    await session.execute(text("SET LOCAL enable_indexscan = off"))


async def add_documents(session: AsyncSession, embeddings: dict[str, list[float]]) -> None:
    await use_exact_search(session)
    session.add_all(
        Document(source="faq", title=title, content=f"{title} content", embedding=embedding)
        for title, embedding in embeddings.items()
    )
    await session.flush()
