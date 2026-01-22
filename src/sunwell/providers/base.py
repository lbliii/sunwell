"""Provider Base Interfaces (RFC-075, RFC-078).

Abstract interfaces for data providers: Calendar, Lists, Notes, Files, Projects.
Implementations can be Sunwell-native or external integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A calendar event."""

    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "location": self.location,
            "notes": self.notes,
        }


class CalendarProvider(ABC):
    """Calendar data provider interface."""

    @abstractmethod
    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Get events in date range."""
        ...

    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new event. Returns event with assigned ID."""
        ...

    @abstractmethod
    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        """Update an existing event."""
        ...

    @abstractmethod
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event. Returns True if deleted."""
        ...


@dataclass(frozen=True, slots=True)
class ListItem:
    """An item in a list."""

    id: str
    text: str
    completed: bool = False
    list_name: str = "default"
    created: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "list_name": self.list_name,
            "created": self.created.isoformat() if self.created else None,
        }


class ListProvider(ABC):
    """List/todo data provider interface."""

    @abstractmethod
    async def get_lists(self) -> list[str]:
        """Get all list names."""
        ...

    @abstractmethod
    async def get_items(
        self, list_name: str, include_completed: bool = False
    ) -> list[ListItem]:
        """Get items in a list."""
        ...

    @abstractmethod
    async def add_item(self, list_name: str, text: str) -> ListItem:
        """Add item to list. Creates list if needed."""
        ...

    @abstractmethod
    async def complete_item(self, item_id: str) -> ListItem:
        """Mark item as complete."""
        ...

    @abstractmethod
    async def delete_item(self, item_id: str) -> bool:
        """Delete an item."""
        ...


@dataclass(frozen=True, slots=True)
class Note:
    """A note/document."""

    id: str
    title: str
    content: str
    created: datetime
    modified: datetime
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "tags": list(self.tags),
        }


class NotesProvider(ABC):
    """Notes/documents provider interface."""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search notes by content."""
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 10) -> list[Note]:
        """Get recently modified notes."""
        ...

    @abstractmethod
    async def get_by_id(self, note_id: str) -> Note | None:
        """Get a specific note."""
        ...

    @abstractmethod
    async def create(
        self, title: str, content: str, tags: list[str] | None = None
    ) -> Note:
        """Create a new note."""
        ...

    @abstractmethod
    async def update(self, note: Note) -> Note:
        """Update an existing note."""
        ...


# =============================================================================
# FILES PROVIDER (RFC-078)
# =============================================================================


@dataclass(frozen=True, slots=True)
class FileInfo:
    """Information about a file."""

    path: str
    name: str
    size: int
    modified: datetime
    is_directory: bool
    extension: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "modified": self.modified.isoformat(),
            "is_directory": self.is_directory,
            "extension": self.extension,
        }


class FilesProvider(ABC):
    """File system provider interface (RFC-078)."""

    @abstractmethod
    async def list_files(
        self, path: str, recursive: bool = False
    ) -> list[FileInfo]:
        """List files in a directory."""
        ...

    @abstractmethod
    async def search_files(
        self, query: str, path: str | None = None
    ) -> list[FileInfo]:
        """Search files by name pattern."""
        ...

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read file contents as text."""
        ...

    @abstractmethod
    async def get_metadata(self, path: str) -> FileInfo | None:
        """Get metadata for a specific file."""
        ...


# =============================================================================
# PROJECTS PROVIDER (RFC-078)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Project:
    """A workspace project."""

    path: str
    name: str
    last_opened: datetime
    status: str  # "active", "archived", "template"
    description: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "name": self.name,
            "last_opened": self.last_opened.isoformat(),
            "status": self.status,
            "description": self.description,
        }


class ProjectsProvider(ABC):
    """Projects provider interface (RFC-078)."""

    @abstractmethod
    async def list_projects(self) -> list[Project]:
        """List all known projects."""
        ...

    @abstractmethod
    async def get_project(self, path: str) -> Project | None:
        """Get a specific project by path."""
        ...

    @abstractmethod
    async def search_projects(self, query: str) -> list[Project]:
        """Search projects by name."""
        ...

    @abstractmethod
    async def update_last_opened(self, path: str) -> Project | None:
        """Update last_opened timestamp for a project."""
        ...


# =============================================================================
# GIT PROVIDER (RFC-078 Phase 2)
# =============================================================================


@dataclass(frozen=True, slots=True)
class GitFileStatus:
    """Status of a single file in git."""

    path: str
    status: str  # "modified", "added", "deleted", "renamed", "untracked"
    staged: bool = False

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "status": self.status,
            "staged": self.staged,
        }


@dataclass(frozen=True, slots=True)
class GitStatus:
    """Git repository status."""

    branch: str
    ahead: int = 0
    behind: int = 0
    files: tuple[GitFileStatus, ...] = ()
    is_clean: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "branch": self.branch,
            "ahead": self.ahead,
            "behind": self.behind,
            "files": [f.to_dict() for f in self.files],
            "is_clean": self.is_clean,
        }


@dataclass(frozen=True, slots=True)
class GitCommit:
    """A git commit."""

    hash: str
    short_hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "hash": self.hash,
            "short_hash": self.short_hash,
            "author": self.author,
            "email": self.email,
            "date": self.date.isoformat(),
            "message": self.message,
            "files_changed": self.files_changed,
        }


@dataclass(frozen=True, slots=True)
class GitBranch:
    """A git branch."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "is_current": self.is_current,
            "is_remote": self.is_remote,
            "upstream": self.upstream,
        }


