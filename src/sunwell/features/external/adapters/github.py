"""GitHub Event Adapter (RFC-049).

Adapter for GitHub events: Actions, Issues, Pull Requests.
"""

import asyncio
import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sunwell.features.external.adapters.base import EventAdapter
from sunwell.features.external.types import (
    STATUS_EMOJI,
    EventCallback,
    EventFeedback,
    EventSource,
    EventType,
    ExternalEvent,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class GitHubAdapter(EventAdapter):
    """Adapter for GitHub events (Actions, Issues, PRs).

    Supports both webhook and polling modes:
    - Webhook: Real-time events via HTTP POST
    - Polling: Periodic API calls (fallback)
    """

    source = EventSource.GITHUB

    def __init__(
        self,
        token: str,
        webhook_secret: str | None = None,
        repo: str | None = None,
        polling_interval: int = 60,
    ):
        """Initialize GitHub adapter.

        Args:
            token: GitHub personal access token
            webhook_secret: Secret for webhook signature verification
            repo: Repository in 'owner/repo' format (for polling)
            polling_interval: Seconds between polls (default: 60)
        """
        self.token = token
        self.webhook_secret = webhook_secret
        self.repo = repo
        self.polling_interval = polling_interval

        self._client: httpx.AsyncClient | None = None
        self._polling_task: asyncio.Task | None = None
        self._webhook_callback: EventCallback | None = None
        self._running = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        return self._client

    async def start(self, callback: EventCallback) -> None:
        """Start receiving GitHub events.

        Args:
            callback: Async function to call for each event
        """
        self._running = True

        if self.webhook_secret:
            # Webhook mode: events come via HTTP
            self._webhook_callback = callback
            logger.info("GitHub adapter started in webhook mode")
        else:
            # Polling mode: poll API periodically
            self._polling_task = asyncio.create_task(self._poll_loop(callback))
            logger.info(f"GitHub adapter started in polling mode (interval: {self.polling_interval}s)")

    async def stop(self) -> None:
        """Stop receiving events."""
        self._running = False

        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("GitHub adapter stopped")

    async def _poll_loop(self, callback: EventCallback) -> None:
        """Poll GitHub API for events."""
        last_check = datetime.now(UTC)

        while self._running:
            try:
                events = []
                events.extend(await self._poll_workflow_runs(last_check))
                events.extend(await self._poll_issues(last_check))
                events.extend(await self._poll_pull_requests(last_check))

                for event in events:
                    await callback(event)

                last_check = datetime.now(UTC)

            except Exception as e:
                logger.error(f"GitHub polling error: {e}")

            await asyncio.sleep(self.polling_interval)

    async def _poll_workflow_runs(self, since: datetime) -> list[ExternalEvent]:
        """Poll for workflow runs (CI)."""
        if not self.repo:
            return []

        events = []
        client = await self._get_client()

        try:
            response = await client.get(
                f"/repos/{self.repo}/actions/runs",
                params={"per_page": 10},
            )
            response.raise_for_status()
            data = response.json()

            for run in data.get("workflow_runs", []):
                updated_at = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                if updated_at <= since:
                    continue

                if run.get("status") != "completed":
                    continue

                event_type = (
                    EventType.CI_FAILURE
                    if run["conclusion"] == "failure"
                    else EventType.CI_SUCCESS
                )

                events.append(ExternalEvent(
                    id=f"github-workflow-{run['id']}",
                    source=EventSource.GITHUB,
                    event_type=event_type,
                    timestamp=updated_at,
                    data={
                        "workflow_name": run["name"],
                        "conclusion": run["conclusion"],
                        "branch": run["head_branch"],
                        "commit_sha": run["head_sha"],
                        "run_id": run["id"],
                    },
                    external_url=run["html_url"],
                    external_ref=f"github:workflow_run:{run['id']}",
                ))

        except Exception as e:
            logger.error(f"Error polling workflow runs: {e}")

        return events

    async def _poll_issues(self, since: datetime) -> list[ExternalEvent]:
        """Poll for new issues."""
        if not self.repo:
            return []

        events = []
        client = await self._get_client()

        try:
            response = await client.get(
                f"/repos/{self.repo}/issues",
                params={
                    "state": "open",
                    "since": since.isoformat(),
                    "per_page": 10,
                },
            )
            response.raise_for_status()
            issues = response.json()

            for issue in issues:
                # Skip pull requests (they appear in issues API)
                if "pull_request" in issue:
                    continue

                created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                if created_at <= since:
                    continue

                events.append(ExternalEvent(
                    id=f"github-issue-{issue['id']}-opened",
                    source=EventSource.GITHUB,
                    event_type=EventType.ISSUE_OPENED,
                    timestamp=created_at,
                    data={
                        "issue_number": issue["number"],
                        "title": issue["title"],
                        "body": issue.get("body", ""),
                        "labels": [l["name"] for l in issue.get("labels", [])],
                        "author": issue["user"]["login"],
                    },
                    external_url=issue["html_url"],
                    external_ref=f"github:issue:{issue['number']}",
                ))

        except Exception as e:
            logger.error(f"Error polling issues: {e}")

        return events

    async def _poll_pull_requests(self, since: datetime) -> list[ExternalEvent]:
        """Poll for new pull requests."""
        if not self.repo:
            return []

        events = []
        client = await self._get_client()

        try:
            response = await client.get(
                f"/repos/{self.repo}/pulls",
                params={
                    "state": "open",
                    "sort": "created",
                    "direction": "desc",
                    "per_page": 10,
                },
            )
            response.raise_for_status()
            prs = response.json()

            for pr in prs:
                created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                if created_at <= since:
                    continue

                events.append(ExternalEvent(
                    id=f"github-pr-{pr['id']}-opened",
                    source=EventSource.GITHUB,
                    event_type=EventType.PULL_REQUEST_OPENED,
                    timestamp=created_at,
                    data={
                        "pr_number": pr["number"],
                        "title": pr["title"],
                        "body": pr.get("body", ""),
                        "branch": pr["head"]["ref"],
                        "base_branch": pr["base"]["ref"],
                        "author": pr["user"]["login"],
                    },
                    external_url=pr["html_url"],
                    external_ref=f"github:pull_request:{pr['number']}",
                ))

        except Exception as e:
            logger.error(f"Error polling pull requests: {e}")

        return events

    def normalize_webhook(self, event_name: str, payload: dict) -> ExternalEvent | None:
        """Convert GitHub webhook payload to ExternalEvent.

        Args:
            event_name: GitHub event name from X-GitHub-Event header
            payload: Webhook payload

        Returns:
            Normalized ExternalEvent or None if not handled
        """
        match event_name:
            case "workflow_run":
                return self._normalize_workflow_run(payload)
            case "issues":
                return self._normalize_issue(payload)
            case "pull_request":
                return self._normalize_pull_request(payload)
            case _:
                return None

    def _normalize_workflow_run(self, payload: dict) -> ExternalEvent | None:
        """Normalize workflow_run webhook."""
        if payload.get("action") != "completed":
            return None

        run = payload["workflow_run"]
        event_type = (
            EventType.CI_FAILURE
            if run["conclusion"] == "failure"
            else EventType.CI_SUCCESS
        )

        return ExternalEvent(
            id=f"github-workflow-{run['id']}",
            source=EventSource.GITHUB,
            event_type=event_type,
            timestamp=datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00")),
            data={
                "workflow_name": run["name"],
                "conclusion": run["conclusion"],
                "branch": run["head_branch"],
                "commit_sha": run["head_sha"],
                "run_id": run["id"],
            },
            external_url=run["html_url"],
            external_ref=f"github:workflow_run:{run['id']}",
            raw_payload=payload,
        )

    def _normalize_issue(self, payload: dict) -> ExternalEvent | None:
        """Normalize issues webhook."""
        action = payload.get("action")
        issue = payload.get("issue", {})

        if action == "opened":
            return ExternalEvent(
                id=f"github-issue-{issue['id']}-opened",
                source=EventSource.GITHUB,
                event_type=EventType.ISSUE_OPENED,
                timestamp=datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")),
                data={
                    "issue_number": issue["number"],
                    "title": issue["title"],
                    "body": issue.get("body", ""),
                    "labels": [l["name"] for l in issue.get("labels", [])],
                    "author": issue["user"]["login"],
                },
                external_url=issue["html_url"],
                external_ref=f"github:issue:{issue['number']}",
                raw_payload=payload,
            )
        elif action == "closed":
            return ExternalEvent(
                id=f"github-issue-{issue['id']}-closed",
                source=EventSource.GITHUB,
                event_type=EventType.ISSUE_CLOSED,
                timestamp=datetime.now(UTC),
                data={
                    "issue_number": issue["number"],
                    "title": issue["title"],
                },
                external_url=issue["html_url"],
                external_ref=f"github:issue:{issue['number']}",
                raw_payload=payload,
            )
        elif action == "labeled":
            return ExternalEvent(
                id=f"github-issue-{issue['id']}-labeled-{payload.get('label', {}).get('name', '')}",
                source=EventSource.GITHUB,
                event_type=EventType.ISSUE_LABELED,
                timestamp=datetime.now(UTC),
                data={
                    "issue_number": issue["number"],
                    "title": issue["title"],
                    "label": payload.get("label", {}).get("name"),
                },
                external_url=issue["html_url"],
                external_ref=f"github:issue:{issue['number']}",
                raw_payload=payload,
            )

        return None

    def _normalize_pull_request(self, payload: dict) -> ExternalEvent | None:
        """Normalize pull_request webhook."""
        action = payload.get("action")
        pr = payload.get("pull_request", {})

        if action == "opened":
            return ExternalEvent(
                id=f"github-pr-{pr['id']}-opened",
                source=EventSource.GITHUB,
                event_type=EventType.PULL_REQUEST_OPENED,
                timestamp=datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")),
                data={
                    "pr_number": pr["number"],
                    "title": pr["title"],
                    "body": pr.get("body", ""),
                    "branch": pr["head"]["ref"],
                    "base_branch": pr["base"]["ref"],
                    "author": pr["user"]["login"],
                },
                external_url=pr["html_url"],
                external_ref=f"github:pull_request:{pr['number']}",
                raw_payload=payload,
            )
        elif action == "closed":
            event_type = (
                EventType.PULL_REQUEST_MERGED
                if pr.get("merged")
                else EventType.PULL_REQUEST_CLOSED
            )
            return ExternalEvent(
                id=f"github-pr-{pr['id']}-closed",
                source=EventSource.GITHUB,
                event_type=event_type,
                timestamp=datetime.now(UTC),
                data={
                    "pr_number": pr["number"],
                    "title": pr["title"],
                    "merged": pr.get("merged", False),
                },
                external_url=pr["html_url"],
                external_ref=f"github:pull_request:{pr['number']}",
                raw_payload=payload,
            )

        return None

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature.

        Args:
            payload: Raw request body bytes
            signature: X-Hub-Signature-256 header value

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

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Post feedback as a comment or status update.

        Args:
            event: Original event
            feedback: Feedback to send
        """
        if not self.repo:
            return

        client = await self._get_client()
        message = self._format_feedback_message(feedback)

        try:
            match event.event_type:
                case EventType.CI_FAILURE | EventType.CI_SUCCESS:
                    # Comment on the commit
                    commit_sha = event.data.get("commit_sha")
                    if commit_sha:
                        await client.post(
                            f"/repos/{self.repo}/commits/{commit_sha}/comments",
                            json={"body": message},
                        )

                case EventType.ISSUE_OPENED | EventType.ISSUE_LABELED:
                    # Comment on the issue
                    issue_number = event.data.get("issue_number")
                    if issue_number:
                        await client.post(
                            f"/repos/{self.repo}/issues/{issue_number}/comments",
                            json={"body": message},
                        )

                case EventType.PULL_REQUEST_OPENED:
                    # Comment on the PR
                    pr_number = event.data.get("pr_number")
                    if pr_number:
                        await client.post(
                            f"/repos/{self.repo}/issues/{pr_number}/comments",
                            json={"body": message},
                        )

        except Exception as e:
            logger.error(f"Error sending feedback to GitHub: {e}")

    def _format_feedback_message(self, feedback: EventFeedback) -> str:
        """Format feedback as GitHub-flavored markdown.

        Args:
            feedback: Feedback to format

        Returns:
            Formatted message
        """
        lines = [
            f"{STATUS_EMOJI.get(feedback.status, '🤖')} **Sunwell**: {feedback.status.title()}",
            "",
            feedback.message,
        ]

        if feedback.commit_sha:
            lines.append(f"\n**Fix**: `{feedback.commit_sha[:7]}`")

        if feedback.goal_id:
            lines.append(f"\n**Goal**: `{feedback.goal_id}`")

        return "\n".join(lines)

    async def handle_webhook(self, event_name: str, payload: dict) -> ExternalEvent | None:
        """Handle incoming webhook and notify callback.

        Args:
            event_name: GitHub event name
            payload: Webhook payload

        Returns:
            Normalized event if handled
        """
        event = self.normalize_webhook(event_name, payload)

        if event and self._webhook_callback:
            await self._webhook_callback(event)

        return event
