"""Backlog Management for Autonomous Backlog (RFC-046 Phase 3).

Maintain goal DAG and coordinate execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult
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
        # Build dependency graph
        goal_map = {g.id: g for g in self.goals.values()}
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
                )

            self.backlog = Backlog(
                goals=goals,
                completed=set(data.get("completed", [])),
                in_progress=data.get("in_progress"),
                blocked=data.get("blocked", {}),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Invalid data - start fresh
            pass

    def _save(self) -> None:
        """Save backlog to disk."""
        current_path = self.backlog_path / "current.json"
        current_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
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
                }
                for gid, goal in self.backlog.goals.items()
            },
            "completed": list(self.backlog.completed),
            "in_progress": self.backlog.in_progress,
            "blocked": self.backlog.blocked,
        }

        current_path.write_text(json.dumps(data, indent=2))
