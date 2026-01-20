"""External Goal Policy (RFC-049).

Policy for handling external events as goals.
"""

from dataclasses import dataclass

from sunwell.external.types import EventSource, EventType, ExternalEvent


@dataclass
class ExternalGoalPolicy:
    """Policy for handling external events as goals.

    Controls which events become goals and their behavior.
    """

    # === Event Filtering ===

    enabled_sources: frozenset[EventSource] = frozenset({
        EventSource.GITHUB,
        EventSource.GITLAB,
    })
    """Which event sources to process."""

    enabled_event_types: frozenset[EventType] = frozenset({
        EventType.CI_FAILURE,
        EventType.ISSUE_OPENED,
        EventType.ALERT_TRIGGERED,
    })
    """Which event types to process."""

    issue_label_filter: frozenset[str] | None = None
    """Only process issues with these labels. None = all issues."""

    exclude_labels: frozenset[str] = frozenset({"wontfix", "duplicate", "sunwell-skip"})
    """Skip issues with these labels."""

    min_priority: float = 0.3
    """Minimum priority to create goal (filter low-value events)."""

    # === Auto-Approval ===

    auto_approve_issues: bool = False
    """Auto-approve goals from issues (requires guardrails check)."""

    auto_approve_ci_failures: bool = False
    """Auto-approve CI failure investigations."""

    # === Rate Limiting ===

    max_events_per_hour: int = 50
    """Maximum events to process per hour (prevent runaway)."""

    max_goals_per_day: int = 20
    """Maximum goals to create per day."""

    cooldown_minutes: int = 5
    """Minimum time between goals from same external ref."""

    def should_process(self, event: ExternalEvent) -> bool:
        """Check if event should be processed.

        Args:
            event: The external event to check

        Returns:
            True if the event should be processed
        """
        # Check source
        if event.source not in self.enabled_sources:
            return False

        # Check event type
        if event.event_type not in self.enabled_event_types:
            return False

        # Check priority
        if event.priority_hint < self.min_priority:
            return False

        # Check issue labels
        if event.event_type == EventType.ISSUE_OPENED:
            labels = set(event.data.get("labels", []))

            # Exclude blocked labels
            if labels & self.exclude_labels:
                return False

            # Include only allowed labels (if filter set)
            if self.issue_label_filter is not None and not (labels & self.issue_label_filter):
                return False

        return True
