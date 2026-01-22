"""Backlog Management for Autonomous Backlog (RFC-046 Phase 3).

Maintain goal DAG and coordinate execution.

RFC-051 Extensions:
- claim_goal(goal_id, worker_id) - Claim a goal for multi-instance
- exclusive_access() - Context manager for cross-process safety
- get_pending_goals() - Get unclaimed, incomplete goals
- mark_failed(goal_id, error) - Mark a goal as failed
- get_goal(goal_id) - Get a goal by ID
"""


import contextlib
import fcntl
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult, GoalScope
from sunwell.backlog.signals import SignalExtractor

if TYPE_CHECKING:
    from sunwell.intelligence.context import ProjectContext


@dataclass
class Backlog:
    """The prioritized backlog as an artifact DAG."""

    goals: dict[str, Goal]
    """All known goals."""

    completed: set[str]
    """Goal IDs that are done."""

    in_progress: str | None
    """Currently executing goal, if any."""

    blocked: dict[str, str]
    """Goal ID → reason blocked."""

    def execution_order(self) -> list[Goal]:
        """Return goals in optimal execution order.

        Uses same wave algorithm as ArtifactGraph (RFC-036):
        - Leaves first (no dependencies)
        - Higher priority within each wave
        - Quick wins before complex tasks
        """
        completed_set = self.completed | set(self.blocked.keys())

        # Topological sort with priority ordering
        waves: list[list[Goal]] = []
        remaining = {
            g.id: g
            for g in self.goals.values()
            if g.id not in completed_set
        }

        while remaining:
            # Find leaves (no uncompleted dependencies)
            ready = [
                g
                for g in remaining.values()
                if all(dep in completed_set for dep in g.requires)
            ]

            if not ready:
                # Cycle or missing dependency - add remaining in priority order
                ready = sorted(
                    remaining.values(),
                    key=lambda g: g.priority,
                    reverse=True,
                )[:1]

            # Sort by priority within wave
            ready_sorted = sorted(ready, key=lambda g: g.priority, reverse=True)
            waves.append(ready_sorted)

            # Mark as completed for next wave
            for g in ready_sorted:
                completed_set.add(g.id)
                remaining.pop(g.id, None)

        # Flatten waves
        return [g for wave in waves for g in wave]

    def next_goal(self) -> Goal | None:
        """Get the next goal to work on."""
        for goal in self.execution_order():
            if goal.id not in self.completed:
                if goal.id not in self.blocked:
                    if all(dep in self.completed for dep in goal.requires):
                        return goal
        return None

    def to_mermaid(self) -> str:
        """Export backlog as Mermaid diagram."""
        lines = ["graph TD"]
        goal_map = {g.id: g for g in self.goals.values()}

        for goal in self.goals.values():
            status = "✓" if goal.id in self.completed else "⏳" if goal.id == self.in_progress else "□"
            lines.append(f'  {goal.id}["{status} {goal.title[:30]}"]')

        for goal in self.goals.values():
            for dep_id in goal.requires:
                if dep_id in goal_map:
                    lines.append(f"  {dep_id} --> {goal.id}")

        return "\n".join(lines)


