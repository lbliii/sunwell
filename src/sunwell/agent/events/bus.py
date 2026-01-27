"""Centralized event bus for agent lifecycle events.

Provides:
- set_run_context(): Set current run ID for event sequencing
- emit(): Emit event with automatic sequencing and run context
- on_event(): Subscribe to events

Inspired by moltbot's agent-events.ts but adapted for Python's
async patterns and free-threading awareness (Python 3.14t).

Features:
- Per-run monotonic sequence numbers
- Automatic timestamp injection
- Run context via contextvars (async/thread-safe)
- Pub/sub listener pattern
- Listener isolation (errors don't break event flow)
"""

import logging
import threading
from collections.abc import Callable
from contextvars import ContextVar
from time import time as get_time
from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType

logger = logging.getLogger(__name__)


# =============================================================================
# Run Context (via contextvars for async/thread safety)
# =============================================================================

_current_run_id: ContextVar[str] = ContextVar("agent_run_id", default="")
"""Current run ID for event sequencing. Set via set_run_context()."""

_current_session_id: ContextVar[str] = ContextVar("agent_session_id", default="")
"""Current session ID for event context. Set via set_run_context()."""


def set_run_context(run_id: str, session_id: str | None = None) -> None:
    """Set the current run context for event sequencing.

    Should be called at the start of each agent run. Events emitted
    in this context will include the run_id and session_id.

    Args:
        run_id: Unique identifier for this run
        session_id: Optional session ID (defaults to run_id)
    """
    _current_run_id.set(run_id)
    _current_session_id.set(session_id or run_id)


def get_run_context() -> tuple[str, str]:
    """Get the current run context.

    Returns:
        Tuple of (run_id, session_id)
    """
    return _current_run_id.get(), _current_session_id.get()


def clear_run_context() -> None:
    """Clear the current run context."""
    _current_run_id.set("")
    _current_session_id.set("")


# =============================================================================
# Event Sequencing (thread-safe)
# =============================================================================

_seq_by_run: dict[str, int] = {}
"""Monotonic sequence counter per run_id."""

_seq_lock = threading.Lock()
"""Lock for sequence counter access."""


def _next_seq(run_id: str) -> int:
    """Get next sequence number for a run (thread-safe)."""
    with _seq_lock:
        seq = _seq_by_run.get(run_id, 0) + 1
        _seq_by_run[run_id] = seq
        return seq


def _clear_seq(run_id: str) -> None:
    """Clear sequence counter for a run."""
    with _seq_lock:
        _seq_by_run.pop(run_id, None)


# =============================================================================
# Event Listeners
# =============================================================================

EventListener = Callable[[AgentEvent], None]
"""Listener callback type: (event) -> None"""

_listeners: set[EventListener] = set()
"""Registered event listeners."""

_listener_lock = threading.Lock()
"""Lock for listener set access."""


def on_event(listener: EventListener) -> Callable[[], None]:
    """Subscribe to agent events.

    Listeners are called synchronously when events are emitted.
    Listener errors are logged but don't break event flow.

    Args:
        listener: Callback function (event: AgentEvent) -> None

    Returns:
        Unsubscribe function. Call to remove the listener.

    Example:
        >>> def my_listener(event):
        ...     print(f"Event: {event.type.value}")
        >>> unsubscribe = on_event(my_listener)
        >>> # Later...
        >>> unsubscribe()
    """
    with _listener_lock:
        _listeners.add(listener)

    def unsubscribe() -> None:
        with _listener_lock:
            _listeners.discard(listener)

    return unsubscribe


def _notify_listeners(event: AgentEvent) -> None:
    """Notify all listeners of an event (thread-safe)."""
    with _listener_lock:
        listeners = list(_listeners)

    for listener in listeners:
        try:
            listener(event)
        except Exception:
            logger.exception("Event listener failed for %s", event.type.value)


# =============================================================================
# Event Emission
# =============================================================================


