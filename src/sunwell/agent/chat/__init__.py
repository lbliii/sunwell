"""Unified Chat-Agent Experience (RFC-135).

Provides seamless transition between conversation and execution modes
via DAG-based intent classification and checkpoint-based handoffs.

Key Components:
    - DAGClassifier: Classifies user input into a conversational intent DAG path
    - IntentNode: Nodes in the intent DAG (CONVERSATION, UNDERSTAND, ACT, etc.)
    - ChatCheckpoint: User-facing handoff points between modes
    - UnifiedChatLoop: Main loop managing both modes

Example:
    >>> from sunwell.chat import UnifiedChatLoop
    >>> loop = UnifiedChatLoop(model=llm, tool_executor=tools, workspace=cwd)
    >>> gen = loop.run()
    >>> await gen.asend(None)  # Initialize
    >>> result = await gen.asend("Add user authentication")
    >>> if isinstance(result, ChatCheckpoint):
    ...     # Handle checkpoint (confirmation, failure, etc.)
    ...     response = await gen.asend(CheckpointResponse("y"))
"""

from sunwell.agent.chat.checkpoint import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
)
from sunwell.agent.chat.state import LoopState
from sunwell.agent.chat.unified import UnifiedChatLoop
from sunwell.agent.intent import (
    DAGClassifier,
    IntentClassification,
    IntentNode,
    IntentPath,
    classify_intent,
    format_path,
    get_tool_scope,
    requires_approval,
)

__all__ = [
    # Intent classification (DAG-based)
    "DAGClassifier",
    "IntentClassification",
    "IntentNode",
    "IntentPath",
    "classify_intent",
    "format_path",
    "get_tool_scope",
    "requires_approval",
    # Checkpoints
    "ChatCheckpoint",
    "ChatCheckpointType",
    "CheckpointResponse",
    # Main loop
    "UnifiedChatLoop",
    "LoopState",
]
