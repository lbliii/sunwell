"""Sunwell Native Calendar Provider (RFC-075).

Local calendar stored in .sunwell/calendar.json.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sunwell.models.providers.base import CalendarEvent, CalendarProvider


class SunwellCalendar(CalendarProvider):
    """Sunwell-native calendar stored in .sunwell/calendar.json."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "calendar.json"
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]")

    def _load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, events: list[dict]) -> None:
        self.path.write_text(json.dumps(events, default=str, indent=2))

    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Get events in date range."""
        data = self._load()
        events = []

        for e in data:
            event_start = datetime.fromisoformat(e["start"])
            if start <= event_start <= end:
                events.append(
                    CalendarEvent(
                        id=e["id"],
                        title=e["title"],
                        start=event_start,
                        end=datetime.fromisoformat(e["end"]),
                        location=e.get("location"),
                        notes=e.get("notes"),
                    )
                )

        return sorted(events, key=lambda e: e.start)

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new event."""
        data = self._load()

        new_event = CalendarEvent(
            id=str(uuid4()),
            title=event.title,
            start=event.start,
            end=event.end,
            location=event.location,
            notes=event.notes,
        )

        data.append({
            "id": new_event.id,
            "title": new_event.title,
            "start": new_event.start.isoformat(),
            "end": new_event.end.isoformat(),
            "location": new_event.location,
            "notes": new_event.notes,
        })

        self._save(data)
        return new_event

    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        """Update an existing event."""
        data = self._load()

        for i, e in enumerate(data):
            if e["id"] == event.id:
                data[i] = {
                    "id": event.id,
                    "title": event.title,
                    "start": event.start.isoformat(),
                    "end": event.end.isoformat(),
                    "location": event.location,
                    "notes": event.notes,
                }
                break

        self._save(data)
        return event

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        data = self._load()
        original_len = len(data)
        data = [e for e in data if e["id"] != event_id]
        self._save(data)
        return len(data) < original_len
