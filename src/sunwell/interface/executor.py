"""Action Executor (RFC-075).

Executes actions against data providers.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sunwell.interface.types import ActionSpec
from sunwell.providers.base import CalendarEvent, CalendarProvider, ListProvider


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Result of an executed action."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


@dataclass
class ActionExecutor:
    """Executes actions against data providers."""

    calendar: CalendarProvider | None = None
    lists: ListProvider | None = None

    async def execute(self, action: ActionSpec) -> ActionResult:
        """Execute an action and return result."""
        match action.type:
            case "add_to_list":
                return await self._add_to_list(action.params)
            case "complete_item":
                return await self._complete_item(action.params)
            case "create_event":
                return await self._create_event(action.params)
            case "create_reminder":
                return await self._create_reminder(action.params)
            case _:
                return ActionResult(
                    success=False,
                    message=f"Unknown action type: {action.type}",
                )

    async def _add_to_list(self, params: dict[str, Any]) -> ActionResult:
        """Add an item to a list."""
        if not self.lists:
            return ActionResult(
                success=False,
                message="Lists provider not configured.",
            )

        list_name = params.get("list", "default")
        item_text = params.get("item")

        if not item_text:
            return ActionResult(
                success=False,
                message="No item specified to add.",
            )

        try:
            item = await self.lists.add_item(list_name, item_text)
            return ActionResult(
                success=True,
                message=f"Added '{item_text}' to {list_name} list.",
                data={"item_id": item.id, "list": list_name},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to add item: {e}",
            )

    async def _complete_item(self, params: dict[str, Any]) -> ActionResult:
        """Mark a list item as complete."""
        if not self.lists:
            return ActionResult(
                success=False,
                message="Lists provider not configured.",
            )

        item_id = params.get("item_id")

        if not item_id:
            return ActionResult(
                success=False,
                message="No item specified to complete.",
            )

        try:
            item = await self.lists.complete_item(item_id)
            return ActionResult(
                success=True,
                message=f"Completed '{item.text}'.",
                data={"item_id": item.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to complete item: {e}",
            )

    async def _create_event(self, params: dict[str, Any]) -> ActionResult:
        """Create a calendar event."""
        if not self.calendar:
            return ActionResult(
                success=False,
                message="Calendar provider not configured.",
            )

        title = params.get("title")
        start = params.get("start")  # ISO string or relative
        duration = params.get("duration_minutes", 60)

        if not title or not start:
            return ActionResult(
                success=False,
                message="Event needs a title and start time.",
            )

        try:
            # Parse start time
            start_dt = self._parse_datetime(start)
            end_dt = start_dt + timedelta(minutes=duration)

            event = CalendarEvent(
                id="",  # Provider will assign
                title=title,
                start=start_dt,
                end=end_dt,
                location=params.get("location"),
                notes=params.get("notes"),
            )

            created = await self.calendar.create_event(event)
            return ActionResult(
                success=True,
                message=f"Created event '{title}' for {start_dt.strftime('%A %B %d at %I:%M %p')}.",
                data={"event_id": created.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to create event: {e}",
            )

    async def _create_reminder(self, params: dict[str, Any]) -> ActionResult:
        """Create a reminder (implemented as a calendar event with reminder flag)."""
        if not self.calendar:
            return ActionResult(
                success=False,
                message="Calendar provider not configured.",
            )

        text = params.get("text")
        when = params.get("when")  # "tomorrow", "in 2 hours", ISO string

        if not text:
            return ActionResult(
                success=False,
                message="Reminder needs text.",
            )

        try:
            remind_at = self._parse_datetime(when or "tomorrow 9am")

            event = CalendarEvent(
                id="",
                title=f"🔔 {text}",
                start=remind_at,
                end=remind_at + timedelta(minutes=15),
                notes="Reminder created via Sunwell",
            )

            created = await self.calendar.create_event(event)
            return ActionResult(
                success=True,
                message=f"Reminder set: '{text}' for {remind_at.strftime('%A %B %d at %I:%M %p')}.",
                data={"event_id": created.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to create reminder: {e}",
            )

    def _parse_datetime(self, value: str) -> datetime:
        """Parse datetime from various formats."""
        now = datetime.now()
        value_lower = value.lower()

        # Relative times
        if value_lower == "tomorrow":
            return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if value_lower == "next week":
            return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(weeks=1)
        if "tomorrow" in value_lower:
            # "tomorrow at 3pm", "tomorrow 3pm"
            base = now + timedelta(days=1)
            return self._parse_time_on_date(base, value_lower)
        if value_lower.startswith("in "):
            # "in 2 hours", "in 30 minutes"
            return self._parse_relative(value_lower[3:], now)

        # Day of week
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in value_lower:
                days_ahead = i - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                base = now + timedelta(days=days_ahead)
                return self._parse_time_on_date(base, value_lower)

        # Try ISO format
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass

        # Default to tomorrow 9am
        return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)

    def _parse_time_on_date(self, date: datetime, value: str) -> datetime:
        """Parse time component and apply to date."""
        import re

        # Look for hour patterns
        time_patterns = [
            (r"(\d{1,2})\s*am", lambda h: h if h < 12 else 0),
            (r"(\d{1,2})\s*pm", lambda h: h + 12 if h < 12 else h),
            (r"(\d{1,2}):(\d{2})", lambda h, m=0: h),  # 24-hour format
        ]

        for pattern, converter in time_patterns:
            match = re.search(pattern, value.lower())
            if match:
                hour = int(match.group(1))
                hour = converter(hour)
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                return date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Default to 9am
        return date.replace(hour=9, minute=0, second=0, microsecond=0)

    def _parse_relative(self, value: str, now: datetime) -> datetime:
        """Parse relative time like '2 hours', '30 minutes'."""
        parts = value.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1].lower()
                if unit.startswith("hour"):
                    return now + timedelta(hours=amount)
                if unit.startswith("minute"):
                    return now + timedelta(minutes=amount)
                if unit.startswith("day"):
                    return now + timedelta(days=amount)
                if unit.startswith("week"):
                    return now + timedelta(weeks=amount)
            except ValueError:
                pass
        return now + timedelta(hours=1)
