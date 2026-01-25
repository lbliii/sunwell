"""Briefing event schemas."""

from typing import TypedDict


class BriefingLoadedData(TypedDict, total=False):
    """Data for briefing_loaded event."""
    path: str  # Required


class BriefingSavedData(TypedDict, total=False):
    """Data for briefing_saved event."""
    path: str  # Required
