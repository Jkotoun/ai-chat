from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal, Self, get_args

import structlog
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.chat import AnswerEvent
from app.services.conversation import ChatTurn
from app.services.llm import TextDelta
from app.services.retrieval import RetrievedDocument
from app.services.tools.create_ticket import TicketCreated

logger = structlog.get_logger()

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

    def chat_turns(self) -> list[ChatTurn]:
        return [ChatTurn(role=m.role, content=m.content) for m in self.history]


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

    @classmethod
    def from_documents(cls, documents: Sequence[RetrievedDocument]) -> Self:
        return cls(sources=[Source.model_validate(d, from_attributes=True) for d in documents])


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
