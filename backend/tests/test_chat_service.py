from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chat import ChatService, ChatTurn, build_messages
from app.services.llm import LLMClient, ToolCall
from app.services.retrieval import RetrievedDocument
from tests.db import add_documents
from tests.mocks import MockLLM, MockModel, make_embedder, unit_vector


async def test_answers_from_retrieved_documents(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Integration test: needs Postgres with migrations applied."""
    await add_documents(
        db_session, {"Reset password": unit_vector(1, 0), "Refunds": unit_vector(0, 1)}
    )
    embedder = make_embedder(MockModel(vectors={"How do I reset?": unit_vector(1, 0)}))
    llm = MockLLM(["Click ", "Forgot password."])
    service = ChatService(db_session_factory, embedder, cast(LLMClient, llm))

    documents = await service.find_sources("How do I reset?")
    deltas = [d async for d in service.stream_answer("How do I reset?", documents)]

    assert documents[0].title == "Reset password"
    assert deltas == ["Click ", "Forgot password."]
    assert "Reset password content" in str(llm.messages[0]["content"])
    assert llm.messages[-1] == {"role": "user", "content": "How do I reset?"}


async def test_stream_answer_yields_only_text(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm = MockLLM(["Hi", ToolCall("call_1", "create_ticket", "{}")])
    service = ChatService(db_session_factory, make_embedder(), cast(LLMClient, llm))

    deltas = [d async for d in service.stream_answer("Hi", [])]

    assert deltas == ["Hi"]


def test_build_messages_puts_documents_in_system_prompt() -> None:
    doc = RetrievedDocument(id=1, source="tos", title="6. Refunds", content="14 days.", score=0.9)

    system, user = build_messages("Refund?", [doc])

    assert 'title="6. Refunds"' in str(system["content"])
    assert "14 days." in str(system["content"])
    assert user == {"role": "user", "content": "Refund?"}


def test_build_messages_puts_history_before_question() -> None:
    history = [ChatTurn("user", "Hi"), ChatTurn("assistant", "Hello!")]

    _, *rest = build_messages("Refunds?", [], history)

    assert rest == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "Refunds?"},
    ]


def test_build_messages_without_documents() -> None:
    system, _ = build_messages("Hi", [])

    assert "(none)" in str(system["content"])


def test_build_messages_quotes_titles() -> None:
    doc = RetrievedDocument(id=1, source="faq", title='Say "hi"', content="Hi.", score=0.9)

    system, _ = build_messages("Hi", [doc])

    assert """title='Say "hi"'""" in str(system["content"])
