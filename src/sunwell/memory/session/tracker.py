"""Session tracking for observability (RFC-120).

Tracks activity within a session and generates summaries.
Integrates with ScopeTracker for file/line metrics.
"""

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sunwell.memory.session.summary import GoalSummary, SessionSummary

# Default session storage location
DEFAULT_SESSIONS_DIR = Path(".sunwell/sessions")


class SessionTracker:
    """Tracks activity within a session.

    Provides session-level aggregation of goals, files, and metrics.
    Integrates with ScopeTracker for detailed file tracking.

    Thread-safe for concurrent goal completions.

    Example:
        >>> tracker = SessionTracker()
        >>> tracker.record_goal_complete(
        ...     goal_id="g1",
        ...     goal="Add OAuth",
        ...     status="completed",
        ...     source="cli",
        ...     duration_seconds=120.0,
        ...     tasks_completed=3,
        ...     tasks_failed=0,
        ...     files=["oauth.py", "tests.py"],
        ... )
        >>> summary = tracker.get_summary()
        >>> print(f"Completed: {summary.goals_completed}")
    """

    def __init__(
        self,
        session_id: str | None = None,
        base_path: Path | None = None,
    ) -> None:
        """Initialize session tracker.

        Args:
            session_id: Optional session ID (generates UUID if not provided)
            base_path: Storage path for session files
        """
        self.session_id = session_id or str(uuid4())
        self.started_at = datetime.now(UTC)
        self.base_path = base_path or DEFAULT_SESSIONS_DIR

        self._goals: list[GoalSummary] = []
        self._learning_count = 0
        self._dead_end_count = 0
        self._files_created: set[str] = set()
        self._files_modified: set[str] = set()
        self._files_deleted: set[str] = set()
        self._lines_added = 0
        self._lines_removed = 0
        self._lock = threading.Lock()

    def record_goal_complete(
        self,
        goal_id: str,
        goal: str,
        status: str,
        source: str,
        duration_seconds: float,
        tasks_completed: int,
        tasks_failed: int,
        files: list[str],
    ) -> GoalSummary:
        """Record a completed goal.

        Args:
            goal_id: Unique goal identifier
            goal: Goal text
            status: Final status (completed, failed, cancelled)
            source: Origin (cli, studio, api)
            duration_seconds: Total execution time
            tasks_completed: Successful task count
            tasks_failed: Failed task count
            files: Files touched during this goal

        Returns:
            The created GoalSummary
        """
        summary = GoalSummary(
            goal_id=goal_id,
            goal=goal,
            status=status,
            source=source,
            started_at=datetime.now(UTC) - timedelta(seconds=duration_seconds),
            duration_seconds=duration_seconds,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            files_touched=tuple(files),
        )

        with self._lock:
            self._goals.append(summary)
            # Track files touched
            self._files_modified.update(files)

        return summary

    def record_file_created(self, path: str) -> None:
        """Record a file creation."""
        with self._lock:
            self._files_created.add(path)

    def record_file_deleted(self, path: str) -> None:
        """Record a file deletion."""
        with self._lock:
            self._files_deleted.add(path)

    def record_lines_changed(self, added: int, removed: int) -> None:
        """Record line changes."""
        with self._lock:
            self._lines_added += added
            self._lines_removed += removed

    def record_learning(self) -> None:
        """Record a new learning."""
        with self._lock:
            self._learning_count += 1

    def record_dead_end(self) -> None:
        """Record a dead end."""
        with self._lock:
            self._dead_end_count += 1

    def get_summary(self) -> SessionSummary:
        """Generate current session summary.

        Returns:
            SessionSummary with aggregated data
        """
        with self._lock:
            goals = list(self._goals)
            files_created = set(self._files_created)
            files_modified = set(self._files_modified)
            files_deleted = set(self._files_deleted)
            lines_added = self._lines_added
            lines_removed = self._lines_removed
            learning_count = self._learning_count
            dead_end_count = self._dead_end_count

        # Determine source based on goals
        sources = {g.source for g in goals}
        source = "mixed" if len(sources) > 1 else (sources.pop() if sources else "cli")

        # Compute duration
        total_duration = (datetime.now(UTC) - self.started_at).total_seconds()

        # Compute timing breakdown (approximate)
        total_goal_time = sum(g.duration_seconds for g in goals)
        planning_seconds = total_goal_time * 0.2  # Estimate 20% planning
        execution_seconds = total_goal_time * 0.8  # Estimate 80% execution
        waiting_seconds = total_duration - total_goal_time  # Remaining is waiting

        return SessionSummary(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=None,  # Set when session ends
            source=source,
            goals_started=len(goals),
            goals_completed=len([g for g in goals if g.status == "completed"]),
            goals_failed=len([g for g in goals if g.status == "failed"]),
            files_created=len(files_created),
            files_modified=len(files_modified - files_created),  # Exclude created
            files_deleted=len(files_deleted),
            lines_added=lines_added,
            lines_removed=lines_removed,
            learnings_added=learning_count,
            dead_ends_recorded=dead_end_count,
            total_duration_seconds=total_duration,
            planning_seconds=planning_seconds,
            execution_seconds=execution_seconds,
            waiting_seconds=max(0, waiting_seconds),  # Don't go negative
            top_files=self._compute_top_files(goals),
            goals=goals,
        )

    def _compute_top_files(self, goals: list[GoalSummary]) -> list[tuple[str, int]]:
        """Compute most frequently edited files.

        Args:
            goals: List of goal summaries

        Returns:
            List of (path, edit_count) tuples, sorted by count
        """
        file_counts: dict[str, int] = {}
        for goal in goals:
            for f in goal.files_touched:
                file_counts[f] = file_counts.get(f, 0) + 1

        return sorted(file_counts.items(), key=lambda x: -x[1])[:10]

    def save(self) -> Path:
        """Save session to disk.

        Returns:
            Path to saved session file
        """
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Use date + session ID for filename
        date_str = self.started_at.strftime("%Y-%m-%d")
        filename = f"{date_str}-{self.session_id[:8]}.json"
        path = self.base_path / filename

        summary = self.get_summary()

        with self._lock, open(path, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)

        return path

    @classmethod
    def load(cls, path: Path) -> SessionTracker:
        """Load a session from disk.

        Args:
            path: Path to session file

        Returns:
            SessionTracker with loaded state
        """
        with open(path) as f:
            data = json.load(f)

        summary = SessionSummary.from_dict(data)

        tracker = cls(
            session_id=summary.session_id,
            base_path=path.parent,
        )

        # Restore state
        tracker.started_at = summary.started_at
        tracker._goals = list(summary.goals)
        tracker._learning_count = summary.learnings_added
        tracker._dead_end_count = summary.dead_ends_recorded
        tracker._lines_added = summary.lines_added
        tracker._lines_removed = summary.lines_removed

        # Restore file sets from goals
        for goal in summary.goals:
            tracker._files_modified.update(goal.files_touched)

        return tracker

    @classmethod
    def list_recent(cls, base_path: Path | None = None, limit: int = 10) -> list[Path]:
        """List recent session files.

        Args:
            base_path: Storage path
            limit: Maximum number to return

        Returns:
            List of session file paths, most recent first
        """
        path = base_path or DEFAULT_SESSIONS_DIR
        if not path.exists():
            return []

        files = sorted(
            path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        return files[:limit]
