"""Event emission utilities for artifact planner (RFC-059)."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.events import AgentEvent


def emit_event(
    event_callback: Callable[[AgentEvent], None] | None,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Emit event via callback if configured (RFC-059).

    RFC-060: Uses create_validated_event() for schema validation.
    Validation mode controlled by SUNWELL_EVENT_VALIDATION env var.
    """
    if event_callback is None:
        return

    try:
        from sunwell.agent.event_schema import create_validated_event
        from sunwell.agent.events import EventType

        # RFC-060: Validate event data against schema
        event = create_validated_event(EventType(event_type), data)
        event_callback(event)
    except ValueError as e:
        # Invalid event type or validation failure (strict mode)
        import logging

        logging.warning(f"Event validation failed for '{event_type}': {e}")
    except Exception as e:
        # Other errors - log but don't break discovery
        import logging

        logging.warning(f"Event emission failed for '{event_type}': {e}")


def emit_error(
    event_callback: Callable[[AgentEvent], None] | None,
    message: str,
    phase: str | None = None,
    error_type: str | None = None,
    **context: Any,
) -> None:
    """Emit error event with context (RFC-059).

    Args:
        event_callback: Event callback function
        message: Error message (required)
        phase: Phase where error occurred ("planning" | "discovery" | "execution" | "validation")
        error_type: Exception class name
        **context: Additional context (artifact_id, task_id, goal, etc.)
    """
    error_data: dict[str, Any] = {"message": message}
    if phase:
        error_data["phase"] = phase
    if error_type:
        error_data["error_type"] = error_type
    if context:
        error_data["context"] = context
    emit_event(event_callback, "error", error_data)
