from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.services.embeddings import Embedder

TOP_K = 5
# pgvector's HNSW scan returns at most hnsw.ef_search (default 40) rows.
MAX_K = 40


@dataclass(frozen=True)
class RetrievedDocument:
    id: int
    source: str
    title: str
    content: str
    score: float  # cosine similarity, higher is closer


async def retrieve(
    session: AsyncSession, embedder: Embedder, query: str, k: int = TOP_K
) -> list[RetrievedDocument]:
    """Top-k documents by cosine similarity to the query."""
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k must be between 1 and {MAX_K}, got {k}")
    if not query.strip():
        raise ValueError("query must not be blank")
    query_embedding = await embedder.embed_query(query)
    distance = Document.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Document.id, Document.source, Document.title, Document.content, distance)
        .order_by(distance)  # a second sort key would stop pgvector from using the HNSW index
        .limit(k)
    )
    return [
        RetrievedDocument(id=id_, source=source, title=title, content=content, score=1 - dist)
        for id_, source, title, content, dist in await session.execute(stmt)
    ]
