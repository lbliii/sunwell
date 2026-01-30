"""Hook system types and event definitions.

Provides event-driven extensibility for external integrations.
Hooks can subscribe to lifecycle events and react to agent activity.

Inspired by moltbot's hooks system but simplified for sunwell's patterns.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class HookEvent(Enum):
    """Events that hooks can subscribe to.

    Lifecycle events:
    - SESSION_START/END: Session boundaries
    - SUBAGENT_SPAWN/COMPLETE: Subagent lifecycle

    Execution events:
    - TASK_START/COMPLETE: Individual task execution
    - TOOL_START/COMPLETE: Tool execution

    Validation events:
    - GATE_PASS/FAIL: Validation gate outcomes

    Planning events:
    - PLAN_CREATE: New plan created
    - PLAN_UPDATE: Plan modified
    """

    # Session lifecycle
    SESSION_START = "session:start"
    SESSION_END = "session:end"

    # Subagent lifecycle
    SUBAGENT_SPAWN = "subagent:spawn"
    SUBAGENT_START = "subagent:start"
    SUBAGENT_HEARTBEAT = "subagent:heartbeat"
    SUBAGENT_COMPLETE = "subagent:complete"

    # Task execution
    TASK_START = "task:start"
    TASK_COMPLETE = "task:complete"

    # Tool execution
    TOOL_START = "tool:start"
    TOOL_COMPLETE = "tool:complete"
    TOOL_ERROR = "tool:error"

    # Validation gates
    GATE_PASS = "gate:pass"
    GATE_FAIL = "gate:fail"

    # Planning
    PLAN_CREATE = "plan:create"
    PLAN_UPDATE = "plan:update"

    # Learning
    LEARNING_EXTRACT = "learning:extract"
    LEARNING_APPLY = "learning:apply"

    # Intent classification (DAG Architecture)
    INTENT_CLASSIFIED = "intent:classified"
    NODE_TRANSITION = "intent:node_transition"

    # File changes (for diff preview)
    FILE_CHANGE_PENDING = "file:change_pending"
    FILE_CHANGE_APPROVED = "file:change_approved"
    FILE_CHANGE_REJECTED = "file:change_rejected"


@dataclass(frozen=True, slots=True)
class HookMetadata:
    """Metadata describing hook requirements and subscriptions.

    Attributes:
        events: Tuple of events this hook subscribes to
        requires_bins: External binaries the hook requires
        requires_env: Environment variables the hook requires
        name: Optional human-readable name for the hook
        description: Optional description of what the hook does
    """

    events: tuple[HookEvent, ...]
    """Events this hook subscribes to."""

    requires_bins: tuple[str, ...] = ()
    """External binaries required (e.g., 'git', 'rg')."""

    requires_env: tuple[str, ...] = ()
    """Environment variables required (e.g., 'GITHUB_TOKEN')."""

    name: str | None = None
    """Optional hook name for logging."""

    description: str | None = None
    """Optional description."""


# Type alias for hook handlers
HookHandler = Callable[[HookEvent, dict[str, Any]], Awaitable[None] | None]
"""Hook handler signature.

Args:
    event: The hook event that triggered
    data: Event-specific data dictionary

Returns:
    None (sync) or Awaitable[None] (async)

Example:
    async def my_hook(event: HookEvent, data: dict) -> None:
        if event == HookEvent.TASK_COMPLETE:
            print(f"Task {data['task_id']} completed!")
"""


# Type alias for unsubscribe function
Unsubscribe = Callable[[], None]
"""Function to unsubscribe a hook."""


@dataclass(frozen=True, slots=True)
class HookRegistration:
    """A registered hook with its metadata.

    Internal type used by HookRegistry to track registrations.
    """

    handler: HookHandler
    """The handler function."""

    metadata: HookMetadata | None
    """Optional metadata about requirements."""

    id: str
    """Unique registration ID."""


# Standard event data schemas (for documentation)
EVENT_DATA_SCHEMAS: dict[HookEvent, dict[str, str]] = {
    HookEvent.SESSION_START: {
        "session_id": "str - Unique session identifier",
        "parent_session_id": "str | None - Parent session if subagent",
    },
    HookEvent.SESSION_END: {
        "session_id": "str - Unique session identifier",
        "success": "bool - Whether session completed successfully",
        "duration_ms": "int - Total duration in milliseconds",
    },
    HookEvent.SUBAGENT_SPAWN: {
        "run_id": "str - Unique subagent run ID",
        "parent_session_id": "str - Parent session",
        "task": "str - Task description",
    },
    HookEvent.SUBAGENT_COMPLETE: {
        "run_id": "str - Unique subagent run ID",
        "outcome": "str - ok/error/timeout/cancelled",
        "duration_ms": "int - Execution duration",
    },
    HookEvent.TASK_START: {
        "task_id": "str - Task identifier",
        "description": "str - Task description",
    },
    HookEvent.TASK_COMPLETE: {
        "task_id": "str - Task identifier",
        "success": "bool - Whether task succeeded",
        "duration_ms": "int - Execution duration",
    },
    HookEvent.TOOL_START: {
        "tool_name": "str - Name of the tool",
        "tool_call_id": "str - Unique call ID",
        "arguments": "dict - Tool arguments",
    },
    HookEvent.TOOL_COMPLETE: {
        "tool_name": "str - Name of the tool",
        "tool_call_id": "str - Unique call ID",
        "success": "bool - Whether tool succeeded",
        "duration_ms": "int - Execution duration",
    },
    HookEvent.GATE_PASS: {
        "gate_name": "str - Name of the gate",
        "files": "list[str] - Files that were validated",
    },
    HookEvent.GATE_FAIL: {
        "gate_name": "str - Name of the gate",
        "files": "list[str] - Files that failed",
        "errors": "list[str] - Validation errors",
    },
    HookEvent.INTENT_CLASSIFIED: {
        "path": "list[str] - DAG path nodes (e.g., ['conversation', 'act', 'write', 'modify'])",
        "confidence": "float - Classification confidence (0.0-1.0)",
        "reasoning": "str - Why this classification was made",
        "user_input": "str - Original user input",
    },
    HookEvent.NODE_TRANSITION: {
        "from_node": "str - Previous node in DAG",
        "to_node": "str - New node in DAG",
        "path": "list[str] - Full current path",
    },
    HookEvent.FILE_CHANGE_PENDING: {
        "file_path": "str - Path to file being changed",
        "change_type": "str - create/modify/delete",
        "diff": "str - Unified diff of changes (for modify)",
    },
    HookEvent.FILE_CHANGE_APPROVED: {
        "file_path": "str - Path to file",
        "change_type": "str - create/modify/delete",
    },
    HookEvent.FILE_CHANGE_REJECTED: {
        "file_path": "str - Path to file",
        "change_type": "str - create/modify/delete",
        "reason": "str - Why change was rejected",
    },
}
