"""Goal dependency tracking for multi-instance coordination (RFC-051).

Tracks dependencies between goals for parallel scheduling:
1. Explicit dependencies (goal.requires)
2. Implicit dependencies from file overlap
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.backlog.goals import Goal
    from sunwell.backlog.manager import Backlog


@dataclass
class GoalDependencyGraph:
    """Tracks dependencies between goals for parallel scheduling.

    Two types of dependencies:
    1. Explicit: Goal A requires Goal B (from goal.requires)
    2. Implicit: Goal A and B touch same files (detected at planning time)

    Example:
        graph = GoalDependencyGraph.from_backlog(backlog)

        # Get goals ready to execute
        ready = graph.get_ready_goals(completed={"goal-1", "goal-2"})

        # Check if two goals can run in parallel
        if graph.can_run_parallel("goal-3", "goal-4"):
            # Safe to run concurrently
            pass
    """

    dependencies: dict[str, set[str]] = field(default_factory=dict)
    """goal_id → set of goal_ids it depends on."""

    dependents: dict[str, set[str]] = field(default_factory=dict)
    """goal_id → set of goal_ids that depend on it."""

    file_mapping: dict[str, set[Path]] = field(default_factory=dict)
    """goal_id → estimated file paths."""

    _conflicts: dict[str, set[str]] = field(default_factory=dict)
    """goal_id → set of conflicting goal_ids (can't run simultaneously)."""

    @classmethod
    def from_backlog(cls, backlog: Backlog) -> GoalDependencyGraph:
        """Build dependency graph from backlog.

        Analyzes:
        1. Explicit dependencies (goal.requires)
        2. File overlap (goals touching same files)

        Args:
            backlog: The backlog to analyze

        Returns:
            GoalDependencyGraph with all dependencies mapped
        """
        graph = cls()

        # Add explicit dependencies
        for goal in backlog.goals.values():
            graph.dependencies[goal.id] = set(goal.requires)
            for dep_id in goal.requires:
                graph.dependents.setdefault(dep_id, set()).add(goal.id)

        # Estimate files per goal
        for goal in backlog.goals.values():
            graph.file_mapping[goal.id] = graph._estimate_affected_files(goal)

        # Add implicit dependencies from file overlap
        goal_ids = list(backlog.goals.keys())
        for i, goal_a_id in enumerate(goal_ids):
            for goal_b_id in goal_ids[i + 1 :]:
                files_a = graph.file_mapping.get(goal_a_id, set())
                files_b = graph.file_mapping.get(goal_b_id, set())

                if files_a & files_b:  # Overlap
                    # Add bidirectional conflict marker
                    # (not hard dep, just scheduling hint)
                    graph.mark_conflict(goal_a_id, goal_b_id)

        return graph

    def get_ready_goals(self, completed: set[str]) -> list[str]:
        """Get goals that are ready to execute.

        A goal is ready if all its dependencies are in `completed`.

        Args:
            completed: Set of completed goal IDs

        Returns:
            List of goal IDs ready to execute
        """
        ready = []
        for goal_id, deps in self.dependencies.items():
            if goal_id not in completed and deps <= completed:
                ready.append(goal_id)
        return ready

    def mark_conflict(self, goal_a: str, goal_b: str) -> None:
        """Mark two goals as conflicting (can't run simultaneously).

        Args:
            goal_a: First goal ID
            goal_b: Second goal ID
        """
        self._conflicts.setdefault(goal_a, set()).add(goal_b)
        self._conflicts.setdefault(goal_b, set()).add(goal_a)

    def can_run_parallel(self, goal_a: str, goal_b: str) -> bool:
        """Check if two goals can run in parallel.

        Two goals can run in parallel if:
        1. Neither depends on the other
        2. They don't have a file conflict

        Args:
            goal_a: First goal ID
            goal_b: Second goal ID

        Returns:
            True if goals can run in parallel
        """
        # Check explicit dependency
        if goal_a in self.dependencies.get(goal_b, set()):
            return False
        if goal_b in self.dependencies.get(goal_a, set()):
            return False

        # Check file conflict
        return goal_b not in self._conflicts.get(goal_a, set())

    def get_parallelizable_groups(
        self, pending: list[str], completed: set[str]
    ) -> list[list[str]]:
        """Get groups of goals that can run in parallel.

        Returns goals grouped such that within each group,
        all goals can run concurrently.

        Args:
            pending: List of pending goal IDs
            completed: Set of completed goal IDs

        Returns:
            List of parallel-safe goal groups
        """
        ready = [g for g in pending if self.dependencies.get(g, set()) <= completed]

        # Group into parallel-safe batches
        groups: list[list[str]] = []
        remaining = set(ready)

        while remaining:
            # Start a new group with the first remaining goal
            current_group = [remaining.pop()]

            # Add compatible goals
            for goal in list(remaining):
                if all(self.can_run_parallel(goal, g) for g in current_group):
                    current_group.append(goal)
                    remaining.discard(goal)

            groups.append(current_group)

        return groups

    def _estimate_affected_files(self, goal: Goal) -> set[Path]:
        """Estimate which files a goal will touch.

        Uses (in priority order):
        1. goal.scope.allowed_paths if specified
        2. Pattern matching on goal description

        Args:
            goal: The goal to analyze

        Returns:
            Set of estimated file paths
        """
        files: set[Path] = set()

        # Use scope if available
        if goal.scope and goal.scope.allowed_paths:
            return set(goal.scope.allowed_paths)

        # Pattern matching heuristics
        description = goal.description.lower()

        # "test for X" → tests/test_X.py
        if "test" in description:
            for match in re.finditer(r"test(?:s)?\s+(?:for\s+)?(\w+)", description):
                module = match.group(1)
                files.add(Path(f"tests/test_{module}.py"))

        # "fix X.py" or "in X.py" → X.py
        for match in re.finditer(r"(\w+\.py)", description):
            files.add(Path(match.group(1)))

        # "add docstrings to X" → X.py
        for match in re.finditer(r"(?:to|in|for)\s+(\w+)(?:\.py)?", description):
            module = match.group(1)
            if not module.endswith(".py"):
                files.add(Path(f"{module}.py"))
                files.add(Path(f"src/{module}.py"))

        return files
