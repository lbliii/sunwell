"""Tool calling event schemas (RFC-134)."""

from typing import Any, TypedDict

# =============================================================================
# Tool Lifecycle Events
# =============================================================================


class ToolStartData(TypedDict, total=False):
    """Data for tool_start event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    arguments: dict[str, Any]


class ToolCompleteData(TypedDict, total=False):
    """Data for tool_complete event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    success: bool
    output: str
    execution_time_ms: int


class ToolErrorData(TypedDict, total=False):
    """Data for tool_error event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    error: str


# =============================================================================
# Tool Loop Events
# =============================================================================


class ToolLoopStartData(TypedDict, total=False):
    """Data for tool_loop_start event."""

    task_description: str
    max_turns: int
    tool_count: int


class ToolLoopTurnData(TypedDict, total=False):
    """Data for tool_loop_turn event."""

    turn: int  # Required
    tool_calls_count: int


class ToolLoopCompleteData(TypedDict, total=False):
    """Data for tool_loop_complete event."""

    turns_used: int
    tool_calls_total: int
    final_response: str | None


# =============================================================================
# RFC-134: Introspection and Escalation Events
# =============================================================================


class ToolRepairData(TypedDict, total=False):
    """Data for tool_repair event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    repairs: list[str]
    repair_count: int


class ToolBlockedData(TypedDict, total=False):
    """Data for tool_blocked event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    reason: str


class ToolRetryData(TypedDict, total=False):
    """Data for tool_retry event."""

    tool_name: str  # Required
    tool_call_id: str  # Required
    attempt: int
    strategy: str
    error: str


class ToolEscalateData(TypedDict, total=False):
    """Data for tool_escalate event."""

    tool_name: str  # Required
    error: str
    reason: str
    attempts: int


class ToolPatternLearnedData(TypedDict, total=False):
    """Data for tool_pattern_learned event."""

    task_type: str
    tool_sequence: list[str]
    success_rate: float


class ProgressiveUnlockData(TypedDict, total=False):
    """Data for progressive_unlock event."""

    category: str
    tools_unlocked: list[str]
    turn: int
    validation_passes: int
