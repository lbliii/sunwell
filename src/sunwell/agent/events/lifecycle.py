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
    from sunwell.agent.event_schema import validated_task_start_event
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
