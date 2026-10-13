import json
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import SupportTicket
from app.services.conversation import ChatTurn
from app.services.tools.base import ToolContext, ToolResult
from app.services.tools.create_ticket import CreateTicketTool, TicketCreated

CONTEXT = ToolContext(
    [
        ChatTurn("user", "I want a refund."),
        ChatTurn("assistant", "What is your email? Or write to help@example.com."),
        ChatTurn("user", "It's Ann@Example.com, please get me a human."),
    ]
)


async def run(
    session_factory: async_sessionmaker[AsyncSession],
    email: str = "ann@example.com",
    summary: str = "Wants a refund.",
) -> ToolResult:
    arguments = json.dumps({"summary": summary, "contact_email": email})
    return await CreateTicketTool(session_factory).run(arguments, CONTEXT)


async def test_creates_ticket_with_transcript(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Integration test: needs Postgres with migrations applied."""
    result = await run(db_session_factory)

    reference = result.content["reference"]
    assert result.event == TicketCreated(reference)
    stored = await db_session.scalar(
        select(SupportTicket).where(SupportTicket.reference == reference)
    )
    assert stored is not None
    assert stored.contact_email == "ann@example.com"
    assert stored.summary == "Wants a refund."
    assert stored.transcript == [{"role": t.role, "content": t.content} for t in CONTEXT.transcript]


@pytest.mark.parametrize(
    "email",
    ["someone@example.com", "help@example.com"],
    ids=["made-up", "from-assistant-message"],
)
async def test_rejects_email_the_user_did_not_write(
    db_session_factory: async_sessionmaker[AsyncSession], email: str
) -> None:
    result = await run(db_session_factory, email=email)

    assert result.event is None
    assert "address the user wrote" in result.content["error"]


async def test_rejects_invalid_arguments(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    result = await run(db_session_factory, email="not-an-email", summary="")

    assert "summary" in result.content["error"]
    assert "contact_email" in result.content["error"]


def test_definition_describes_arguments() -> None:
    definition = CreateTicketTool(cast(async_sessionmaker[AsyncSession], None)).definition

    assert definition["function"]["name"] == "create_ticket"
    assert definition["function"]["parameters"]["required"] == ["summary", "contact_email"]
