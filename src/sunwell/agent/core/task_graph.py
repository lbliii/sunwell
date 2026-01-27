"""Task graph for tracking execution state.

The TaskGraph manages task dependencies, completion status, and artifact tracking
for the Agent's execution pipeline.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.planning.naaru.types import Task

from sunwell.agent.validation.gates import ValidationGate


def sanitize_code_content(content: str | None) -> str:
    """Strip markdown fences from generated code content.

    Defense-in-depth: Called before direct file writes to ensure
    markdown fences are removed even if other sanitization missed them.

    Args:
        content: Raw content that may contain markdown fences

    Returns:
        Content with markdown fences stripped, or empty string if None/empty
    """
    if not content:
        return ""
    if not content.startswith("```"):
        return content

    lines = content.split("\n")

    # Remove opening fence (```python, ```rust, etc.)
    if lines[0].startswith("```"):
        lines = lines[1:]

    # Remove closing fence
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)




@dataclass(slots=True)
class TaskGraph:
    """A graph of tasks with execution state.

    Tracks which tasks are complete, which artifacts have been produced,
    and provides methods to determine which tasks are ready for execution.

    Attributes:
        tasks: All tasks in the graph
        gates: Validation gates to run at checkpoints
        completed_ids: IDs of completed tasks
        completed_artifacts: Artifacts that have been produced
    """

    tasks: list[Task] = field(default_factory=list)
    """All tasks in the graph."""

    gates: list[ValidationGate] = field(default_factory=list)
    """Validation gates."""

    completed_ids: set[str] = field(default_factory=set)
    """IDs of completed tasks."""

    completed_artifacts: set[str] = field(default_factory=set)
    """Artifacts that have been produced."""

    def has_pending_tasks(self) -> bool:
        """Check if there are pending tasks."""
        return len(self.completed_ids) < len(self.tasks)

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute.

        A task is ready when:
        - It hasn't been completed yet
        - All its dependencies are satisfied

        Returns:
            List of tasks ready for execution
        """
        return [
            t
            for t in self.tasks
            if t.id not in self.completed_ids
            and t.is_ready(self.completed_ids, self.completed_artifacts)
        ]

    def mark_complete(self, task: Task) -> None:
        """Mark a task as complete.

        Args:
            task: The completed task
        """
        self.completed_ids.add(task.id)
        if task.produces:
            self.completed_artifacts.update(task.produces)

    @property
    def completed_summary(self) -> str:
        """Summary of completed work."""
        return f"{len(self.completed_ids)}/{len(self.tasks)} tasks"

    # =========================================================================
    # Parallel Execution Support (Agentic Infrastructure Phase 2)
    # =========================================================================

    def get_parallel_groups(self) -> dict[str | None, list[Task]]:
        """Group ready tasks by parallel_group for subagent spawning.

        Returns a dict mapping parallel_group name to list of ready tasks.
        Tasks without a parallel_group are grouped under key None.

        Only returns tasks that are:
        - Not yet completed
        - Have all dependencies satisfied
        - Can potentially run in parallel

        Returns:
            Dict mapping parallel_group name (or None) to ready tasks
        """
        ready = self.get_ready_tasks()
        groups: dict[str | None, list[Task]] = {}

        for task in ready:
            group_key = task.parallel_group
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(task)

        return groups

    def can_parallelize(self, tasks: list[Task]) -> bool:
        """Check if tasks can safely execute in parallel.

        Tasks can be parallelized when they have non-overlapping `modifies` sets.
        Two tasks with overlapping modifies sets could conflict on the same file.

        Args:
            tasks: List of tasks to check

        Returns:
            True if tasks have no overlapping modifies sets
        """
        if len(tasks) <= 1:
            return True

        # Collect all modifies sets
        all_modifies: list[frozenset[str]] = []
        for task in tasks:
            if task.modifies:
                all_modifies.append(task.modifies)

        # Check for overlaps
        for i, mods_a in enumerate(all_modifies):
            for mods_b in all_modifies[i + 1:]:
                if mods_a & mods_b:  # Non-empty intersection
                    return False

        return True

    def get_parallelizable_groups(self) -> dict[str, list[Task]]:
        """Get parallel groups that are safe to execute concurrently.

        Filters get_parallel_groups() to only include groups where:
        - All tasks have non-overlapping modifies sets
        - Group has more than one task (worth parallelizing)

        Returns:
            Dict mapping group name to parallelizable tasks.
            Excludes None key and single-task groups.
        """
        groups = self.get_parallel_groups()
        result: dict[str, list[Task]] = {}

        for group_name, tasks in groups.items():
            # Skip ungrouped tasks and single-task groups
            if group_name is None or len(tasks) <= 1:
                continue

            # Check if tasks can actually be parallelized
            if self.can_parallelize(tasks):
                result[group_name] = tasks

        return result

    def get_sequential_tasks(self) -> list[Task]:
        """Get ready tasks that must execute sequentially.

        Returns tasks that are:
        - Not in a parallel group, OR
        - In a parallel group but can't be safely parallelized

        Returns:
            List of tasks to execute one at a time
        """
        groups = self.get_parallel_groups()
        parallelizable = self.get_parallelizable_groups()

        sequential: list[Task] = []

        for group_name, tasks in groups.items():
            if group_name is None:
                # Ungrouped tasks are sequential
                sequential.extend(tasks)
            elif group_name not in parallelizable:
                # Group exists but isn't parallelizable (conflicts)
                sequential.extend(tasks)

        return sequential
