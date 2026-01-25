"""Event Processor for External Integration (RFC-049).

Translates external events into RFC-046 goals.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.features.backlog.goals import Goal, GoalScope
from sunwell.features.external.context import ExternalContext
from sunwell.features.external.policy import ExternalGoalPolicy
from sunwell.features.external.ratelimit import RateLimiter
from sunwell.features.external.store import ExternalEventStore
from sunwell.features.external.types import (
    EventFeedback,
    EventSource,
    EventType,
    ExternalEvent,
)

if TYPE_CHECKING:
    from sunwell.features.backlog.manager import BacklogManager
    from sunwell.features.external.adapters.base import EventAdapter

logger = logging.getLogger(__name__)


class EventProcessor:
    """Process external events and generate goals.

    Translation strategy:
    1. Receive ExternalEvent from adapter
    2. Check rate limits
    3. Check if similar goal already exists (dedupe)
    4. Translate to Goal using event-specific logic
    5. Add to BacklogManager (RFC-046)
    6. Optionally send acknowledgment back to source
    """

    def __init__(
        self,
        root: Path,
        backlog_manager: BacklogManager,
        goal_policy: ExternalGoalPolicy | None = None,
        feedback_enabled: bool = True,
    ):
        """Initialize event processor.

        Args:
            root: Project root directory
            backlog_manager: Backlog manager for adding goals
            goal_policy: Policy for filtering and handling events
            feedback_enabled: Whether to send feedback to sources
        """
        self.root = Path(root)
        self.backlog_manager = backlog_manager
        self.goal_policy = goal_policy or ExternalGoalPolicy()
        self.feedback_enabled = feedback_enabled

        self._adapters: dict[EventSource, EventAdapter] = {}
        self._rate_limiter = RateLimiter(self.goal_policy)
        self._store = ExternalEventStore(root)

    def register_adapter(self, adapter: EventAdapter) -> None:
        """Register an event adapter.

        Args:
            adapter: The adapter to register
        """
        self._adapters[adapter.source] = adapter

    async def process_event(self, event: ExternalEvent) -> Goal | None:
        """Process an external event and potentially create a goal.

        Args:
            event: The external event to process

        Returns:
            The created goal, or None if filtered/deduplicated
        """
        # 0. Write to WAL before processing
        await self._store.wal_append(event, status="received")

        try:
            # 1. Check policy (should we handle this event?)
            if not self.goal_policy.should_process(event):
                logger.debug(f"Event filtered by policy: {event.id}")
                await self._store.wal_append(event, status="filtered")
                return None

            # 2. Check rate limits
            allowed, reason = self._rate_limiter.allow(event)
            if not allowed:
                logger.warning(f"Event rate limited: {event.id} — {reason}")
                await self._store.wal_append(event, status="rate_limited", reason=reason)
                return None

            # 3. Check for duplicates
            if await self._is_duplicate(event):
                logger.debug(f"Duplicate event: {event.id}")
                await self._store.wal_append(event, status="duplicate")
                return None

            # 4. Translate to goal
            goal = await self._translate_to_goal(event)
            if goal is None:
                await self._store.wal_append(event, status="skipped")
                return None

            # 5. Add to backlog
            await self.backlog_manager.add_external_goal(goal)

            # 6. Store event and record goal creation
            await self._store.store(event)
            self._rate_limiter.record_goal_created(event)

            # 7. Send acknowledgment
            if self.feedback_enabled:
                adapter = self._adapters.get(event.source)
                if adapter:
                    await adapter.send_feedback(
                        event,
                        EventFeedback(
                            event_id=event.id,
                            status="acknowledged",
                            message=f"Added to Sunwell backlog: {goal.title}",
                            goal_id=goal.id,
                        ),
                    )

            await self._store.wal_append(event, status="processed", goal_id=goal.id)
            return goal

        except Exception as e:
            logger.error(f"Error processing event {event.id}: {e}")
            await self._store.wal_append(event, status="failed", error=str(e))
            raise

    async def _translate_to_goal(self, event: ExternalEvent) -> Goal | None:
        """Convert external event to a Goal.

        Args:
            event: The external event

        Returns:
            A Goal if translation succeeds, None otherwise
        """
        match event.event_type:
            case EventType.CI_FAILURE:
                return self._goal_from_ci_failure(event)
            case EventType.ISSUE_OPENED:
                return self._goal_from_issue(event)
            case EventType.ERROR_SPIKE | EventType.ALERT_TRIGGERED:
                return self._goal_from_alert(event)
            case EventType.PULL_REQUEST_OPENED:
                return self._goal_from_pr(event)
            case EventType.CRON_TRIGGER:
                return self._goal_from_cron(event)
            case _:
                return None

    def _goal_from_ci_failure(self, event: ExternalEvent) -> Goal:
        """Create goal from CI failure."""
        return Goal(
            id=f"ext-ci-{event.data.get('run_id', event.id)}",
            title=f"Investigate CI failure: {event.data.get('workflow_name', 'unknown')}",
            description=(
                f"CI workflow '{event.data.get('workflow_name')}' failed on branch "
                f"'{event.data.get('branch')}'. "
                f"Commit: {event.data.get('commit_sha', 'unknown')[:7]}.\n\n"
                f"View details: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=0.95,  # CI failures are high priority
            estimated_complexity="simple",  # Investigation first
            requires=frozenset(),
            category="fix",
            auto_approvable=False,  # CI failures need human review
            scope=GoalScope(max_files=5, max_lines_changed=200),
            external_ref=event.external_ref,
        )

    def _goal_from_issue(self, event: ExternalEvent) -> Goal:
        """Create goal from new issue."""
        title = event.data.get("title", "Unknown issue")
        labels = event.data.get("labels", [])

        # Determine category from labels
        category = "improve"
        if "bug" in labels or "fix" in labels:
            category = "fix"
        elif "enhancement" in labels or "feature" in labels:
            category = "add"
        elif "documentation" in labels:
            category = "document"

        # Determine complexity from labels
        complexity = "moderate"
        if "trivial" in labels or "good first issue" in labels:
            complexity = "simple"
        elif "complex" in labels or "epic" in labels:
            complexity = "complex"

        return Goal(
            id=f"ext-issue-{event.data.get('issue_number', event.id)}",
            title=f"Issue #{event.data.get('issue_number')}: {title[:60]}",
            description=(
                f"**Issue**: {title}\n\n"
                f"**Author**: {event.data.get('author', 'unknown')}\n"
                f"**Labels**: {', '.join(labels) if labels else 'none'}\n\n"
                f"**Body**:\n{event.data.get('body', 'No description provided.')}\n\n"
                f"**Link**: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=event.priority_hint,
            estimated_complexity=complexity,
            requires=frozenset(),
            category=category,
            auto_approvable=self.goal_policy.auto_approve_issues,
            scope=GoalScope(max_files=10, max_lines_changed=500),
            external_ref=event.external_ref,
        )

    def _goal_from_alert(self, event: ExternalEvent) -> Goal:
        """Create goal from production alert."""
        return Goal(
            id=f"ext-alert-{event.id}",
            title=f"Production alert: {event.data.get('title', 'Unknown')[:60]}",
            description=(
                f"**Alert**: {event.data.get('title')}\n\n"
                f"**Level**: {event.data.get('level', 'unknown')}\n"
                f"**Message**: {event.data.get('message', 'No message')}\n"
                f"**Culprit**: {event.data.get('culprit', 'unknown')}\n\n"
                f"**Link**: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=0.90,  # Production alerts are high priority
            estimated_complexity="moderate",
            requires=frozenset(),
            category="fix",
            auto_approvable=False,  # Production issues need review
            scope=GoalScope(max_files=5, max_lines_changed=200),
            external_ref=event.external_ref,
        )

    def _goal_from_pr(self, event: ExternalEvent) -> Goal:
        """Create goal from pull request."""
        title = event.data.get("title", "Unknown PR")

        return Goal(
            id=f"ext-pr-{event.data.get('pr_number', event.id)}",
            title=f"PR #{event.data.get('pr_number')}: {title[:60]}",
            description=(
                f"**Pull Request**: {title}\n\n"
                f"**Author**: {event.data.get('author', 'unknown')}\n"
                f"**Branch**: {event.data.get('branch')} → {event.data.get('base_branch')}\n\n"
                f"**Body**:\n{event.data.get('body', 'No description provided.')}\n\n"
                f"**Link**: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=event.priority_hint,
            estimated_complexity="moderate",
            requires=frozenset(),
            category="improve",  # PR review/assist
            auto_approvable=False,
            scope=GoalScope(max_files=15, max_lines_changed=1000),
            external_ref=event.external_ref,
        )

    def _goal_from_cron(self, event: ExternalEvent) -> Goal:
        """Create goal from cron trigger."""
        trigger = event.data.get("trigger", "scheduled")

        return Goal(
            id=f"ext-cron-{event.id}",
            title=f"Scheduled task: {trigger}",
            description=(
                f"Scheduled task triggered: {trigger}\n\n"
                f"Time: {event.timestamp.isoformat()}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=0.50,  # Scheduled tasks are normal priority
            estimated_complexity="moderate",
            requires=frozenset(),
            category="improve",
            auto_approvable=False,
            scope=GoalScope(max_files=10, max_lines_changed=500),
            external_ref=event.external_ref,
        )

    async def _is_duplicate(self, event: ExternalEvent) -> bool:
        """Check if a similar goal already exists.

        Args:
            event: The external event to check

        Returns:
            True if a duplicate goal exists
        """
        if not event.external_ref:
            return False

        existing_goals = await self.backlog_manager.get_goals_by_external_ref(
            event.external_ref
        )
        return len(existing_goals) > 0

    def create_external_context(self, event: ExternalEvent) -> ExternalContext:
        """Create an ExternalContext from an event for RFC-042 integration.

        Args:
            event: The external event

        Returns:
            ExternalContext for adaptive routing
        """
        context = ExternalContext.from_event(event.source, event.priority_hint)

        # Add CI logs if available
        if event.event_type == EventType.CI_FAILURE:
            logs = event.data.get("logs") or event.data.get("error_output")
            if logs:
                context = context.with_ci_logs(logs)

        # Add issue body if available
        if event.event_type == EventType.ISSUE_OPENED:
            body = event.data.get("body")
            if body:
                context = context.with_issue_body(body)

        return context

    async def recover_from_crash(self) -> list[str]:
        """Recover unprocessed events after crash.

        Returns:
            List of event IDs that were recovered
        """
        return await self._store.recover_from_crash()

    async def compact_wal(self) -> int:
        """Compact the write-ahead log.

        Returns:
            Number of entries removed
        """
        return await self._store.compact_wal()

    def get_rate_limit_stats(self) -> dict:
        """Get current rate limit statistics.

        Returns:
            Rate limit stats dictionary
        """
        return self._rate_limiter.get_stats()
