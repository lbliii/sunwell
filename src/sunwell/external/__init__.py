"""External Integration for Sunwell (RFC-049).

Connects Sunwell to external services: CI/CD, Git, Issue Trackers, and Production Monitoring.
"""

from sunwell.external.context import ExternalContext
from sunwell.external.policy import ExternalGoalPolicy
from sunwell.external.processor import EventProcessor
from sunwell.external.ratelimit import RateLimitBucket, RateLimiter
from sunwell.external.store import ExternalEventStore
from sunwell.external.types import (
    EventCallback,
    EventFeedback,
    EventSource,
    EventType,
    ExternalEvent,
)

__all__ = [
    # Types
    "EventSource",
    "EventType",
    "ExternalEvent",
    "EventFeedback",
    "EventCallback",
    # Policy
    "ExternalGoalPolicy",
    # Rate Limiting
    "RateLimiter",
    "RateLimitBucket",
    # Processing
    "EventProcessor",
    "ExternalEventStore",
    # Context
    "ExternalContext",
]
