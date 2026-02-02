"""Loop state machine for unified chat-agent loop.

Defines the state enum and related types for the UnifiedChatLoop.
"""

from enum import Enum


class LoopState(Enum):
    """State machine for the unified loop."""

    IDLE = "idle"
    """Waiting for user input."""

    CLASSIFYING = "classifying"
    """Analyzing intent."""

    CONVERSING = "conversing"
    """Generating chat response."""

    PLANNING = "planning"
    """Agent creating plan."""

    CONFIRMING = "confirming"
    """Awaiting user confirmation."""

    EXECUTING = "executing"
    """Running tasks."""

    INTERRUPTED = "interrupted"
    """User input during execution."""

    COMPLETED = "completed"
    """Goal finished."""

    ERROR = "error"
    """Unrecoverable error."""


# Maximum conversation history entries (user + assistant messages)
# 50 entries = ~25 turns, enough context without unbounded growth
MAX_HISTORY_SIZE = 50


def append_to_history(
    history: list[dict[str, str]],
    role: str,
    content: str,
) -> None:
    """Append message to conversation history and trim if needed.

    This helper ensures conversation history never grows unbounded by
    trimming oldest entries when size exceeds MAX_HISTORY_SIZE.

    Args:
        history: Conversation history list to modify in-place
        role: Message role ("user" or "assistant")
        content: Message content
    """
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY_SIZE:
        del history[:-MAX_HISTORY_SIZE]
