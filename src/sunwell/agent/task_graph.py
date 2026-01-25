"""Task graph for tracking execution state.

The TaskGraph manages task dependencies, completion status, and artifact tracking
for the Agent's execution pipeline.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.naaru.types import Task

from sunwell.agent.gates import ValidationGate


def sanitize_code_content(content: str) -> str:
    """Strip markdown fences from generated code content.

    Defense-in-depth: Called before direct file writes to ensure
    markdown fences are removed even if other sanitization missed them.

    Args:
        content: Raw content that may contain markdown fences

    Returns:
        Content with markdown fences stripped
    """
    if not content or not content.startswith("```"):
        return content

    lines = content.split("\n")

    # Remove opening fence (```python, ```rust, etc.)
    if lines[0].startswith("```"):
        lines = lines[1:]

    # Remove closing fence
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)


# Backward compatibility alias
_sanitize_code_content = sanitize_code_content


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

    tasks: list["Task"] = field(default_factory=list)
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

    def get_ready_tasks(self) -> list["Task"]:
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

    def mark_complete(self, task: "Task") -> None:
        """Mark a task as complete.

        Args:
            task: The completed task
        """
        self.completed_ids.add(task.id)
        self.completed_artifacts.update(task.produces)

    @property
    def completed_summary(self) -> str:
        """Summary of completed work."""
        return f"{len(self.completed_ids)}/{len(self.tasks)} tasks"
