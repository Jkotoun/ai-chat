import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SupportTicket, TicketStatus
from app.services.tickets import create_ticket, new_reference

TRANSCRIPT = [{"role": "user", "content": "I want a human."}]


def test_new_reference_is_readable_and_random() -> None:
    references = {new_reference() for _ in range(100)}

    assert len(references) == 100
    assert all(re.fullmatch(r"SUP-[2-9A-HJ-NP-Z]{8}", r) for r in references)


async def test_create_ticket_stores_an_open_ticket(db_session: AsyncSession) -> None:
    """Integration test: needs Postgres with migrations applied."""
    ticket = await create_ticket(
        db_session, contact_email="a@example.com", summary="Refund", transcript=TRANSCRIPT
    )

    stored = await db_session.scalar(
        select(SupportTicket).where(SupportTicket.reference == ticket.reference)
    )
    assert stored is not None
    assert stored.status == TicketStatus.OPEN
    assert stored.contact_email == "a@example.com"
    assert stored.summary == "Refund"
    assert stored.transcript == TRANSCRIPT
