"""Event types for Adaptive Agent streaming (RFC-042).

Events enable live progress streaming so users see what's happening,
reducing perceived wait time. Events are yielded as the agent works.

Event categories:
- Memory: Simulacrum load/save, learning extraction
- Signal: Goal analysis, routing decisions
- Planning: Plan candidates, selection, expansion
- Execution: Task progress, completion
- Validation: Gate checks, errors
- Fix: Auto-repair progress
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class EventType(Enum):
    """Types of events emitted by the Adaptive Agent."""

    # Memory events (Simulacrum integration)
    MEMORY_LOAD = "memory_load"
    """Starting to load session memory."""

    MEMORY_LOADED = "memory_loaded"
    """Session memory loaded successfully."""

    MEMORY_NEW = "memory_new"
    """Created new session (no existing memory)."""

    MEMORY_LEARNING = "memory_learning"
    """Extracted a new learning from generated code."""

    MEMORY_DEAD_END = "memory_dead_end"
    """Recorded a dead end (approach that didn't work)."""

    MEMORY_CHECKPOINT = "memory_checkpoint"
    """Checkpointed memory to disk (survives crashes)."""

    MEMORY_SAVED = "memory_saved"
    """Session memory saved at end of run."""

    # Signal events (adaptive routing)
    SIGNAL = "signal"
    """Signal extraction status or results."""

    SIGNAL_ROUTE = "signal_route"
    """Routing decision based on signals."""

    # Planning events
    PLAN_START = "plan_start"
    """Starting plan generation."""

    PLAN_CANDIDATE = "plan_candidate"
    """Generated a plan candidate (harmonic planning)."""

    PLAN_WINNER = "plan_winner"
    """Selected winning plan."""

    PLAN_EXPANDED = "plan_expanded"
    """Expanded plan with additional tasks (iterative DAG)."""

    PLAN_ASSESS = "plan_assess"
    """Assessing if goal is complete or needs expansion."""

    # Gate events
    GATE_START = "gate_start"
    """Starting validation at a gate."""

    GATE_STEP = "gate_step"
    """Completed a step within gate validation (syntax, lint, type, etc.)."""

    GATE_PASS = "gate_pass"
    """Gate validation passed."""

    GATE_FAIL = "gate_fail"
    """Gate validation failed."""

    # Execution events
    TASK_START = "task_start"
    """Starting to execute a task."""

    TASK_PROGRESS = "task_progress"
    """Progress update during task execution."""

    TASK_COMPLETE = "task_complete"
    """Task completed successfully."""

    TASK_FAILED = "task_failed"
    """Task execution failed."""

    # Validation events
    VALIDATE_START = "validate_start"
    """Starting validation cascade."""

    VALIDATE_LEVEL = "validate_level"
    """Validation at a specific level (syntax, import, runtime)."""

    VALIDATE_ERROR = "validate_error"
    """Validation found an error."""

    VALIDATE_PASS = "validate_pass"
    """Validation passed at current level."""

    # Fix events
    FIX_START = "fix_start"
    """Starting auto-fix process."""

    FIX_PROGRESS = "fix_progress"
    """Progress during fix (e.g., Compound Eye scanning)."""

    FIX_ATTEMPT = "fix_attempt"
    """Attempting a specific fix."""

    FIX_COMPLETE = "fix_complete"
    """Fix completed successfully."""

    FIX_FAILED = "fix_failed"
    """Fix attempt failed."""

    # Completion events
    COMPLETE = "complete"
    """Agent run completed successfully."""

    ERROR = "error"
    """Agent encountered unrecoverable error."""

    ESCALATE = "escalate"
    """Escalating to user (dangerous operation or low confidence)."""


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """A single event in the agent stream.

    Events are yielded as the agent works, enabling real-time progress
    display. Each event has a type, associated data, and timestamp.

    Example:
        >>> event = AgentEvent(EventType.TASK_START, {"task_id": "UserModel"})
        >>> print(f"{event.type.value}: {event.data}")
        task_start: {'task_id': 'UserModel'}
    """

    type: EventType
    """The type of event."""

    data: dict[str, Any] = field(default_factory=dict)
    """Event-specific data."""

    timestamp: float = field(default_factory=time)
    """Unix timestamp when event was created."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEvent:
        """Create from dict."""
        return cls(
            type=EventType(data["type"]),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time()),
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"[{self.type.value}] {self.data}"


# =============================================================================
# Event Factory Helpers
# =============================================================================


def signal_event(status: str, **kwargs: Any) -> AgentEvent:
    """Create a signal extraction event."""
    return AgentEvent(EventType.SIGNAL, {"status": status, **kwargs})


def task_start_event(task_id: str, description: str, **kwargs: Any) -> AgentEvent:
    """Create a task start event."""
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