class GitProvider(ABC):
    """Git repository provider interface (RFC-078 Phase 2)."""

    @abstractmethod
    async def get_status(self, path: str | None = None) -> GitStatus:
        """Get repository status (branch, staged/unstaged changes)."""
        ...

    @abstractmethod
    async def get_log(
        self, path: str | None = None, limit: int = 50
    ) -> list[GitCommit]:
        """Get commit history."""
        ...

    @abstractmethod
    async def get_branches(self, path: str | None = None) -> list[GitBranch]:
        """Get all branches (local and remote)."""
        ...

    @abstractmethod
    async def get_diff(
        self, path: str | None = None, ref: str = "HEAD"
    ) -> str:
        """Get diff against a reference (default: HEAD for unstaged changes)."""
        ...

    @abstractmethod
    async def search_commits(
        self, query: str, path: str | None = None, limit: int = 20
    ) -> list[GitCommit]:
        """Search commits by message or author."""
        ...


# =============================================================================
# BOOKMARKS PROVIDER (RFC-078 Phase 2)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Bookmark:
    """A saved bookmark/link."""

    id: str
    url: str
    title: str
    tags: tuple[str, ...] = ()
    description: str | None = None
    created: datetime | None = None
    favicon: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "tags": list(self.tags),
            "description": self.description,
            "created": self.created.isoformat() if self.created else None,
            "favicon": self.favicon,
        }


class BookmarksProvider(ABC):
    """Bookmarks provider interface (RFC-078 Phase 2)."""

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Bookmark]:
        """Search bookmarks by title, URL, or description."""
        ...

    @abstractmethod
    async def get_by_tag(self, tag: str) -> list[Bookmark]:
        """Get all bookmarks with a specific tag."""
        ...

    @abstractmethod
    async def get_all_tags(self) -> list[str]:
        """Get all unique tags."""
        ...

    @abstractmethod
    async def add_bookmark(
        self,
        url: str,
        title: str,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Bookmark:
        """Add a new bookmark."""
        ...

    @abstractmethod
    async def delete_bookmark(self, bookmark_id: str) -> bool:
        """Delete a bookmark."""
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 20) -> list[Bookmark]:
        """Get recently added bookmarks."""
        ...


# =============================================================================
# HABITS PROVIDER (RFC-078 Phase 4)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Habit:
    """A trackable habit."""

    id: str
    name: str
    description: str | None = None
    frequency: str = "daily"  # "daily", "weekly", "custom"
    target_count: int = 1  # How many times per frequency period
    color: str | None = None
    icon: str | None = None
    created: datetime | None = None
    archived: bool = False

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency,
            "target_count": self.target_count,
            "color": self.color,
            "icon": self.icon,
            "created": self.created.isoformat() if self.created else None,
            "archived": self.archived,
        }


@dataclass(frozen=True, slots=True)
class HabitEntry:
    """A single habit completion entry."""

    id: str
    habit_id: str
    date: datetime
    count: int = 1
    notes: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "habit_id": self.habit_id,
            "date": self.date.isoformat(),
            "count": self.count,
            "notes": self.notes,
        }


class HabitsProvider(ABC):
    """Habits tracking provider interface (RFC-078 Phase 4)."""

    @abstractmethod
    async def list_habits(self, include_archived: bool = False) -> list[Habit]:
        """List all habits."""
        ...

    @abstractmethod
    async def get_habit(self, habit_id: str) -> Habit | None:
        """Get a specific habit by ID."""
        ...

    @abstractmethod
    async def create_habit(
        self,
        name: str,
        description: str | None = None,
        frequency: str = "daily",
        target_count: int = 1,
    ) -> Habit:
        """Create a new habit to track."""
        ...

    @abstractmethod
    async def archive_habit(self, habit_id: str) -> Habit | None:
        """Archive a habit (soft delete)."""
        ...

    @abstractmethod
    async def log_entry(
        self,
        habit_id: str,
        date: datetime | None = None,
        count: int = 1,
        notes: str | None = None,
    ) -> HabitEntry:
        """Log a habit completion entry."""
        ...

    @abstractmethod
    async def get_entries(
        self,
        habit_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[HabitEntry]:
        """Get entries for a habit in a date range."""
        ...

    @abstractmethod
    async def get_streak(self, habit_id: str) -> int:
        """Get the current streak for a habit (consecutive days completed)."""
        ...


# =============================================================================
# CONTACTS PROVIDER (RFC-078 Phase 4)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Contact:
    """A contact/person."""

    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    organization: str | None = None
    title: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    birthday: datetime | None = None
    created: datetime | None = None
    modified: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "organization": self.organization,
            "title": self.title,
            "notes": self.notes,
            "tags": list(self.tags),
            "birthday": self.birthday.isoformat() if self.birthday else None,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
        }


class ContactsProvider(ABC):
    """Contacts provider interface (RFC-078 Phase 4)."""

    @abstractmethod
    async def list_contacts(self, limit: int = 100) -> list[Contact]:
        """List all contacts."""
        ...

    @abstractmethod
    async def get_contact(self, contact_id: str) -> Contact | None:
        """Get a specific contact by ID."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Contact]:
        """Search contacts by name, email, or organization."""
        ...

    @abstractmethod
    async def get_by_tag(self, tag: str) -> list[Contact]:
        """Get contacts with a specific tag."""
        ...

    @abstractmethod
    async def create_contact(
        self,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        organization: str | None = None,
        tags: list[str] | None = None,
    ) -> Contact:
        """Create a new contact."""
        ...

    @abstractmethod
    async def update_contact(self, contact: Contact) -> Contact:
        """Update an existing contact."""
        ...

    @abstractmethod
    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact."""
        ...
