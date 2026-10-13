from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Must match the embedding model's output size; changing it needs a migration.
EMBEDDING_DIM = 384
TITLE_MAX_LENGTH = 512
TICKET_SUMMARY_MAX_LENGTH = 1000
# RFC 5321 limit for an address
EMAIL_MAX_LENGTH = 320


class DocumentSource(StrEnum):
    FAQ = "faq"
    TOS = "tos"


class Document(Base):
    """A knowledge base entry: one FAQ Q&A pair or one ToS section."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # a DocumentSource
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
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


class TicketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class SupportTicket(Base):
    """A request from a chat user to be contacted by human support."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True)  # shown to the user
    status: Mapped[str] = mapped_column(String(16), default=TicketStatus.OPEN)  # a TicketStatus
    contact_email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    summary: Mapped[str] = mapped_column(String(TICKET_SUMMARY_MAX_LENGTH))
    transcript: Mapped[list[dict[str, str]]] = mapped_column(JSONB)  # [{"role", "content"}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