class BacklogManager:
    """Manages the autonomous backlog lifecycle."""

    def __init__(
        self,
        root: Path,
        context: ProjectContext | None = None,
        signal_extractor: SignalExtractor | None = None,
        goal_generator: GoalGenerator | None = None,
        policy: GoalPolicy | None = None,
    ):
        """Initialize backlog manager.

        Args:
            root: Project root directory
            context: Optional project context (for intelligence)
            signal_extractor: Signal extractor (creates if None)
            goal_generator: Goal generator (creates if None)
            policy: Goal policy
        """
        self.root = Path(root)
        self.context = context
        self.policy = policy or GoalPolicy()

        self.signal_extractor = signal_extractor or SignalExtractor(self.root)
        self.goal_generator = goal_generator or GoalGenerator(
            context=context,
            policy=self.policy,
        )

        self.backlog_path = self.root / ".sunwell" / "backlog"
        self.backlog_path.mkdir(parents=True, exist_ok=True)

        self.backlog = Backlog(
            goals={},
            completed=set(),
            in_progress=None,
            blocked={},
        )

        # External ref index for deduplication (RFC-049)
        self._external_refs: dict[str, str] = {}  # external_ref → goal_id

        # Load existing backlog
        self._load()

    async def refresh(self) -> Backlog:
        """Refresh backlog from current project state.

        Called:
        - On session start
        - After completing a goal
        - After external changes (git pull, etc.)
        """
        # 1. Extract fresh signals
        observable = await self.signal_extractor.extract_all()

        # 2. Generate goals
        intelligence_signals = []
        if self.context:
            # Future: extract intelligence signals from context (RFC-045)
            pass

        goals = await self.goal_generator.generate(
            observable_signals=observable,
            intelligence_signals=intelligence_signals,
        )

        # 3. Merge with existing backlog (preserve completed, update priorities)
        self.backlog = self._merge_backlog(self.backlog, goals)

        # 4. Save
        self._save()

        return self.backlog

    def _merge_backlog(self, existing: Backlog, new_goals: list[Goal]) -> Backlog:
        """Merge new goals with existing backlog.

        Preserves completed goals, updates priorities for existing goals.
        """
        merged_goals: dict[str, Goal] = {}

        # Keep completed goals (for history)
        for goal_id, goal in existing.goals.items():
            if goal_id in existing.completed:
                merged_goals[goal_id] = goal

        # Add/update new goals
        for goal in new_goals:
            if goal.id in merged_goals:
                # Update priority if higher
                existing_goal = merged_goals[goal.id]
                if goal.priority > existing_goal.priority:
                    merged_goals[goal.id] = goal
            else:
                merged_goals[goal.id] = goal

        return Backlog(
            goals=merged_goals,
            completed=existing.completed.copy(),
            in_progress=existing.in_progress,
            blocked=existing.blocked.copy(),
        )

    async def complete_goal(self, goal_id: str, result: GoalResult) -> None:
        """Mark a goal as completed and refresh."""
        self.backlog.completed.add(goal_id)
        self.backlog.in_progress = None

        # Record in history
        await self._record_completion(goal_id, result)

        # Refresh to find newly unblocked goals
        await self.refresh()

    async def block_goal(self, goal_id: str, reason: str) -> None:
        """Mark a goal as blocked."""
        self.backlog.blocked[goal_id] = reason
        self.backlog.in_progress = None
        self._save()

    async def add_external_goal(self, goal: Goal) -> None:
        """Add a goal from an external event (RFC-049).

        External goals are:
        1. Tracked with external_ref for deduplication
        2. Prioritized alongside internal goals
        3. Logged separately for auditing

        Args:
            goal: The goal to add (must have external_ref set)
        """
        self.backlog.goals[goal.id] = goal

        # Track external reference for deduplication
        if goal.external_ref:
            self._external_refs[goal.external_ref] = goal.id

        self._save()

    async def get_goals_by_external_ref(self, ref: str) -> list[Goal]:
        """Get goals associated with an external reference (RFC-049).

        Args:
            ref: External reference ID (e.g., 'github:issue:123')

        Returns:
            List of goals with this external reference (usually 0 or 1)
        """
        goal_id = self._external_refs.get(ref)
        if goal_id and goal_id in self.backlog.goals:
            return [self.backlog.goals[goal_id]]
        return []

    # =========================================================================
    # RFC-051: Multi-Instance Coordination Methods
    # =========================================================================

    @asynccontextmanager
    async def exclusive_access(self) -> AsyncIterator[None]:
        """Acquire exclusive access to backlog.

        Uses flock for cross-process safety. Must be used when
        modifying backlog from multiple worker processes.

        Example:
            async with backlog_manager.exclusive_access():
                goal = await backlog_manager.get_pending_goals()[0]
                await backlog_manager.claim_goal(goal.id, worker_id=1)
        """
        lock_path = self.backlog_path / "backlog.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # Reload to get latest state
            self._load()
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    async def claim_goal(self, goal_id: str, worker_id: int) -> bool:
        """Claim a goal for a worker (RFC-051).

        Must be called within exclusive_access() context.

        Args:
            goal_id: ID of the goal to claim
            worker_id: ID of the claiming worker

        Returns:
            True if successfully claimed, False if already claimed
        """
        goal = self.backlog.goals.get(goal_id)
        if goal is None:
            return False

        # Check if already claimed
        if goal.claimed_by is not None:
            return False

        # Create new goal with claim info
        claimed_goal = Goal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            source_signals=goal.source_signals,
            priority=goal.priority,
            estimated_complexity=goal.estimated_complexity,
            requires=goal.requires,
            category=goal.category,
            auto_approvable=goal.auto_approvable,
            scope=goal.scope,
            external_ref=goal.external_ref,
            claimed_by=worker_id,
            claimed_at=datetime.now(),
        )

        self.backlog.goals[goal_id] = claimed_goal
        self._save()
        return True

    async def get_pending_goals(self) -> list[Goal]:
        """Get goals that are pending (not completed, not blocked).

        For multi-instance, this returns goals in execution order
        that haven't been completed or blocked.

        Returns:
            List of pending goals in priority order
        """
        pending = []
        for goal in self.backlog.execution_order():
            if goal.id not in self.backlog.completed and goal.id not in self.backlog.blocked:
                pending.append(goal)
        return pending

    async def get_goal(self, goal_id: str) -> Goal | None:
        """Get a goal by ID.

        Args:
            goal_id: ID of the goal to retrieve

        Returns:
            The goal, or None if not found
        """
        return self.backlog.goals.get(goal_id)

    async def mark_complete(self, goal_id: str) -> None:
        """Mark a goal as completed (RFC-051).

        Args:
            goal_id: ID of the goal to mark complete
        """
        self.backlog.completed.add(goal_id)
        self.backlog.in_progress = None
        self._save()

    async def mark_failed(self, goal_id: str, error: str) -> None:
        """Mark a goal as failed (RFC-051).

        Args:
            goal_id: ID of the goal that failed
            error: Error message describing the failure
        """
        self.backlog.blocked[goal_id] = f"Failed: {error}"
        self.backlog.in_progress = None
        self._save()

    async def unclaim_goal(self, goal_id: str) -> None:
        """Remove claim from a goal (RFC-051).

        Used when a worker fails or abandons a goal.

        Args:
            goal_id: ID of the goal to unclaim
        """
        goal = self.backlog.goals.get(goal_id)
        if goal is None:
            return

        # Create new goal without claim
        unclaimed_goal = Goal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            source_signals=goal.source_signals,
            priority=goal.priority,
            estimated_complexity=goal.estimated_complexity,
            requires=goal.requires,
            category=goal.category,
            auto_approvable=goal.auto_approvable,
            scope=goal.scope,
            external_ref=goal.external_ref,
            claimed_by=None,
            claimed_at=None,
        )

        self.backlog.goals[goal_id] = unclaimed_goal
        self._save()

    def get_claims(self) -> dict[str, int]:
        """Get current goal claims (RFC-051).

        Returns:
            Dictionary mapping goal_id → worker_id for claimed goals
        """
        claims = {}
        for goal in self.backlog.goals.values():
            if goal.claimed_by is not None:
                claims[goal.id] = goal.claimed_by
        return claims

    async def _record_completion(self, goal_id: str, result: GoalResult) -> None:
        """Record goal completion in history."""
        history_path = self.backlog_path / "completed.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "goal_id": goal_id,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "files_changed": result.files_changed,
            "failure_reason": result.failure_reason,
        }

        with history_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def _load(self) -> None:
        """Load backlog from disk."""
        current_path = self.backlog_path / "current.json"
        if not current_path.exists():
            return

        try:
            data = json.loads(current_path.read_text())
            goals: dict[str, Goal] = {}

            for gid, goal_data in data.get("goals", {}).items():
                # Reconstruct Goal with proper types
                scope_data = goal_data.get("scope", {})
                scope = GoalScope(
                    max_files=scope_data.get("max_files", 5),
                    max_lines_changed=scope_data.get("max_lines_changed", 500),
                )

                # RFC-051: Parse claimed_at timestamp
                claimed_at = None
                if goal_data.get("claimed_at"):
                    with contextlib.suppress(ValueError, TypeError):
                        claimed_at = datetime.fromisoformat(goal_data["claimed_at"])

                goals[gid] = Goal(
                    id=goal_data["id"],
                    title=goal_data["title"],
                    description=goal_data["description"],
                    source_signals=tuple(goal_data.get("source_signals", [])),
                    priority=goal_data["priority"],
                    estimated_complexity=goal_data["estimated_complexity"],
                    requires=frozenset(goal_data.get("requires", [])),
                    category=goal_data["category"],
                    auto_approvable=goal_data.get("auto_approvable", False),
                    scope=scope,
                    external_ref=goal_data.get("external_ref"),  # RFC-049
                    claimed_by=goal_data.get("claimed_by"),  # RFC-051
                    claimed_at=claimed_at,  # RFC-051
                )

            self.backlog = Backlog(
                goals=goals,
                completed=set(data.get("completed", [])),
                in_progress=data.get("in_progress"),
                blocked=data.get("blocked", {}),
            )

            # Load or rebuild external refs index (RFC-049)
            self._external_refs = data.get("external_refs", {})
            if not self._external_refs:
                # Rebuild index from goals if migrating from old schema
                for goal in self.backlog.goals.values():
                    if goal.external_ref:
                        self._external_refs[goal.external_ref] = goal.id

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Invalid data - start fresh
            pass

    def _save(self) -> None:
        """Save backlog to disk."""
        current_path = self.backlog_path / "current.json"
        current_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "schema_version": 3,  # RFC-051: Added claimed_by/claimed_at
            "goals": {
                gid: {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "source_signals": list(goal.source_signals),
                    "priority": goal.priority,
                    "estimated_complexity": goal.estimated_complexity,
                    "requires": list(goal.requires),
                    "category": goal.category,
                    "auto_approvable": goal.auto_approvable,
                    "scope": {
                        "max_files": goal.scope.max_files,
                        "max_lines_changed": goal.scope.max_lines_changed,
                    },
                    "external_ref": goal.external_ref,  # RFC-049
                    "claimed_by": goal.claimed_by,  # RFC-051
                    "claimed_at": (
                        goal.claimed_at.isoformat() if goal.claimed_at else None
                    ),  # RFC-051
                }
                for gid, goal in self.backlog.goals.items()
            },
            "completed": list(self.backlog.completed),
            "in_progress": self.backlog.in_progress,
            "blocked": self.backlog.blocked,
            "external_refs": self._external_refs,  # RFC-049
        }

        # Use file locking for process safety (RFC-049/051)
        with open(current_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
