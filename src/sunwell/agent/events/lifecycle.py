"""Core lifecycle event factories.

Event factories for basic agent lifecycle:
- signal_event: Signal extraction
- task_start_event, task_complete_event, task_output_event: Task execution
- gate_start_event, gate_step_event: Validation gates
- validate_error_event: Validation errors
- fix_progress_event: Fix progress
- memory_learning_event: Memory learning
- complete_event: Run completion
- lens_selected_event: Lens selection
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def signal_event(status: str, **kwargs: Any) -> AgentEvent:
    """Create a signal extraction event."""
    return AgentEvent(EventType.SIGNAL, {"status": status, **kwargs})


def task_start_event(task_id: str, description: str, **kwargs: Any) -> AgentEvent:
    """Create a task start event.

    For type-safe version with validation, use:
    from sunwell.agent.events.schemas import validated_task_start_event
    """
    return AgentEvent(
        EventType.TASK_START,
        {"task_id": task_id, "description": description, **kwargs},
    )


def task_complete_event(task_id: str, duration_ms: int, **kwargs: Any) -> AgentEvent:
    """Create a task completion event."""
    return AgentEvent(
        EventType.TASK_COMPLETE,
        {"task_id": task_id, "duration_ms": duration_ms, **kwargs},
    )


def task_output_event(task_id: str, content: str, **kwargs: Any) -> AgentEvent:
    """Create a task output event for displaying results (no target file)."""
    return AgentEvent(
        EventType.TASK_OUTPUT,
        {"task_id": task_id, "content": content, **kwargs},
    )


def gate_start_event(gate_id: str, gate_type: str, **kwargs: Any) -> AgentEvent:
    """Create a gate start event."""
    return AgentEvent(
        EventType.GATE_START,
        {"gate_id": gate_id, "gate_type": gate_type, **kwargs},
    )


def gate_step_event(
    gate_id: str,
    step: str,
    passed: bool,
    message: str = "",
    **kwargs: Any,
) -> AgentEvent:
    """Create a gate step event."""
    return AgentEvent(
        EventType.GATE_STEP,
        {"gate_id": gate_id, "step": step, "passed": passed, "message": message, **kwargs},
    )


def validate_error_event(
    error_type: str,
    message: str,
    file: str | None = None,
    line: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validation error event."""
    return AgentEvent(
        EventType.VALIDATE_ERROR,
        {
            "error_type": error_type,
            "message": message,
            "file": file,
            "line": line,
            **kwargs,
        },
    )


def fix_progress_event(
    stage: str,
    progress: float,
    detail: str = "",
    **kwargs: Any,
) -> AgentEvent:
    """Create a fix progress event."""
    return AgentEvent(
        EventType.FIX_PROGRESS,
        {"stage": stage, "progress": progress, "detail": detail, **kwargs},
    )


def memory_learning_event(fact: str, category: str, **kwargs: Any) -> AgentEvent:
    """Create a memory learning event."""
    return AgentEvent(
        EventType.MEMORY_LEARNING,
        {"fact": fact, "category": category, **kwargs},
    )


def complete_event(
    tasks_completed: int,
    gates_passed: int,
    duration_s: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create a completion event."""
    return AgentEvent(
        EventType.COMPLETE,
        {
            "tasks_completed": tasks_completed,
            "gates_passed": gates_passed,
            "duration_s": duration_s,
            **kwargs,
        },
    )


def lens_selected_event(
    name: str,
    source: str,
    confidence: float,
    reason: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a lens selected event (RFC-064)."""
    return AgentEvent(
        EventType.LENS_SELECTED,
        {
            "name": name,
            "source": source,
            "confidence": confidence,
            "reason": reason,
            **kwargs,
        },
    )


# =============================================================================
# Goal Lifecycle Events (RFC-131)
# =============================================================================


def goal_received_event(goal: str, **kwargs: Any) -> AgentEvent:
    """Create a goal received event.

    Emitted when a goal is acknowledged at the start of a run.
    """
    return AgentEvent(
        EventType.GOAL_RECEIVED,
        {"goal": goal[:500] if len(goal) > 500 else goal, **kwargs},
    )


def goal_analyzing_event(goal: str, **kwargs: Any) -> AgentEvent:
    """Create a goal analyzing event.

    Emitted before signal extraction and routing decision.
    """
    return AgentEvent(
        EventType.GOAL_ANALYZING,
        {"goal": goal[:500] if len(goal) > 500 else goal, **kwargs},
    )


def goal_ready_event(
    plan_id: str | None = None,
    tasks: int = 0,
    strategy: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a goal ready event.

    Emitted when plan is selected and execution is about to begin.
    """
    return AgentEvent(
        EventType.GOAL_READY,
        {"plan_id": plan_id, "tasks": tasks, "strategy": strategy, **kwargs},
    )


def goal_complete_event(
    turns: int,
    tools_called: int,
    success: bool = True,
    **kwargs: Any,
) -> AgentEvent:
    """Create a goal complete event.

    Emitted when goal is achieved successfully.
    """
    return AgentEvent(
        EventType.GOAL_COMPLETE,
        {"turns": turns, "tools_called": tools_called, "success": success, **kwargs},
    )


def goal_failed_event(
    error: str,
    turn: int,
    tools_called: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a goal failed event.

    Emitted when goal could not be achieved.
    """
    return AgentEvent(
        EventType.GOAL_FAILED,
        {
            "error": error[:500] if len(error) > 500 else error,
            "turn": turn,
            "tools_called": tools_called,
            **kwargs,
        },
    )


# =============================================================================
# Routing Events
# =============================================================================


def signal_route_event(
    confidence: float,
    strategy: str,
    threshold_vortex: float = 0.6,
    threshold_interference: float = 0.85,
    **kwargs: Any,
) -> AgentEvent:
    """Create a signal route event.

    Emitted after routing decision based on confidence score.

    Args:
        confidence: Confidence score (0.0-1.0)
        strategy: Selected strategy ("vortex", "interference", "single_shot")
        threshold_vortex: Threshold below which Vortex is used
        threshold_interference: Threshold below which Interference is used
    """
    return AgentEvent(
        EventType.SIGNAL_ROUTE,
        {
            "confidence": round(confidence, 3),
            "strategy": strategy,
            "threshold_vortex": threshold_vortex,
            "threshold_interference": threshold_interference,
            **kwargs,
        },
    )
