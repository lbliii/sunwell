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
