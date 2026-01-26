"""Event emitter protocols."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sunwell.agent.events import AgentEvent

from .validation import validate_event_data


@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for event emitters.

    All event-emitting code should implement this protocol.
    """

    def emit(self, event: AgentEvent) -> None:
        """Emit an event.

        Args:
            event: The event to emit
        """
        ...


@dataclass(frozen=True, slots=True)
class ValidatedEventEmitter:
    """Event emitter with validation.

    Wraps an event emitter and validates events before emitting.
    """

    inner: EventEmitter
    validate: bool = True

    def emit(self, event: AgentEvent) -> None:
        """Emit a validated event."""
        if self.validate:
            validate_event_data(event.type, event.data)
        self.inner.emit(event)
