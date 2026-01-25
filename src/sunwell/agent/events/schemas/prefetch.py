"""Prefetch event schemas."""

from typing import TypedDict


class PrefetchStartData(TypedDict, total=False):
    """Data for prefetch_start event."""
    sources: list[str]  # Required


class PrefetchCompleteData(TypedDict, total=False):
    """Data for prefetch_complete event."""
    duration_ms: int  # Required
    sources_loaded: int  # Required


class PrefetchTimeoutData(TypedDict, total=False):
    """Data for prefetch_timeout event."""
    timeout_ms: int  # Required
