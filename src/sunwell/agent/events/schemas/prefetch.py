"""Prefetch event schemas."""

from typing import TypedDict


class PrefetchStartData(TypedDict, total=False):
    """Data for prefetch_start event.

    Note: Factory provides briefing field.
    """

    briefing: str


class PrefetchCompleteData(TypedDict, total=False):
    """Data for prefetch_complete event.

    Note: Factory provides files_loaded/learnings_loaded/skills_activated.
    """

    files_loaded: int
    learnings_loaded: int
    skills_activated: list[str]


class PrefetchTimeoutData(TypedDict, total=False):
    """Data for prefetch_timeout event.

    Note: Factory provides error field.
    """

    error: str | None
