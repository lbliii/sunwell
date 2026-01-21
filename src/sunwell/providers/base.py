"""Provider Base Interfaces (RFC-075, RFC-078).

Abstract interfaces for data providers: Calendar, Lists, Notes, Files, Projects.
Implementations can be Sunwell-native or external integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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
