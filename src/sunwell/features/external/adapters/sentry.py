"""Sentry Event Adapter (RFC-049).

Adapter for Sentry error tracking and monitoring events.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sunwell.features.external.adapters.base import EventAdapter
from sunwell.features.external.types import (
    EventCallback,
    EventFeedback,
    EventSource,
    EventType,
    ExternalEvent,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SentryAdapter(EventAdapter):
    """Adapter for Sentry error tracking.

    Supports webhook mode for real-time error alerts.
    """

    source = EventSource.SENTRY

    def __init__(
        self,
        webhook_secret: str | None = None,
        dsn: str | None = None,
        organization_slug: str | None = None,
        project_slug: str | None = None,
    ):
        """Initialize Sentry adapter.

        Args:
            webhook_secret: Secret for webhook signature verification
            dsn: Sentry DSN (for API calls)
            organization_slug: Organization slug
            project_slug: Project slug
        """
        self.webhook_secret = webhook_secret
        self.dsn = dsn
        self.organization_slug = organization_slug
        self.project_slug = project_slug

        self._callback: EventCallback | None = None

    async def start(self, callback: EventCallback) -> None:
        """Start receiving Sentry events.

        Args:
            callback: Async function to call for each event
        """
        self._callback = callback
        logger.info("Sentry adapter started (webhook mode)")

    async def stop(self) -> None:
        """Stop receiving events."""
        self._callback = None
        logger.info("Sentry adapter stopped")

    def normalize_webhook(self, payload: dict) -> ExternalEvent | None:
        """Convert Sentry webhook to ExternalEvent.

        Args:
            payload: Webhook payload

        Returns:
            Normalized ExternalEvent or None if not handled
        """
        action = payload.get("action")
        resource = payload.get("resource")

        if action == "triggered":
            return self._normalize_alert_triggered(payload)
        elif action == "resolved":
            return self._normalize_alert_resolved(payload)
        elif resource == "issue" and action == "created":
            return self._normalize_issue_created(payload)
        elif resource == "error" and action == "created":
            return self._normalize_error_created(payload)

        return None

    def _normalize_alert_triggered(self, payload: dict) -> ExternalEvent:
        """Normalize alert triggered webhook."""
        data = payload.get("data", {})
        event_data = data.get("event", {})
        issue = data.get("issue", {})

        event_id = event_data.get("event_id", payload.get("id", "unknown"))

        return ExternalEvent(
            id=f"sentry-alert-{event_id}",
            source=EventSource.SENTRY,
            event_type=EventType.ALERT_TRIGGERED,
            timestamp=datetime.now(UTC),
            data={
                "title": event_data.get("title") or issue.get("title", "Unknown error"),
                "message": event_data.get("message", ""),
                "level": event_data.get("level", "error"),
                "culprit": event_data.get("culprit") or issue.get("culprit", ""),
                "platform": event_data.get("platform", ""),
                "tags": event_data.get("tags", {}),
                "issue_id": issue.get("id"),
                "short_id": issue.get("shortId"),
            },
            external_url=event_data.get("web_url") or issue.get("permalink"),
            external_ref=f"sentry:event:{event_id}",
            raw_payload=payload,
        )

    def _normalize_alert_resolved(self, payload: dict) -> ExternalEvent:
        """Normalize alert resolved webhook."""
        data = payload.get("data", {})
        issue = data.get("issue", {})

        return ExternalEvent(
            id=f"sentry-resolved-{issue.get('id', 'unknown')}",
            source=EventSource.SENTRY,
            event_type=EventType.ISSUE_CLOSED,
            timestamp=datetime.now(UTC),
            data={
                "title": issue.get("title", "Unknown issue"),
                "issue_id": issue.get("id"),
                "short_id": issue.get("shortId"),
            },
            external_url=issue.get("permalink"),
            external_ref=f"sentry:issue:{issue.get('id', 'unknown')}",
            raw_payload=payload,
        )

    def _normalize_issue_created(self, payload: dict) -> ExternalEvent:
        """Normalize new issue webhook."""
        data = payload.get("data", {})
        issue = data.get("issue", {})

        return ExternalEvent(
            id=f"sentry-issue-{issue.get('id', 'unknown')}",
            source=EventSource.SENTRY,
            event_type=EventType.ERROR_NEW,
            timestamp=datetime.now(UTC),
            data={
                "title": issue.get("title", "Unknown issue"),
                "culprit": issue.get("culprit", ""),
                "level": issue.get("level", "error"),
                "issue_id": issue.get("id"),
                "short_id": issue.get("shortId"),
                "count": issue.get("count", 1),
            },
            external_url=issue.get("permalink"),
            external_ref=f"sentry:issue:{issue.get('id', 'unknown')}",
            raw_payload=payload,
        )

    def _normalize_error_created(self, payload: dict) -> ExternalEvent:
        """Normalize error spike webhook."""
        data = payload.get("data", {})
        error = data.get("error", {})

        return ExternalEvent(
            id=f"sentry-error-{error.get('id', 'unknown')}",
            source=EventSource.SENTRY,
            event_type=EventType.ERROR_SPIKE,
            timestamp=datetime.now(UTC),
            data={
                "title": error.get("title", "Unknown error"),
                "message": error.get("message", ""),
                "level": error.get("level", "error"),
                "culprit": error.get("culprit", ""),
            },
            external_url=error.get("web_url"),
            external_ref=f"sentry:error:{error.get('id', 'unknown')}",
            raw_payload=payload,
        )

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Sentry webhook signature.

        Args:
            payload: Raw request body bytes
            signature: Sentry-Hook-Signature header value

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return False

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Send feedback to Sentry (as issue comment or activity).

        Note: Sentry's API for adding comments/notes is limited.
        This is a placeholder for future implementation.

        Args:
            event: Original event
            feedback: Feedback to send
        """
        # Sentry doesn't have a simple comment API like GitHub/Linear
        # We could potentially add a note via the Issues API, but that
        # requires more setup (auth token, organization/project slugs)
        logger.info(
            f"Sentry feedback for {event.id}: {feedback.status} - {feedback.message}"
        )

    async def handle_webhook(self, payload: dict) -> ExternalEvent | None:
        """Handle incoming webhook and notify callback.

        Args:
            payload: Webhook payload

        Returns:
            Normalized event if handled
        """
        event = self.normalize_webhook(payload)

        if event and self._callback:
            await self._callback(event)

        return event
