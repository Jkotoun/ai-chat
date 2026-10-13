import secrets
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SupportTicket

# No 0/O or 1/I, so references are easy to read out and type.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
REFERENCE_LENGTH = 8


def new_reference() -> str:
    """A random, unguessable reference like `SUP-7K3QX9AB`."""
    return "SUP-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


async def create_ticket(
    session: AsyncSession,
    *,
    contact_email: str,
    summary: str,
    transcript: Sequence[dict[str, str]],
) -> SupportTicket:
    """Add an open ticket. The caller commits."""
    ticket = SupportTicket(
        reference=new_reference(),
        contact_email=contact_email,
        summary=summary,
        transcript=list(transcript),
    )
    session.add(ticket)
    await session.flush()
    return ticket
