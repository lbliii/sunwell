"""Session summary data models (RFC-120).

Defines the data structures for session summaries, providing
a human-readable view of what was accomplished.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class GoalSummary:
    """Summary of a single goal within a session.

    Attributes:
        goal_id: Unique identifier for the goal
        goal: The goal text
        status: Final status (completed, failed, cancelled)
        source: Origin of the goal (cli, studio, api)
        started_at: When execution started
        duration_seconds: Total execution time
        tasks_completed: Number of successful tasks
        tasks_failed: Number of failed tasks
        files_touched: Files modified during this goal
    """

    goal_id: str
    goal: str
    status: str
    source: str
    started_at: datetime
    duration_seconds: float
    tasks_completed: int
    tasks_failed: int
    files_touched: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "goal_id": self.goal_id,
            "goal": self.goal,
            "status": self.status,
            "source": self.source,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "files_touched": list(self.files_touched),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalSummary:
        """Create from dict."""
        return cls(
            goal_id=data["goal_id"],
            goal=data["goal"],
            status=data["status"],
            source=data["source"],
            started_at=datetime.fromisoformat(data["started_at"]),
            duration_seconds=data["duration_seconds"],
            tasks_completed=data["tasks_completed"],
            tasks_failed=data["tasks_failed"],
            files_touched=tuple(data.get("files_touched", [])),
        )


@dataclass(slots=True)
class SessionSummary:
    """Summary of a coding session.

    Aggregates activity across all goals in a session, providing
    a high-level view of what was accomplished.

    Attributes:
        session_id: Unique session identifier
        started_at: Session start time
        ended_at: Session end time (None if ongoing)
        source: Primary source (cli, studio, mixed)
        goals_started: Total goals attempted
        goals_completed: Successfully completed goals
        goals_failed: Failed goals
        files_created: New files created
        files_modified: Existing files modified
        files_deleted: Files deleted
        lines_added: Lines of code added
        lines_removed: Lines of code removed
        learnings_added: New patterns learned
        dead_ends_recorded: Dead ends recorded
        total_duration_seconds: Total session duration
        planning_seconds: Time spent planning
        execution_seconds: Time spent executing
        waiting_seconds: Time waiting for user input
        top_files: Most frequently edited files (path, edit_count)
        goals: Individual goal summaries
    """

    session_id: str
    started_at: datetime
    source: str
    goals_started: int = 0
    goals_completed: int = 0
    goals_failed: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    learnings_added: int = 0
    dead_ends_recorded: int = 0
    total_duration_seconds: float = 0.0
    planning_seconds: float = 0.0
    execution_seconds: float = 0.0
    waiting_seconds: float = 0.0
    ended_at: datetime | None = None
    top_files: list[tuple[str, int]] = field(default_factory=list)
    goals: list[GoalSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "source": self.source,
            "goals_started": self.goals_started,
            "goals_completed": self.goals_completed,
            "goals_failed": self.goals_failed,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "learnings_added": self.learnings_added,
            "dead_ends_recorded": self.dead_ends_recorded,
            "total_duration_seconds": self.total_duration_seconds,
            "planning_seconds": self.planning_seconds,
            "execution_seconds": self.execution_seconds,
            "waiting_seconds": self.waiting_seconds,
            "top_files": self.top_files,
            "goals": [g.to_dict() for g in self.goals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionSummary:
        """Create from dict."""
        return cls(
            session_id=data["session_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            source=data["source"],
            goals_started=data.get("goals_started", 0),
            goals_completed=data.get("goals_completed", 0),
            goals_failed=data.get("goals_failed", 0),
            files_created=data.get("files_created", 0),
            files_modified=data.get("files_modified", 0),
            files_deleted=data.get("files_deleted", 0),
            lines_added=data.get("lines_added", 0),
            lines_removed=data.get("lines_removed", 0),
            learnings_added=data.get("learnings_added", 0),
            dead_ends_recorded=data.get("dead_ends_recorded", 0),
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
            planning_seconds=data.get("planning_seconds", 0.0),
            execution_seconds=data.get("execution_seconds", 0.0),
            waiting_seconds=data.get("waiting_seconds", 0.0),
            top_files=data.get("top_files", []),
            goals=[GoalSummary.from_dict(g) for g in data.get("goals", [])],
        )
