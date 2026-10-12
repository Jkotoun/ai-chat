"""FastAPI dependencies exposing the resources created in the app lifespan."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
