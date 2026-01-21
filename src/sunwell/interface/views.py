"""View Renderer (RFC-075).

Renders views for calendar, lists, notes, and search.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sunwell.interface.types import ViewSpec
from sunwell.providers.registry import ProviderRegistry


@dataclass
class ViewRenderer:
    """Renders views based on ViewSpec."""

    providers: ProviderRegistry

    async def render(self, spec: ViewSpec) -> dict[str, Any]:
        """Render a view and return its data."""
        match spec.type:
            case "calendar":
                return await self._render_calendar(spec)
            case "list":
                return await self._render_list(spec)
            case "notes":
                return await self._render_notes(spec)
            case "search":
                return await self._render_search(spec)
            case _:
                return {"error": f"Unknown view type: {spec.type}"}

    async def _render_calendar(self, spec: ViewSpec) -> dict[str, Any]:
        """Render calendar view."""
        if not self.providers.has_calendar():
            return {"error": "Calendar provider not configured", "events": []}

        focus = spec.focus or {}

        # Parse date range
        start = self._parse_date(focus.get("start"))
        end = self._parse_date(focus.get("end"))

        # Default to next 7 days if no range specified
        if start is None:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = start + timedelta(days=7)

        events = await self.providers.calendar.get_events(start, end)

        return {
            "type": "calendar",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events": [e.to_dict() for e in events],
            "event_count": len(events),
        }

    async def _render_list(self, spec: ViewSpec) -> dict[str, Any]:
        """Render list view."""
        if not self.providers.has_lists():
            return {"error": "Lists provider not configured", "items": []}

        focus = spec.focus or {}
        list_name = focus.get("list_name", "default")
        include_completed = focus.get("include_completed", False)

        items = await self.providers.lists.get_items(list_name, include_completed)

        return {
            "type": "list",
            "list_name": list_name,
            "items": [i.to_dict() for i in items],
            "item_count": len(items),
            "completed_count": sum(1 for i in items if i.completed),
        }

    async def _render_notes(self, spec: ViewSpec) -> dict[str, Any]:
        """Render notes view."""
        if not self.providers.has_notes():
            return {"error": "Notes provider not configured", "notes": []}

        focus = spec.focus or {}

        if focus.get("search"):
            notes = await self.providers.notes.search(focus["search"])
            return {
                "type": "notes",
                "mode": "search",
                "query": focus["search"],
                "notes": [n.to_dict() for n in notes],
                "note_count": len(notes),
            }
        else:
            limit = focus.get("limit", 10)
            notes = await self.providers.notes.get_recent(limit)
            return {
                "type": "notes",
                "mode": "recent",
                "notes": [n.to_dict() for n in notes],
                "note_count": len(notes),
            }

    async def _render_search(self, spec: ViewSpec) -> dict[str, Any]:
        """Render search view across all providers."""
        query = spec.query or ""
        if not query:
            return {"error": "No search query provided", "results": []}

        results: list[dict[str, Any]] = []

        # Search notes
        if self.providers.has_notes():
            notes = await self.providers.notes.search(query, limit=5)
            for note in notes:
                preview = note.content[:100]
                if len(note.content) > 100:
                    preview += "..."
                results.append({
                    "type": "note",
                    "id": note.id,
                    "title": note.title,
                    "preview": preview,
                    "modified": note.modified.isoformat(),
                })

        # Search lists (search item text)
        if self.providers.has_lists():
            list_names = await self.providers.lists.get_lists()
            query_lower = query.lower()
            for list_name in list_names:
                items = await self.providers.lists.get_items(list_name, include_completed=True)
                for item in items:
                    if query_lower in item.text.lower():
                        results.append({
                            "type": "list_item",
                            "id": item.id,
                            "text": item.text,
                            "list": list_name,
                            "completed": item.completed,
                        })

        # Search calendar events
        if self.providers.has_calendar():
            now = datetime.now()
            events = await self.providers.calendar.get_events(
                now - timedelta(days=30),
                now + timedelta(days=90),
            )
            query_lower = query.lower()
            for event in events:
                if query_lower in event.title.lower() or (
                    event.notes and query_lower in event.notes.lower()
                ):
                    results.append({
                        "type": "event",
                        "id": event.id,
                        "title": event.title,
                        "start": event.start.isoformat(),
                        "end": event.end.isoformat(),
                    })

        return {
            "type": "search",
            "query": query,
            "results": results[:20],  # Limit results
            "result_count": len(results),
        }

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse a date string."""
        if not value:
            return None

        try:
            # Try ISO format first
            if "T" in value:
                return datetime.fromisoformat(value)
            else:
                return datetime.fromisoformat(value + "T00:00:00")
        except ValueError:
            pass

        # Try relative dates
        value_lower = value.lower()
        now = datetime.now()

        if value_lower == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif value_lower == "tomorrow":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif value_lower == "yesterday":
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif "saturday" in value_lower:
            days_ahead = 5 - now.weekday()  # Saturday is 5
            if days_ahead <= 0:
                days_ahead += 7
            target = now + timedelta(days=days_ahead)
            return target.replace(hour=0, minute=0, second=0, microsecond=0)
        elif "sunday" in value_lower:
            days_ahead = 6 - now.weekday()  # Sunday is 6
            if days_ahead <= 0:
                days_ahead += 7
            target = now + timedelta(days=days_ahead)
            return target.replace(hour=0, minute=0, second=0, microsecond=0)

        return None
