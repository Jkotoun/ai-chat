from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChatTurn:
    """A message of the conversation."""

    role: Literal["user", "assistant"]
    content: str
