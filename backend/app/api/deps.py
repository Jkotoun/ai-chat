"""FastAPI dependencies exposing the resources created in the app lifespan."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.rate_limit import RateLimiter
from app.services.chat import ChatService
from app.services.embeddings import Embedder
from app.services.llm import LLMClient


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.state.session_factory
    return session_factory


def get_embedder(request: Request) -> Embedder:
    embedder: Embedder = request.state.embedder
    return embedder


def get_llm(request: Request) -> LLMClient:
    llm: LLMClient = request.state.llm
    return llm


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]


async def get_session(session_factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    """A session per request."""
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_chat_service(
    session_factory: SessionFactoryDep, embedder: EmbedderDep, llm: LLMDep
) -> ChatService:
    return ChatService(session_factory, embedder, llm)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_chat_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.state.chat_rate_limiter
    return limiter


def limit_chat_rate(
    request: Request, limiter: Annotated[RateLimiter, Depends(get_chat_rate_limiter)]
) -> None:
    """Reject the request with 429 when its client is over the limit."""
    client = request.client.host if request.client else "unknown"
    if not limiter.hit(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many questions, please wait a minute.",
            headers={"Retry-After": str(int(limiter.window_seconds))},
        )
