from collections.abc import AsyncIterator, Sequence
from xml.sax.saxutils import quoteattr

from groq.types.chat import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.embeddings import Embedder
from app.services.llm import LLMClient
from app.services.retrieval import RetrievedDocument, retrieve

SYSTEM_PROMPT = """\
You are a customer support assistant.
Answer the user's question using only the context documents below.
If the context does not contain the answer, say that you don't know and suggest \
contacting human support. Do not make up information.
Keep answers short and friendly."""


def build_messages(
    question: str, documents: Sequence[RetrievedDocument]
) -> list[ChatCompletionMessageParam]:
    context = "\n\n".join(
        f"<document source={quoteattr(d.source)} title={quoteattr(d.title)}>\n"
        f"{d.content}\n</document>"
        for d in documents
    )
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context or '(none)'}"},
        {"role": "user", "content": question},
    ]


class ChatService:
    """Answers questions from the knowledge base."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: Embedder,
        llm: LLMClient,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._llm = llm

    async def find_sources(self, question: str) -> list[RetrievedDocument]:
        # Short-lived session, so no DB connection is held while the LLM streams.
        async with self._session_factory() as session:
            return await retrieve(session, self._embedder, question)

    def stream_answer(
        self, question: str, documents: Sequence[RetrievedDocument]
    ) -> AsyncIterator[str]:
        """The answer's text deltas, grounded in `documents`."""
        return self._llm.stream(build_messages(question, documents))
