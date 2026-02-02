"""Activity-based decay tracking (inspired by MIRA).

Tracks "activity days" - calendar days with user engagement - rather than
wall-clock time. This prevents memory decay during vacations or periods
of inactivity when the codebase hasn't actually changed.

See: MIRA's lt_memory/scoring_formula.sql for the original concept.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProjectActivity:
    """Activity state for a project.

    Attributes:
        cumulative_activity_days: Total count of days with user activity
        last_activity_date: ISO date (YYYY-MM-DD) of last activity
    """

    cumulative_activity_days: int = 0
    last_activity_date: str | None = None


class ActivityTracker:
    """Tracks cumulative activity days per project.

    An "activity day" is a calendar day where the user interacted
    with sunwell. This decouples memory decay from wall-clock time,
    preventing vacation-induced degradation of memory relevance.

    Storage: base_path/projects/{project}/activity.json
    (Follows existing SessionManager storage pattern)

    Thread-safe (3.14t compatible) via lock on write operations.

    Example:
        >>> tracker = ActivityTracker(Path(".sunwell/memory"))
        >>> days = tracker.record_activity("my-project")
        >>> print(f"Activity days: {days}")
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize activity tracker.

        Args:
            base_path: Base directory for storage (e.g., .sunwell/memory)
        """
        self._base_path = Path(base_path)
        self._cache: dict[str, ProjectActivity] = {}
        self._lock = threading.Lock()

    def _activity_path(self, project: str) -> Path:
        """Get path to activity file for a project."""
        return self._base_path / "projects" / project / "activity.json"

    def _load(self, project: str) -> ProjectActivity:
        """Load activity state for a project (uses cache)."""
        if project in self._cache:
            return self._cache[project]

        path = self._activity_path(project)
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                activity = ProjectActivity(
                    cumulative_activity_days=data.get("cumulative_activity_days", 0),
                    last_activity_date=data.get("last_activity_date"),
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load activity for %s: %s", project, e)
                activity = ProjectActivity()
        else:
            activity = ProjectActivity()

        self._cache[project] = activity
        return activity

    def _save(self, project: str, activity: ProjectActivity) -> None:
        """Save activity state for a project."""
        path = self._activity_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cumulative_activity_days": activity.cumulative_activity_days,
                        "last_activity_date": activity.last_activity_date,
                    },
                    f,
                    indent=2,
                )
        except OSError as e:
            logger.error("Failed to save activity for %s: %s", project, e)
            raise

    def record_activity(self, project: str) -> int:
        """Record activity for today, return current cumulative days.

        Call this at session start. If this is a new calendar day,
        increments the cumulative count. Idempotent within the same day.

        Args:
            project: Project identifier/slug

        Returns:
            Current cumulative activity days count
        """
        with self._lock:
            activity = self._load(project)
            today = date.today().isoformat()

            if activity.last_activity_date != today:
                activity.cumulative_activity_days += 1
                activity.last_activity_date = today
                self._save(project, activity)
                logger.debug(
                    "Recorded activity for %s: day %d",
                    project,
                    activity.cumulative_activity_days,
                )

            return activity.cumulative_activity_days

    def get_activity_days(self, project: str) -> int:
        """Get current cumulative activity days for project.

        Args:
            project: Project identifier/slug

        Returns:
            Cumulative activity days count (0 if no activity recorded)
        """
        return self._load(project).cumulative_activity_days

    def clear_cache(self, project: str | None = None) -> None:
        """Clear cached activity state.

        Args:
            project: Project to clear, or None to clear all
        """
        with self._lock:
            if project:
                self._cache.pop(project, None)
            else:
                self._cache.clear()
