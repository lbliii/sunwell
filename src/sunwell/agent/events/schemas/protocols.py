"""Event emitter protocols.

EventEmitter protocol moved to sunwell.contracts.events; re-exported here
for backward compatibility. ValidatedEventEmitter stays here as it contains
business logic (validation).
"""

from dataclasses import dataclass

from sunwell.contracts.events import AgentEvent, EventEmitter

from .validation import validate_event_data


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
