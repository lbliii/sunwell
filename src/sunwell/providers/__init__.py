"""Data Providers — Pluggable Interfaces (RFC-075, RFC-078).

This module provides abstract interfaces for data providers and
Sunwell-native implementations. External integrations (Google Calendar,
Todoist, Obsidian) can be added later via these interfaces.
"""

from sunwell.providers.base import (
    Bookmark,
    BookmarksProvider,
    CalendarEvent,
    CalendarProvider,
    Contact,
    ContactsProvider,
    FileInfo,
    FilesProvider,
    GitBranch,
    GitCommit,
    GitFileStatus,
    GitProvider,
    GitStatus,
    Habit,
    HabitEntry,
    HabitsProvider,
    ListItem,
    ListProvider,
    Note,
    NotesProvider,
    Project,
    ProjectsProvider,
    Serializable,
)
from sunwell.providers.registry import ProviderRegistry

__all__ = [
    # Base interfaces
    "Bookmark",
    "BookmarksProvider",
    "CalendarEvent",
    "CalendarProvider",
    "Contact",
    "ContactsProvider",
    "FileInfo",
    "FilesProvider",
    "GitBranch",
    "GitCommit",
    "GitFileStatus",
    "GitProvider",
    "GitStatus",
    "Habit",
    "HabitEntry",
    "HabitsProvider",
    "ListItem",
    "ListProvider",
    "Note",
    "NotesProvider",
    "Project",
    "ProjectsProvider",
    "Serializable",
    # Registry
    "ProviderRegistry",
]
