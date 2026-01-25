"""Event Adapters for External Integration (RFC-049).

Adapters normalize events from different external sources.
"""

from sunwell.features.external.adapters.base import EventAdapter
from sunwell.features.external.adapters.github import GitHubAdapter
from sunwell.features.external.adapters.linear import LinearAdapter
from sunwell.features.external.adapters.sentry import SentryAdapter

__all__ = [
    "EventAdapter",
    "GitHubAdapter",
    "LinearAdapter",
    "SentryAdapter",
]
