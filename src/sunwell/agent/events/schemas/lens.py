"""Lens event schemas (RFC-064, RFC-071)."""

from typing import TypedDict


class LensSelectedData(TypedDict, total=False):
    """Data for lens_selected event."""
    name: str  # Required
    version: str | None
    source: str | None


class LensChangedData(TypedDict, total=False):
    """Data for lens_changed event."""
    old_lens: str | None
    new_lens: str  # Required
    reason: str | None


class LensSuggestedData(TypedDict, total=False):
    """Data for lens_suggested event."""
    suggested: str  # Required
    reason: str  # Required
