from collections.abc import AsyncIterator
from typing import Annotated, Literal, get_args

import structlog
from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.deps import ChatServiceDep, limit_chat_rate
from app.services.chat import ChatTurn

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


class DoneEvent(ChatEventBase):
    type: Literal["done"] = "done"


class ErrorEvent(ChatEventBase):
    type: Literal["error"] = "error"
    detail: str


ChatEvent = Annotated[
    SourcesEvent | TokenEvent | DoneEvent | ErrorEvent, Field(discriminator="type")
]


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
    the rest if something fails mid-stream.
    """
    try:
        documents = await chat_service.find_sources(body.question)
        yield SourcesEvent(
            sources=[Source.model_validate(d, from_attributes=True) for d in documents]
        )
        history = [ChatTurn(role=m.role, content=m.content) for m in body.history]
        async for delta in chat_service.stream_answer(body.question, documents, history):
            yield TokenEvent(text=delta)
    except Exception:
        # Headers are already sent, so report the failure in-band.
        logger.exception("chat_failed")
        yield ErrorEvent(detail="Something went wrong, please try again.")
        return
    yield DoneEvent()
