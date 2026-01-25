"""Tool calling event factories (RFC-134: S-Tier Tool Calling).

Event factories for tool execution lifecycle:
- tool_start_event, tool_complete_event, tool_error_event
- tool_loop_start_event, tool_loop_turn_event, tool_loop_complete_event
- tool_repair_event, tool_blocked_event, tool_retry_event, tool_escalate_event
- tool_pattern_learned_event, progressive_unlock_event
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def tool_start_event(
    tool_name: str,
    tool_call_id: str,
    arguments: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool start event."""
    return AgentEvent(
        EventType.TOOL_START,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "arguments": arguments or {},
            **kwargs,
        },
    )


def tool_complete_event(
    tool_name: str,
    tool_call_id: str,
    success: bool,
    output: str,
    execution_time_ms: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool completion event."""
    return AgentEvent(
        EventType.TOOL_COMPLETE,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "success": success,
            "output": output[:500] if len(output) > 500 else output,  # Truncate for display
            "execution_time_ms": execution_time_ms,
            **kwargs,
        },
    )


def tool_error_event(
    tool_name: str,
    tool_call_id: str,
    error: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool error event."""
    return AgentEvent(
        EventType.TOOL_ERROR,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "error": error,
            **kwargs,
        },
    )


def tool_loop_start_event(
    task_description: str,
    max_turns: int,
    tool_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool loop start event."""
    return AgentEvent(
        EventType.TOOL_LOOP_START,
        {
            "task_description": task_description[:200],
            "max_turns": max_turns,
            "tool_count": tool_count,
            **kwargs,
        },
    )


def tool_loop_turn_event(
    turn: int,
    tool_calls_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool loop turn event."""
    return AgentEvent(
        EventType.TOOL_LOOP_TURN,
        {
            "turn": turn,
            "tool_calls_count": tool_calls_count,
            **kwargs,
        },
    )


def tool_loop_complete_event(
    turns_used: int,
    tool_calls_total: int,
    final_response: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool loop completion event."""
    return AgentEvent(
        EventType.TOOL_LOOP_COMPLETE,
        {
            "turns_used": turns_used,
            "tool_calls_total": tool_calls_total,
            "final_response": (
                final_response[:500]
                if final_response and len(final_response) > 500
                else final_response
            ),
            **kwargs,
        },
    )


# =============================================================================
# RFC-134: Introspection and Escalation Events
# =============================================================================


def tool_repair_event(
    tool_name: str,
    tool_call_id: str,
    repairs: tuple[str, ...],
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool repair event (RFC-134).

    Emitted when tool call arguments are fixed by introspection.
    """
    return AgentEvent(
        EventType.TOOL_REPAIR,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "repairs": list(repairs),
            "repair_count": len(repairs),
            **kwargs,
        },
    )


def tool_blocked_event(
    tool_name: str,
    tool_call_id: str,
    reason: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool blocked event (RFC-134).

    Emitted when a tool call is blocked due to invalid arguments.
    """
    return AgentEvent(
        EventType.TOOL_BLOCKED,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "reason": reason,
            **kwargs,
        },
    )


def tool_retry_event(
    tool_name: str,
    tool_call_id: str,
    attempt: int,
    strategy: str,
    error: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool retry event (RFC-134).

    Emitted when retrying a tool call with escalated strategy.
    """
    return AgentEvent(
        EventType.TOOL_RETRY,
        {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "attempt": attempt,
            "strategy": strategy,
            "error": error[:200] if len(error) > 200 else error,
            **kwargs,
        },
    )


def tool_escalate_event(
    tool_name: str,
    error: str,
    reason: str,
    attempts: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool escalate event (RFC-134).

    Emitted when tool failures exceed retry limit and user intervention needed.
    """
    return AgentEvent(
        EventType.TOOL_ESCALATE,
        {
            "tool_name": tool_name,
            "error": error[:500] if len(error) > 500 else error,
            "reason": reason,
            "attempts": attempts,
            **kwargs,
        },
    )


def tool_pattern_learned_event(
    task_type: str,
    tool_sequence: list[str],
    success_rate: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create a tool pattern learned event (RFC-134).

    Emitted when a successful tool pattern is recorded.
    """
    return AgentEvent(
        EventType.TOOL_PATTERN_LEARNED,
        {
            "task_type": task_type,
            "tool_sequence": tool_sequence,
            "success_rate": success_rate,
            **kwargs,
        },
    )


def progressive_unlock_event(
    category: str,
    tools_unlocked: list[str],
    turn: int,
    validation_passes: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a progressive unlock event (RFC-134).

    Emitted when a new tool category is unlocked.
    """
    return AgentEvent(
        EventType.PROGRESSIVE_UNLOCK,
        {
            "category": category,
            "tools_unlocked": tools_unlocked,
            "turn": turn,
            "validation_passes": validation_passes,
            **kwargs,
        },
    )
