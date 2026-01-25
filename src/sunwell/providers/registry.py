"""Provider Registry (RFC-075, RFC-078).

Central registry for data providers. Allows swapping implementations
(Sunwell native vs external integrations).
"""

from dataclasses import dataclass
from pathlib import Path

from sunwell.providers.base import (
    BookmarksProvider,
    CalendarProvider,
    ContactsProvider,
    FilesProvider,
    GitProvider,
    HabitsProvider,
    ListProvider,
    NotesProvider,
    ProjectsProvider,
)


@dataclass(slots=True)
class ProviderRegistry:
    """Registry for data providers.

    Allows swapping implementations (Sunwell native vs external integrations).
    """

    _calendar: CalendarProvider | None = None
    _lists: ListProvider | None = None
    _notes: NotesProvider | None = None
    _files: FilesProvider | None = None
    _projects: ProjectsProvider | None = None
    _git: GitProvider | None = None
    _bookmarks: BookmarksProvider | None = None
    _habits: HabitsProvider | None = None
    _contacts: ContactsProvider | None = None

    @classmethod
    def create_default(
        cls,
        data_dir: Path,
        workspace_root: Path | None = None,
    ) -> ProviderRegistry:
        """Create registry with Sunwell-native providers.

        Args:
            data_dir: The .sunwell data directory.
            workspace_root: The workspace root for file operations.
        """
        from sunwell.providers.native import (
            SunwellBookmarks,
            SunwellCalendar,
            SunwellContacts,
            SunwellFiles,
            SunwellGit,
            SunwellHabits,
            SunwellLists,
            SunwellNotes,
            SunwellProjects,
        )

        root = workspace_root or data_dir.parent
        return cls(
            _calendar=SunwellCalendar(data_dir),
            _lists=SunwellLists(data_dir),
            _notes=SunwellNotes(data_dir),
            _files=SunwellFiles(root),
            _projects=SunwellProjects(data_dir),
            _git=SunwellGit(root),
            _bookmarks=SunwellBookmarks(data_dir),
            _habits=SunwellHabits(data_dir),
            _contacts=SunwellContacts(data_dir),
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

    @property
    def files(self) -> FilesProvider:
        """Get files provider."""
        if not self._files:
            raise RuntimeError("Files provider not configured")
        return self._files

    @property
    def projects(self) -> ProjectsProvider:
        """Get projects provider."""
        if not self._projects:
            raise RuntimeError("Projects provider not configured")
        return self._projects

    @property
    def git(self) -> GitProvider:
        """Get git provider."""
        if not self._git:
            raise RuntimeError("Git provider not configured")
        return self._git

    @property
    def bookmarks(self) -> BookmarksProvider:
        """Get bookmarks provider."""
        if not self._bookmarks:
            raise RuntimeError("Bookmarks provider not configured")
        return self._bookmarks

    @property
    def habits(self) -> HabitsProvider:
        """Get habits provider."""
        if not self._habits:
            raise RuntimeError("Habits provider not configured")
        return self._habits

    @property
    def contacts(self) -> ContactsProvider:
        """Get contacts provider."""
        if not self._contacts:
            raise RuntimeError("Contacts provider not configured")
        return self._contacts

    def register_calendar(self, provider: CalendarProvider) -> None:
        """Register a calendar provider (e.g., Google Calendar)."""
        self._calendar = provider

    def register_lists(self, provider: ListProvider) -> None:
        """Register a lists provider (e.g., Todoist)."""
        self._lists = provider

    def register_notes(self, provider: NotesProvider) -> None:
        """Register a notes provider (e.g., Obsidian)."""
        self._notes = provider

    def register_files(self, provider: FilesProvider) -> None:
        """Register a files provider."""
        self._files = provider

    def register_projects(self, provider: ProjectsProvider) -> None:
        """Register a projects provider."""
        self._projects = provider

    def register_git(self, provider: GitProvider) -> None:
        """Register a git provider."""
        self._git = provider

    def register_bookmarks(self, provider: BookmarksProvider) -> None:
        """Register a bookmarks provider."""
        self._bookmarks = provider

    def register_habits(self, provider: HabitsProvider) -> None:
        """Register a habits provider."""
        self._habits = provider

    def register_contacts(self, provider: ContactsProvider) -> None:
        """Register a contacts provider."""
        self._contacts = provider

    def has_calendar(self) -> bool:
        """Check if calendar provider is configured."""
        return self._calendar is not None

    def has_lists(self) -> bool:
        """Check if lists provider is configured."""
        return self._lists is not None

    def has_notes(self) -> bool:
        """Check if notes provider is configured."""
        return self._notes is not None

    def has_files(self) -> bool:
        """Check if files provider is configured."""
        return self._files is not None

    def has_projects(self) -> bool:
        """Check if projects provider is configured."""
        return self._projects is not None

    def has_git(self) -> bool:
        """Check if git provider is configured."""
        return self._git is not None

    def has_bookmarks(self) -> bool:
        """Check if bookmarks provider is configured."""
        return self._bookmarks is not None

    def has_habits(self) -> bool:
        """Check if habits provider is configured."""
        return self._habits is not None

    def has_contacts(self) -> bool:
        """Check if contacts provider is configured."""
        return self._contacts is not None
