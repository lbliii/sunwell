"""Type-safe event factory functions."""

from typing import Any

from sunwell.agent.events import EventType

from .base import PlanWinnerData, TaskCompleteData, TaskFailedData, TaskStartData
from .validation import create_validated_event


def validated_task_start_event(
    task_id: str,
    description: str,
    artifact_id: str | None = None,
    **kwargs: Any,
) -> Any:  # Returns AgentEvent, but avoiding circular import
    """Create a validated task_start event."""
    from sunwell.agent.events import AgentEvent

    data: TaskStartData = {
        "task_id": task_id,
        "description": description,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    return create_validated_event(EventType.TASK_START, data)


def validated_task_complete_event(
    task_id: str,
    duration_ms: int,
    artifact_id: str | None = None,
    file: str | None = None,
    **kwargs: Any,
) -> Any:  # Returns AgentEvent, but avoiding circular import
    """Create a validated task_complete event."""
    data: TaskCompleteData = {
        "task_id": task_id,
        "duration_ms": duration_ms,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    if file:
        data["file"] = file
    return create_validated_event(EventType.TASK_COMPLETE, data)


def validated_task_failed_event(
    task_id: str,
    error: str,
    artifact_id: str | None = None,
    **kwargs: Any,
) -> Any:  # Returns AgentEvent, but avoiding circular import
    """Create a validated task_failed event."""
    data: TaskFailedData = {
        "task_id": task_id,
        "error": error,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    return create_validated_event(EventType.TASK_FAILED, data)


def validated_plan_winner_event(
    tasks: int,
    artifact_count: int | None = None,
    gates: int | None = None,
    technique: str | None = None,
    **kwargs: Any,
) -> Any:  # Returns AgentEvent, but avoiding circular import
    """Create a validated plan_winner event."""
    data: PlanWinnerData = {
        "tasks": tasks,
        **kwargs,
    }
    if artifact_count is not None:
        data["artifact_count"] = artifact_count
    if gates is not None:
        data["gates"] = gates
    if technique:
        data["technique"] = technique
    return create_validated_event(EventType.PLAN_WINNER, data)
