"""Core Types for External Integration (RFC-049).

Defines external event types, sources, and normalized event structure.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol


class EventSource(Enum):
    """Supported external event sources."""

    GITHUB = "github"
    GITLAB = "gitlab"
    LINEAR = "linear"
    JIRA = "jira"
    SENTRY = "sentry"
    DATADOG = "datadog"
    CRON = "cron"
    MANUAL = "manual"


class EventType(Enum):
    """Types of external events."""

    # CI/CD Events
    CI_FAILURE = "ci_failure"
    CI_SUCCESS = "ci_success"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYMENT_COMPLETED = "deployment_completed"
    DEPLOYMENT_FAILED = "deployment_failed"

    # Git Events
    PUSH = "push"
    PULL_REQUEST_OPENED = "pull_request_opened"
    PULL_REQUEST_MERGED = "pull_request_merged"
    PULL_REQUEST_CLOSED = "pull_request_closed"
    BRANCH_CREATED = "branch_created"
    BRANCH_DELETED = "branch_deleted"
    TAG_CREATED = "tag_created"

    # Issue Events
    ISSUE_OPENED = "issue_opened"
    ISSUE_ASSIGNED = "issue_assigned"
    ISSUE_LABELED = "issue_labeled"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_COMMENTED = "issue_commented"

    # Production Events
    ERROR_SPIKE = "error_spike"
    LATENCY_SPIKE = "latency_spike"
    ERROR_NEW = "error_new"
    ALERT_TRIGGERED = "alert_triggered"

    # Scheduled Events
    CRON_TRIGGER = "cron_trigger"


@dataclass(frozen=True, slots=True)
class ExternalEvent:
    """A normalized external event from any source."""

    id: str
    """Unique event identifier."""

    source: EventSource
    """Where this event came from."""

    event_type: EventType
    """Type of event."""

    timestamp: datetime
    """When the event occurred."""

    data: dict
    """Source-specific event data."""

    external_url: str | None = None
    """URL to the event in the external system."""

    external_ref: str | None = None
    """External reference ID (e.g., 'github:issue:123')."""

    raw_payload: dict | None = None
    """Original webhook payload for debugging."""

    @property
    def priority_hint(self) -> float:
        """Suggest priority based on event type."""
        match self.event_type:
            case EventType.CI_FAILURE | EventType.DEPLOYMENT_FAILED:
                return 0.95  # Critical
            case EventType.ERROR_SPIKE | EventType.ALERT_TRIGGERED:
                return 0.90  # High
            case EventType.ISSUE_OPENED:
                return 0.70  # Medium
            case EventType.PULL_REQUEST_OPENED:
                return 0.60  # Normal
            case _:
                return 0.50  # Default


@dataclass(frozen=True, slots=True)
class EventFeedback:
    """Feedback to send back to external service."""

    event_id: str
    """Original event ID."""

    status: Literal["acknowledged", "investigating", "fixed", "skipped"]
    """Status of Sunwell's response."""

    message: str
    """Human-readable message."""

    commit_sha: str | None = None
    """Commit SHA if a fix was applied."""

    goal_id: str | None = None
    """Internal goal ID for tracking."""


class EventCallback(Protocol):
    """Protocol for event callback functions."""

    async def __call__(self, event: ExternalEvent) -> None:
        """Handle an external event."""
        ...
