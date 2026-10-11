from collections.abc import AsyncIterator
from typing import Annotated, Literal, get_args

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chat import build_messages
from app.services.embeddings import Embedder
from app.services.llm import LLMClient
from app.services.retrieval import retrieve

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


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


def get_embedder(request: Request) -> Embedder:
    embedder: Embedder = request.state.embedder
    return embedder


def get_llm(request: Request) -> LLMClient:
    llm: LLMClient = request.state.llm
    return llm


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.state.session_factory
    return session_factory


async def stream_answer(
    question: str,
    embedder: Embedder,
    llm: LLMClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SourcesEvent | TokenEvent]:
    """`sources` for the question, then a `token` per answer text delta."""
    # Short-lived session, so no DB connection is held while the LLM streams.
    async with session_factory() as session:
        documents = await retrieve(session, embedder, question)
    yield SourcesEvent(sources=[Source.model_validate(d, from_attributes=True) for d in documents])
    async for delta in llm.stream(build_messages(question, documents)):
        yield TokenEvent(text=delta)


# FastAPI only describes the stream items with OpenAPI 3.2's `itemSchema`, which client
# generators don't read yet, so the plain 3.1 `schema` lists the event types too.
STREAM_SCHEMA = {
    "oneOf": [{"$ref": f"#/components/schemas/{model.__name__}"} for model in chat_event_models()]
}


@router.post(
    "/chat",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {"schema": STREAM_SCHEMA}}}},
)
async def chat(
    body: ChatRequest,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[ChatEvent]:
    """Answer from the knowledge base, streamed as SSE.

    Sends `sources`, then a `token` per text delta, then `done`; `error` replaces
    the rest if something fails mid-stream.
    """
    try:
        async for event in stream_answer(body.question, embedder, llm, session_factory):
            yield event
    except Exception:
        # Headers are already sent, so report the failure in-band.
        logger.exception("chat_failed")
        yield ErrorEvent(detail="Something went wrong, please try again.")
        return
    yield DoneEvent()
