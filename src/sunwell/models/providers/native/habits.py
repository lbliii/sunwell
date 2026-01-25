"""Sunwell Native Habits Provider (RFC-078 Phase 4).

Local habit tracking stored in .sunwell/habits.json.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sunwell.providers.base import Habit, HabitEntry, HabitsProvider


class SunwellHabits(HabitsProvider):
    """Sunwell-native habits tracker stored in .sunwell/habits.json."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize with data directory.

        Args:
            data_dir: The .sunwell data directory.
        """
        self.habits_path = data_dir / "habits.json"
        self.entries_path = data_dir / "habit_entries.json"
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        """Ensure the data files exist."""
        self.habits_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.habits_path.exists():
            self.habits_path.write_text("[]")
        if not self.entries_path.exists():
            self.entries_path.write_text("[]")

    def _load_habits(self) -> list[dict]:
        """Load habits from JSON file."""
        try:
            return json.loads(self.habits_path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_habits(self, habits: list[dict]) -> None:
        """Save habits to JSON file."""
        self.habits_path.write_text(json.dumps(habits, default=str, indent=2))

    def _load_entries(self) -> list[dict]:
        """Load entries from JSON file."""
        try:
            return json.loads(self.entries_path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_entries(self, entries: list[dict]) -> None:
        """Save entries to JSON file."""
        self.entries_path.write_text(json.dumps(entries, default=str, indent=2))

    def _dict_to_habit(self, data: dict) -> Habit:
        """Convert dictionary to Habit."""
        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        return Habit(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            frequency=data.get("frequency", "daily"),
            target_count=data.get("target_count", 1),
            color=data.get("color"),
            icon=data.get("icon"),
            created=created,
            archived=data.get("archived", False),
        )

    def _dict_to_entry(self, data: dict) -> HabitEntry:
        """Convert dictionary to HabitEntry."""
        date = data.get("date")
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif date is None:
            date = datetime.now()

        return HabitEntry(
            id=data["id"],
            habit_id=data["habit_id"],
            date=date,
            count=data.get("count", 1),
            notes=data.get("notes"),
        )

    async def list_habits(self, include_archived: bool = False) -> list[Habit]:
        """List all habits."""
        data = self._load_habits()
        habits = [self._dict_to_habit(h) for h in data]

        if not include_archived:
            habits = [h for h in habits if not h.archived]

        return sorted(habits, key=lambda h: h.created or datetime.min, reverse=True)

    async def get_habit(self, habit_id: str) -> Habit | None:
        """Get a specific habit by ID."""
        data = self._load_habits()
        for h in data:
            if h["id"] == habit_id:
                return self._dict_to_habit(h)
        return None

    async def create_habit(
        self,
        name: str,
        description: str | None = None,
        frequency: str = "daily",
        target_count: int = 1,
    ) -> Habit:
        """Create a new habit to track."""
        data = self._load_habits()
        now = datetime.now()

        new_habit = {
            "id": str(uuid4()),
            "name": name,
            "description": description,
            "frequency": frequency,
            "target_count": target_count,
            "color": None,
            "icon": None,
            "created": now.isoformat(),
            "archived": False,
        }

        data.append(new_habit)
        self._save_habits(data)
        return self._dict_to_habit(new_habit)

    async def archive_habit(self, habit_id: str) -> Habit | None:
        """Archive a habit (soft delete)."""
        data = self._load_habits()

        for h in data:
            if h["id"] == habit_id:
                h["archived"] = True
                self._save_habits(data)
                return self._dict_to_habit(h)

        return None

    async def log_entry(
        self,
        habit_id: str,
        date: datetime | None = None,
        count: int = 1,
        notes: str | None = None,
    ) -> HabitEntry:
        """Log a habit completion entry."""
        entries = self._load_entries()
        entry_date = date or datetime.now()

        # Check if entry exists for this habit on this date
        date_str = entry_date.strftime("%Y-%m-%d")
        for e in entries:
            e_date = datetime.fromisoformat(e["date"]).strftime("%Y-%m-%d")
            if e["habit_id"] == habit_id and e_date == date_str:
                # Update existing entry
                e["count"] = e.get("count", 0) + count
                if notes:
                    e["notes"] = notes
                self._save_entries(entries)
                return self._dict_to_entry(e)

        # Create new entry
        new_entry = {
            "id": str(uuid4()),
            "habit_id": habit_id,
            "date": entry_date.isoformat(),
            "count": count,
            "notes": notes,
        }

        entries.append(new_entry)
        self._save_entries(entries)
        return self._dict_to_entry(new_entry)

    async def get_entries(
        self,
        habit_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[HabitEntry]:
        """Get entries for a habit in a date range."""
        entries = self._load_entries()
        result: list[HabitEntry] = []

        for e in entries:
            if e["habit_id"] != habit_id:
                continue

            entry_date = datetime.fromisoformat(e["date"])

            if start and entry_date < start:
                continue
            if end and entry_date > end:
                continue

            result.append(self._dict_to_entry(e))

        return sorted(result, key=lambda e: e.date, reverse=True)

    async def get_streak(self, habit_id: str) -> int:
        """Get the current streak for a habit (consecutive days completed)."""
        # Get habit to check frequency
        habit = await self.get_habit(habit_id)
        if not habit:
            return 0

        entries = self._load_entries()

        # Get all dates with entries for this habit
        entry_dates: set[str] = set()
        for e in entries:
            if e["habit_id"] == habit_id:
                entry_date = datetime.fromisoformat(e["date"])
                entry_dates.add(entry_date.strftime("%Y-%m-%d"))

        if not entry_dates:
            return 0

        # Count consecutive days backward from today
        streak = 0
        current = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Check if today is completed, if not start from yesterday
        if current.strftime("%Y-%m-%d") not in entry_dates:
            current -= timedelta(days=1)

        while True:
            date_str = current.strftime("%Y-%m-%d")
            if date_str in entry_dates:
                streak += 1
                current -= timedelta(days=1)
            else:
                break

        return streak

    async def get_completion_rate(
        self,
        habit_id: str,
        days: int = 30,
    ) -> float:
        """Get completion rate for a habit over the last N days."""
        end = datetime.now()
        start = end - timedelta(days=days)

        entries = await self.get_entries(habit_id, start=start, end=end)

        if days == 0:
            return 0.0

        # Count unique days with entries
        unique_days = len({e.date.strftime("%Y-%m-%d") for e in entries})
        return unique_days / days

    async def get_today_status(self) -> list[dict]:
        """Get completion status for all active habits today."""
        habits = await self.list_habits(include_archived=False)
        entries = self._load_entries()

        today = datetime.now().strftime("%Y-%m-%d")
        today_entries: dict[str, int] = {}

        for e in entries:
            entry_date = datetime.fromisoformat(e["date"]).strftime("%Y-%m-%d")
            if entry_date == today:
                habit_id = e["habit_id"]
                today_entries[habit_id] = today_entries.get(habit_id, 0) + e.get("count", 1)

        result: list[dict] = []
        for habit in habits:
            completed = today_entries.get(habit.id, 0)
            result.append({
                "habit": habit.to_dict(),
                "completed_today": completed,
                "target": habit.target_count,
                "is_complete": completed >= habit.target_count,
            })

        return result
