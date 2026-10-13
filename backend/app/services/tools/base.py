"""What the chat needs from a tool the LLM can call."""

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import structlog
from groq.types.chat import ChatCompletionToolParam
from pydantic import BaseModel, ValidationError

from app.services.conversation import ChatTurn

logger = structlog.get_logger()


@dataclass(frozen=True)
class ToolContext:
    """The conversation the tool was called in, ending with the current question."""

    transcript: Sequence[ChatTurn]

    def user_text(self) -> str:
        return "\n".join(t.content for t in self.transcript if t.role == "user")


class ToolEvent:
    """Base for things a tool did that the user should see, e.g. a created ticket."""


@dataclass(frozen=True)
class ToolResult:
    """`content` goes back to the model; `event`, if any, goes to the user."""

    content: dict[str, str]
    event: ToolEvent | None = None

    @classmethod
    def error(cls, message: str) -> ToolResult:
        return cls({"error": message})

    @property
    def is_error(self) -> bool:
        return "error" in self.content

    def to_json(self) -> str:
        return json.dumps(self.content)


class ToolError(Exception):
    """The call can't be carried out; the message is meant for the model."""


class Tool[Args: BaseModel](ABC):
    """A function the LLM can call; subclasses set the attributes and implement `execute`."""

    name: str
    description: str
    instructions: str  # added to the system prompt: when and how to use the tool
    args_model: type[Args]

    @property
    def definition(self) -> ChatCompletionToolParam:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    async def run(self, arguments: str, context: ToolContext) -> ToolResult:
        """Validate the model's JSON `arguments` and execute; problems become error results."""
        try:
            args = self.args_model.model_validate_json(arguments or "{}")
        except ValidationError as exc:
            return self._reject(validation_message(exc))
        try:
            return await self.execute(args, context)
        except ToolError as exc:
            return self._reject(str(exc))

    @abstractmethod
    async def execute(self, args: Args, context: ToolContext) -> ToolResult: ...

    def _reject(self, reason: str) -> ToolResult:
        logger.info("tool_call_rejected", tool=self.name, reason=reason)
        return ToolResult.error(reason)


def validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()
    )
