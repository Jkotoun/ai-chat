from collections.abc import AsyncIterator, Sequence

from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam


class LLMClient:
    """Streams chat completions from Groq."""

    def __init__(self, client: AsyncGroq, model: str) -> None:
        self._client = client
        self._model = model

    async def stream(self, messages: Sequence[ChatCompletionMessageParam]) -> AsyncIterator[str]:
        """Yield the answer's text deltas as they arrive."""
        if not self._client.api_key:
            # Otherwise the SDK reports a misleading, retried "Connection error".
            raise RuntimeError("GROQ_API_KEY is not set")
        stream = await self._client.chat.completions.create(
            model=self._model, messages=list(messages), stream=True, temperature=0.2
        )
        async with stream:
            async for chunk in stream:
                if chunk.choices and (delta := chunk.choices[0].delta.content):
                    yield delta
