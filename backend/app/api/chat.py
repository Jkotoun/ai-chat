from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any, Literal, get_args

import structlog
from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.deps import ChatServiceDep, limit_chat_rate
from app.services.chat import AnswerEvent
from app.services.conversation import ChatTurn
from app.services.llm import TextDelta
from app.services.tools.create_ticket import TicketCreated

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])

MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_LENGTH = 4000


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=MAX_HISTORY_CONTENT_LENGTH)]


class ChatRequest(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    # Earlier messages, oldest first; the server keeps no conversation state.
    history: Annotated[list[HistoryMessage], Field(max_length=MAX_HISTORY_MESSAGES)] = []


class Source(BaseModel):
    id: int
    source: str
    title: str
    score: float


class ChatEventBase(BaseModel):
    # Keeps the `type` tags required in the OpenAPI schema even though they have defaults.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class SourcesEvent(ChatEventBase):
    type: Literal["sources"] = "sources"
    sources: list[Source]


class TokenEvent(ChatEventBase):
    type: Literal["token"] = "token"
    text: str


class TicketEvent(ChatEventBase):
    type: Literal["ticket"] = "ticket"
    reference: str


class DoneEvent(ChatEventBase):
    type: Literal["done"] = "done"


class ErrorEvent(ChatEventBase):
    type: Literal["error"] = "error"
    detail: str


ChatEvent = Annotated[
    SourcesEvent | TokenEvent | TicketEvent | DoneEvent | ErrorEvent, Field(discriminator="type")
]


# How each event of the chat service is sent to the client, by exact type.
SSE_EVENTS: dict[type[AnswerEvent], Callable[[Any], TokenEvent | TicketEvent]] = {
    TextDelta: lambda delta: TokenEvent(text=delta.text),
    TicketCreated: lambda ticket: TicketEvent(reference=ticket.reference),
}


def to_sse_event(event: AnswerEvent) -> TokenEvent | TicketEvent | None:
    """The client event for `event`, or None if it has no mapping in `SSE_EVENTS`."""
    convert = SSE_EVENTS.get(type(event))
    if convert is None:
        logger.warning("answer_event_not_sent", event_type=type(event).__name__)
        return None
    return convert(event)


def chat_event_models() -> tuple[type[ChatEventBase], ...]:
    """The event models in the `ChatEvent` union."""
    union, _discriminator = get_args(ChatEvent)
    return get_args(union)


# FastAPI only describes the stream items with OpenAPI 3.2's `itemSchema`, which client
# generators don't read yet, so the plain 3.1 `schema` lists the event types too.
STREAM_SCHEMA = {
    "oneOf": [{"$ref": f"#/components/schemas/{model.__name__}"} for model in chat_event_models()]
}


@router.post(
    "/chat",
    response_class=EventSourceResponse,
    dependencies=[Depends(limit_chat_rate)],
    responses={200: {"content": {"text/event-stream": {"schema": STREAM_SCHEMA}}}},
)
async def chat(body: ChatRequest, chat_service: ChatServiceDep) -> AsyncIterator[ChatEvent]:
    """Answer from the knowledge base, streamed as SSE.

    Sends `sources`, then a `token` per text delta, then `done`; `error` replaces
    the rest if something fails mid-stream. A `ticket` event comes before the
    tokens that confirm it when the user was handed over to human support.
    """
    try:
        documents = await chat_service.find_sources(body.question)
        yield SourcesEvent(
            sources=[Source.model_validate(d, from_attributes=True) for d in documents]
        )
        history = [ChatTurn(role=m.role, content=m.content) for m in body.history]
        async for event in chat_service.stream_answer(body.question, documents, history):
            if sse_event := to_sse_event(event):
                yield sse_event
    except Exception:
        # Headers are already sent, so report the failure in-band.
        logger.exception("chat_failed")
        yield ErrorEvent(detail="Something went wrong, please try again.")
        return
    yield DoneEvent()
