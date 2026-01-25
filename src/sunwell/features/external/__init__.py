"""External Integration for Sunwell (RFC-049).

Connects Sunwell to external services: CI/CD, Git, Issue Trackers, and Production Monitoring.
"""

from sunwell.features.external.context import ExternalContext
from sunwell.features.external.policy import ExternalGoalPolicy
from sunwell.features.external.processor import EventProcessor
from sunwell.features.external.ratelimit import RateLimitBucket, RateLimiter
from sunwell.features.external.store import ExternalEventStore
from sunwell.features.external.types import (
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
