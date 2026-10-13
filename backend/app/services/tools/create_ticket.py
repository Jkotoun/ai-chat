"""Hands the conversation over to human support by creating a ticket."""

from dataclasses import asdict, dataclass

import structlog
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import TICKET_SUMMARY_MAX_LENGTH
from app.services.tickets import create_ticket
from app.services.tools.base import Tool, ToolContext, ToolError, ToolEvent, ToolResult

logger = structlog.get_logger()


class CreateTicketArgs(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=TICKET_SUMMARY_MAX_LENGTH,
        description="One paragraph for the support agent: what the user needs help with.",
    )
    contact_email: EmailStr = Field(description="The email address the user gave.")


@dataclass(frozen=True)
class TicketCreated(ToolEvent):
    reference: str


class CreateTicketTool(Tool[CreateTicketArgs]):
    name = "create_ticket"
    description = (
        "Create a support ticket so a human agent contacts the user by email. "
        "Call it only after the user asked for a human and gave their email address."
    )
    instructions = f"""\
If you can't answer from the context, offer to create a support ticket so a human can help.
If the user asks to talk to a human, escalate, or contact support, offer to create a \
support ticket. You need their email address: ask for it if they haven't written it \
in this conversation, and never guess it. Then call `{name}` with a short summary of \
their problem. Only say a ticket was created if the tool returned its reference, and \
tell the user that reference."""
    args_model = CreateTicketArgs

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, args: CreateTicketArgs, context: ToolContext) -> ToolResult:
        # Guards against an address the model made up or took from its own messages.
        if args.contact_email.lower() not in context.user_text().lower():
            raise ToolError("contact_email must be an address the user wrote; ask them for it")
        async with self._session_factory.begin() as session:
            ticket = await create_ticket(
                session,
                contact_email=args.contact_email,
                summary=args.summary,
                transcript=[asdict(t) for t in context.transcript],
            )
            reference = ticket.reference
        logger.info("ticket_created", reference=reference)
        return ToolResult({"reference": reference}, event=TicketCreated(reference))
