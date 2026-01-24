"""Linear Event Adapter (RFC-049).

Adapter for Linear issue tracking events.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sunwell.external.adapters.base import EventAdapter
from sunwell.external.types import (
    EventCallback,
    EventFeedback,
    EventSource,
    EventType,
    ExternalEvent,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class LinearAdapter(EventAdapter):
    """Adapter for Linear issue tracking.

    Supports webhook mode for real-time events.
    """

    source = EventSource.LINEAR

    def __init__(
        self,
        api_key: str,
        webhook_secret: str | None = None,
        team_id: str | None = None,
    ):
        """Initialize Linear adapter.

        Args:
            api_key: Linear API key
            webhook_secret: Secret for webhook signature verification
            team_id: Team ID to filter events
        """
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.team_id = team_id

        self._client: httpx.AsyncClient | None = None
        self._callback: EventCallback | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url="https://api.linear.app",
                headers={"Authorization": self.api_key},
            )
        return self._client

    async def start(self, callback: EventCallback) -> None:
        """Start receiving Linear events.

        Args:
            callback: Async function to call for each event
        """
        self._callback = callback
        logger.info("Linear adapter started (webhook mode)")

    async def stop(self) -> None:
        """Stop receiving events."""
        self._callback = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("Linear adapter stopped")

    def normalize_webhook(self, payload: dict) -> ExternalEvent | None:
        """Convert Linear webhook to ExternalEvent.

        Args:
            payload: Webhook payload

        Returns:
            Normalized ExternalEvent or None if not handled
        """
        action = payload.get("action")
        data_type = payload.get("type")
        data = payload.get("data", {})

        if data_type == "Issue":
            return self._normalize_issue(action, data, payload)
        elif data_type == "Comment":
            return self._normalize_comment(action, data, payload)

        return None

    def _normalize_issue(
        self, action: str, data: dict, payload: dict
    ) -> ExternalEvent | None:
        """Normalize Issue webhook."""
        issue_id = data.get("id", "")

        if action == "create":
            return ExternalEvent(
                id=f"linear-issue-{issue_id}-created",
                source=EventSource.LINEAR,
                event_type=EventType.ISSUE_OPENED,
                timestamp=datetime.now(UTC),
                data={
                    "issue_id": issue_id,
                    "title": data.get("title", ""),
                    "body": data.get("description", ""),
                    "priority": data.get("priority"),
                    "labels": [l.get("name") for l in data.get("labels", [])],
                    "team": data.get("team", {}).get("name"),
                    "author": data.get("creator", {}).get("name"),
                },
                external_url=data.get("url"),
                external_ref=f"linear:issue:{issue_id}",
                raw_payload=payload,
            )
        elif action == "update":
            # Check if issue was closed
            state = data.get("state", {})
            if state.get("type") == "completed":
                return ExternalEvent(
                    id=f"linear-issue-{issue_id}-closed",
                    source=EventSource.LINEAR,
                    event_type=EventType.ISSUE_CLOSED,
                    timestamp=datetime.now(UTC),
                    data={
                        "issue_id": issue_id,
                        "title": data.get("title", ""),
                    },
                    external_url=data.get("url"),
                    external_ref=f"linear:issue:{issue_id}",
                    raw_payload=payload,
                )

        return None

    def _normalize_comment(
        self, action: str, data: dict, payload: dict
    ) -> ExternalEvent | None:
        """Normalize Comment webhook."""
        if action != "create":
            return None

        issue = data.get("issue", {})
        issue_id = issue.get("id", "")
        comment_id = data.get("id", "")

        return ExternalEvent(
            id=f"linear-comment-{comment_id}",
            source=EventSource.LINEAR,
            event_type=EventType.ISSUE_COMMENTED,
            timestamp=datetime.now(UTC),
            data={
                "issue_id": issue_id,
                "comment_id": comment_id,
                "body": data.get("body", ""),
                "author": data.get("user", {}).get("name"),
            },
            external_url=issue.get("url"),
            external_ref=f"linear:issue:{issue_id}",
            raw_payload=payload,
        )

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Linear webhook signature.

        Args:
            payload: Raw request body bytes
            signature: Linear-Webhook-Signature header value

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
        """Create a comment on the Linear issue.

        Args:
            event: Original event
            feedback: Feedback to send
        """
        issue_id = event.data.get("issue_id")
        if not issue_id:
            return

        client = await self._get_client()

        mutation = """
        mutation CreateComment($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """

        status_emoji = {
            "acknowledged": "👀",
            "investigating": "🔍",
            "fixed": "✅",
            "skipped": "⏭️",
        }

        message = f"{status_emoji.get(feedback.status, '🤖')} **Sunwell**: {feedback.message}"
        if feedback.commit_sha:
            message += f"\n\n**Fix**: `{feedback.commit_sha[:7]}`"

        try:
            await client.post(
                "/graphql",
                json={
                    "query": mutation,
                    "variables": {
                        "issueId": issue_id,
                        "body": message,
                    },
                },
            )
        except Exception as e:
            logger.error(f"Error sending feedback to Linear: {e}")

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
