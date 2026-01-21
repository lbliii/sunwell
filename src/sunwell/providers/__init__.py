"""Data Providers — Pluggable Interfaces for Calendar, Lists, Notes (RFC-075).

This module provides abstract interfaces for data providers and
Sunwell-native implementations. External integrations (Google Calendar,
Todoist, Obsidian) can be added later via these interfaces.
"""

from sunwell.providers.base import (
    CalendarEvent,
    CalendarProvider,
    ListItem,
    ListProvider,
    Note,
    NotesProvider,
)
from sunwell.providers.registry import ProviderRegistry

__all__ = [
    # Base interfaces
    "CalendarEvent",
    "CalendarProvider",
    "ListItem",
    "ListProvider",
    "Note",
    "NotesProvider",
    # Registry
    "ProviderRegistry",
]
