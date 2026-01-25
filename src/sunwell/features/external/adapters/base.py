"""Base Event Adapter Protocol (RFC-049).

Defines the interface for all event source adapters.
"""

from abc import ABC, abstractmethod

from sunwell.external.types import (
    EventCallback,
    EventFeedback,
    EventSource,
    ExternalEvent,
)


class EventAdapter(ABC):
    """Base class for external service adapters.

    Each adapter:
    1. Receives events (webhook or polling)
    2. Normalizes to ExternalEvent
    3. Optionally pushes feedback back to service
    """

    @property
    @abstractmethod
    def source(self) -> EventSource:
        """Which source this adapter handles."""
        ...

    @abstractmethod
    async def start(self, callback: EventCallback) -> None:
        """Start receiving events, call callback for each.

        Args:
            callback: Async function to call for each event
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop receiving events."""
        ...

    @abstractmethod
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature for security.

        Args:
            payload: Raw request body bytes
            signature: Signature header value

        Returns:
            True if signature is valid
        """
        ...

    @abstractmethod
    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Send feedback back to the external service.

        Args:
            event: Original event that was processed
            feedback: Feedback to send
        """
        ...
