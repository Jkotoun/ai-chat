from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse

from app.api.deps import ChatServiceDep, limit_chat_rate
from app.api.schemas.chat import (
    STREAM_SCHEMA,
    ChatEvent,
    ChatRequest,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    to_sse_event,
)

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])


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
        yield SourcesEvent.from_documents(documents)
        stream = chat_service.stream_answer(body.question, documents, body.chat_turns())
        async for event in stream:
            if sse_event := to_sse_event(event):
                yield sse_event
    except Exception:
        # Headers are already sent, so report the failure in-band.
        logger.exception("chat_failed")
        yield ErrorEvent(detail="Something went wrong, please try again.")
        return
    yield DoneEvent()
