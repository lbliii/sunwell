"""Event emission for Naaru (RFC-053/RFC-060).

Provides validated event emission with schema enforcement.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class EventEmitter(Protocol):
    """Protocol for event emission."""

    def emit(self, event_type: str, **data: Any) -> None:
        """Emit an event with validated payload."""
        ...

    def emit_error(
        self,
        message: str,
        phase: str | None = None,
        error_type: str | None = None,
        **context: Any,
    ) -> None:
        """Emit an error event with context."""
        ...


class NaaruEventEmitter:
    """Validated event emitter for Naaru (RFC-060).

    Uses create_validated_event() for schema validation.
    Validation mode controlled by SUNWELL_EVENT_VALIDATION env var.
    """

    def __init__(self, callback: Callable[[Any], None] | None = None) -> None:
        """Initialize emitter with optional callback.

        Args:
            callback: Event callback function. If None, events are no-ops.
        """
        self._callback = callback

    def emit(self, event_type: str, **data: Any) -> None:
        """Emit an AgentEvent to the configured callback.

        Args:
            event_type: Event type from EventType enum (as string)
            **data: Event payload data
        """
        if self._callback is None:
            return

        from sunwell.adaptive.event_schema import create_validated_event
        from sunwell.adaptive.events import EventType

        try:
            event = create_validated_event(EventType(event_type), data)
            self._callback(event)
        except ValueError:
            # Unknown event type or validation failure - skip
            pass

    def emit_error(
        self,
        message: str,
        phase: str | None = None,
        error_type: str | None = None,
        **context: Any,
    ) -> None:
        """Emit error event with context (RFC-059).

        Args:
            message: Error message (required)
            phase: Phase where error occurred
            error_type: Exception class name
            **context: Additional context
        """
        error_data: dict[str, Any] = {"message": message}
        if phase:
            error_data["phase"] = phase
        if error_type:
            error_data["error_type"] = error_type
        if context:
            error_data["context"] = context
        self.emit("error", **error_data)

    def emit_plan_start(self, goal: str) -> None:
        """Emit plan_start event."""
        self.emit("plan_start", goal=goal)

    def emit_plan_winner(self, tasks: int, artifact_count: int | None = None) -> None:
        """Emit plan_winner event with validated factory."""
        if self._callback is None:
            return

        from sunwell.adaptive.event_schema import validated_plan_winner_event

        event = validated_plan_winner_event(tasks=tasks, artifact_count=artifact_count)
        self._callback(event)

    def emit_complete(
        self,
        tasks_completed: int,
        tasks_failed: int,
        duration_s: float,
        learnings_count: int,
    ) -> None:
        """Emit completion event."""
        self.emit(
            "complete",
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            duration_s=duration_s,
            learnings_count=learnings_count,
        )

    def emit_learning(self, **learning_data: Any) -> None:
        """Emit learning event."""
        self.emit("learning", **learning_data)