def emit(event: AgentEvent) -> AgentEvent:
    """Emit an event with automatic enrichment.

    Enriches the event data with:
    - seq: Monotonic sequence number for this run
    - run_id: Current run ID from context
    - session_id: Current session ID from context

    The event's timestamp is already set by the AgentEvent dataclass.

    Args:
        event: The AgentEvent to emit

    Returns:
        The same event (for chaining)

    Example:
        >>> event = emit(AgentEvent(EventType.TASK_START, {"task_id": "123"}))
        >>> print(event.data["seq"])
        1
    """
    run_id, session_id = get_run_context()

    # Enrich event data with bus context
    # Note: AgentEvent.data is a dict, so we can add to it
    event.data["seq"] = _next_seq(run_id) if run_id else 0
    if run_id:
        event.data["run_id"] = run_id
    if session_id:
        event.data["session_id"] = session_id

    # Notify listeners
    _notify_listeners(event)

    return event


def emit_typed(
    event_type: EventType,
    **kwargs: Any,
) -> AgentEvent:
    """Emit a typed event with keyword arguments.

    Convenience wrapper around emit() for cleaner event creation.

    Args:
        event_type: The event type
        **kwargs: Additional event data

    Returns:
        The emitted AgentEvent

    Example:
        >>> event = emit_typed(EventType.TASK_START, task_id="123", description="Test")
        >>> print(event.type.value)
        task_start
    """
    event = AgentEvent(type=event_type, data=dict(kwargs), timestamp=get_time())
    return emit(event)


# =============================================================================
# Lifecycle Helpers
# =============================================================================


def start_session(run_id: str, session_id: str | None = None) -> AgentEvent:
    """Start a new session context.

    Combines set_run_context() and emits a SESSION_START event.

    Args:
        run_id: Unique identifier for this run
        session_id: Optional session ID (defaults to run_id)

    Returns:
        The emitted SESSION_START event
    """
    set_run_context(run_id, session_id)
    return emit_typed(
        EventType.SESSION_START,
        run_id=run_id,
        session_id=session_id or run_id,
    )


def end_session(outcome: str = "ok", error: str | None = None) -> AgentEvent:
    """End the current session context.

    Emits a SESSION_END event and clears the context.

    Args:
        outcome: Session outcome ("ok", "error", "cancelled")
        error: Optional error message if outcome is "error"

    Returns:
        The emitted SESSION_END event
    """
    run_id, session_id = get_run_context()
    event = emit_typed(
        EventType.SESSION_END,
        run_id=run_id,
        session_id=session_id,
        outcome=outcome,
        error=error,
    )
    _clear_seq(run_id)
    clear_run_context()
    return event


def crash_session(error: str) -> AgentEvent:
    """Record a session crash.

    Emits a SESSION_CRASH event and clears the context.

    Args:
        error: Error message describing the crash

    Returns:
        The emitted SESSION_CRASH event
    """
    run_id, session_id = get_run_context()
    event = emit_typed(
        EventType.SESSION_CRASH,
        run_id=run_id,
        session_id=session_id,
        error=error,
    )
    _clear_seq(run_id)
    clear_run_context()
    return event


# =============================================================================
# Testing Utilities
# =============================================================================


def reset_for_tests() -> None:
    """Reset all event bus state (for testing only)."""
    with _seq_lock:
        _seq_by_run.clear()
    with _listener_lock:
        _listeners.clear()
    clear_run_context()


def collect_events() -> tuple[list[AgentEvent], Callable[[], None]]:
    """Create an event collector for testing.

    Returns:
        Tuple of (events_list, unsubscribe_function)

    Example:
        >>> events, unsubscribe = collect_events()
        >>> emit_typed(EventType.TASK_START, task_id="123")
        >>> assert len(events) == 1
        >>> assert events[0].type == EventType.TASK_START
        >>> unsubscribe()
    """
    events: list[AgentEvent] = []

    def collector(event: AgentEvent) -> None:
        events.append(event)

    unsubscribe = on_event(collector)
    return events, unsubscribe
