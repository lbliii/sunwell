"""Event Adapters for External Integration (RFC-049).

Adapters normalize events from different external sources.
"""

from sunwell.external.adapters.base import EventAdapter
from sunwell.external.adapters.github import GitHubAdapter
from sunwell.external.adapters.linear import LinearAdapter
from sunwell.external.adapters.sentry import SentryAdapter

__all__ = [
    "EventAdapter",
    "GitHubAdapter",
    "LinearAdapter",
    "SentryAdapter",
]
