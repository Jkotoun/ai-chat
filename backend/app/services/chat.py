from collections.abc import Sequence

from groq.types.chat import ChatCompletionMessageParam

from app.services.retrieval import RetrievedDocument

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
        f'<document source="{d.source}" title="{d.title}">\n{d.content}\n</document>'
        for d in documents
    )
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context or '(none)'}"},
        {"role": "user", "content": question},
    ]
