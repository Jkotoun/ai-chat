from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, StringConstraints
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


def get_embedder(request: Request) -> Embedder:
    embedder: Embedder = request.state.embedder
    return embedder


def get_llm(request: Request) -> LLMClient:
    llm: LLMClient = request.state.llm
    return llm


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.state.session_factory
    return session_factory


@router.post("/chat", response_class=EventSourceResponse)
async def chat(
    body: ChatRequest,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[ServerSentEvent]:
    """Answer from the knowledge base, streamed as SSE.

    Events: `sources` (list of Source), then `token` per text delta, then `done`;
    `error` replaces the rest if something fails mid-stream.
    """
    try:
        # Short-lived session, so no DB connection is held while the LLM streams.
        async with session_factory() as session:
            documents = await retrieve(session, embedder, body.question)
        yield ServerSentEvent(
            event="sources",
            data=[
                Source(id=d.id, source=d.source, title=d.title, score=d.score) for d in documents
            ],
        )
        async for delta in llm.stream(build_messages(body.question, documents)):
            yield ServerSentEvent(event="token", data=delta)
    except Exception:
        # Headers are already sent, so report the failure in-band.
        logger.exception("chat_failed")
        yield ServerSentEvent(
            event="error", data={"detail": "Something went wrong, please try again."}
        )
        return
    yield ServerSentEvent(event="done", data={})
