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

⚠️ BIDIRECTIONAL GENERATOR PATTERN:

Several async generators in this module use bidirectional communication via
``asend()`` to receive checkpoint responses. These generators are marked with
a ⚠️ warning in their docstrings.

**IMPORTANT**: Do NOT consume these generators with ``async for``. The
``async for`` syntax calls ``__anext__()`` which is equivalent to
``asend(None)``, causing checkpoint responses to be lost.

**Correct pattern**::

    gen = bidirectional_generator(...)
    try:
        result = await gen.asend(None)  # Initialize
        while True:
            # Handle result (yield to caller or process checkpoint)
            response = get_checkpoint_response(result)
            result = await gen.asend(response)  # Forward response
    except StopAsyncIteration:
        pass

**Incorrect pattern** (will break checkpoints)::

    async for result in bidirectional_generator(...):  # ❌ WRONG
        yield result  # Checkpoint responses are lost!
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
