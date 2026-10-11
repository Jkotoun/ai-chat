from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Model and vector size are tied to the DB schema; changing either needs a migration.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
# Recommended by BAAI for bge v1.5 short-query-to-passage retrieval; fastembed doesn't add it.
EMBEDDING_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Document(Base):
    """A knowledge base entry: one FAQ Q&A pair or one ToS section."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # "faq" | "tos"
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_documents_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
