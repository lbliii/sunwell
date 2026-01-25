"""Unified Chat-Agent Experience (RFC-135).

Provides seamless transition between conversation and execution modes
via intent detection and checkpoint-based handoffs.

Key Components:
    - IntentRouter: Classifies user input as conversation vs task
    - ChatCheckpoint: User-facing handoff points between modes
    - UnifiedChatLoop: Main loop managing both modes

Example:
    >>> from sunwell.chat import UnifiedChatLoop, IntentRouter
    >>> loop = UnifiedChatLoop(model=llm, tool_executor=tools, workspace=cwd)
    >>> gen = loop.run()
    >>> await gen.asend(None)  # Initialize
    >>> result = await gen.asend("Add user authentication")
    >>> if isinstance(result, ChatCheckpoint):
    ...     # Handle checkpoint (confirmation, failure, etc.)
    ...     response = await gen.asend(CheckpointResponse("y"))
"""

from sunwell.chat.checkpoint import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
)
from sunwell.chat.intent import Intent, IntentClassification, IntentRouter
from sunwell.chat.unified import LoopState, UnifiedChatLoop

__all__ = [
    # Intent classification
    "Intent",
    "IntentClassification",
    "IntentRouter",
    # Checkpoints
    "ChatCheckpoint",
    "ChatCheckpointType",
    "CheckpointResponse",
    # Main loop
    "UnifiedChatLoop",
    "LoopState",
]
