"""Provider Registry (RFC-075).

Central registry for data providers. Allows swapping implementations
(Sunwell native vs external integrations).
"""

from dataclasses import dataclass
from pathlib import Path

from sunwell.providers.base import CalendarProvider, ListProvider, NotesProvider


@dataclass
class ProviderRegistry:
    """Registry for data providers.

    Allows swapping implementations (Sunwell native vs external integrations).
    """

    _calendar: CalendarProvider | None = None
    _lists: ListProvider | None = None
    _notes: NotesProvider | None = None

    @classmethod
    def create_default(cls, data_dir: Path) -> ProviderRegistry:
        """Create registry with Sunwell-native providers."""
        from sunwell.providers.native import SunwellCalendar, SunwellLists, SunwellNotes

        return cls(
            _calendar=SunwellCalendar(data_dir),
            _lists=SunwellLists(data_dir),
            _notes=SunwellNotes(data_dir),
        )

    @property
    def calendar(self) -> CalendarProvider:
        """Get calendar provider."""
        if not self._calendar:
            raise RuntimeError("Calendar provider not configured")
        return self._calendar

    @property
    def lists(self) -> ListProvider:
        """Get lists provider."""
        if not self._lists:
            raise RuntimeError("Lists provider not configured")
        return self._lists

    @property
    def notes(self) -> NotesProvider:
        """Get notes provider."""
        if not self._notes:
            raise RuntimeError("Notes provider not configured")
        return self._notes

    def register_calendar(self, provider: CalendarProvider) -> None:
        """Register a calendar provider (e.g., Google Calendar)."""
        self._calendar = provider

    def register_lists(self, provider: ListProvider) -> None:
        """Register a lists provider (e.g., Todoist)."""
        self._lists = provider

    def register_notes(self, provider: NotesProvider) -> None:
        """Register a notes provider (e.g., Obsidian)."""
        self._notes = provider

    def has_calendar(self) -> bool:
        """Check if calendar provider is configured."""
        return self._calendar is not None

    def has_lists(self) -> bool:
        """Check if lists provider is configured."""
        return self._lists is not None

    def has_notes(self) -> bool:
        """Check if notes provider is configured."""
        return self._notes is not None
