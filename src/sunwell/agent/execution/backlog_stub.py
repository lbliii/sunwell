"""Stub backlog types for ExecutionManager (backlog feature removed).

Provides minimal Goal, GoalScope, GoalResult, and BacklogManager
so ExecutionManager can run without the full backlog implementation.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GoalScope:
    """Scope limits for a goal."""

    max_files: int = 50
    max_lines_changed: int = 5000


@dataclass(frozen=True, slots=True)
class Goal:
    """Minimal goal type (backlog feature removed)."""

    id: str
    title: str
    description: str
    source_signals: tuple[str, ...] = ()
    priority: float = 1.0
    estimated_complexity: str = "moderate"
    requires: frozenset[str] = frozenset()
    category: str = "user"
    auto_approvable: bool = True
    scope: GoalScope = field(default_factory=GoalScope)
    goal_type: str = "task"
    parent_goal_id: str | None = None


@dataclass(frozen=True, slots=True)
class GoalResult:
    """Result of goal execution."""

    success: bool
    artifacts: tuple[str, ...] = ()
    error: str | None = None


class _BacklogState:
    """Internal state for stub BacklogManager."""

    def __init__(self) -> None:
        self.goals: dict[str, Goal] = {}
        self.in_progress: str | None = None
        self.active_epic: str | None = None
        self.active_milestone: str | None = None
        self.completed: set[str] = set()

    def get_epic(self, epic_id: str) -> Goal | None:
        """Return epic goal or None."""
        return self.goals.get(epic_id)

    def get_current_milestone(self) -> Goal | None:
        """Return current milestone or None."""
        if self.active_milestone:
            return self.goals.get(self.active_milestone)
        return None


class BacklogManager:
    """Stub BacklogManager - backlog feature removed.

    All methods are no-ops. ExecutionManager can run but goals
    are not persisted.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.backlog = _BacklogState()

    async def claim_goal(self, goal_id: str, worker_id: str | None = None) -> bool:
        """Stub - always returns True."""
        self.backlog.in_progress = goal_id
        return True

    async def unclaim_goal(self, goal_id: str) -> None:
        """Stub - no-op."""
        if self.backlog.in_progress == goal_id:
            self.backlog.in_progress = None

    async def get_pending_goals(self) -> list[Goal]:
        """Stub - returns empty list."""
        return []

    async def get_completed_artifacts(self) -> list[str]:
        """Stub - returns empty list."""
        return []

    async def complete_goal(
        self,
        goal_id: str,
        artifacts: tuple[str, ...] = (),
        learnings: tuple[str, ...] = (),
    ) -> None:
        """Stub - no-op."""
        if goal_id in self.backlog.goals:
            del self.backlog.goals[goal_id]
        if self.backlog.in_progress == goal_id:
            self.backlog.in_progress = None

    async def mark_failed(self, goal_id: str, error: str) -> None:
        """Stub - no-op."""
        if self.backlog.in_progress == goal_id:
            self.backlog.in_progress = None

    async def add_external_goal(self, goal: Goal) -> None:
        """Stub - stores in memory only."""
        self.backlog.goals[goal.id] = goal
