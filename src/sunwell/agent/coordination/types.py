"""Shared types for coordination modules — breaks circular imports."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class TaskResult:
    """Result of executing a task."""

    task_id: str
    """ID of the task."""

    success: bool
    """Whether the task completed successfully."""

    output: str | None = None
    """Output or result description."""

    error: str | None = None
    """Error message if failed."""

    artifacts: list[str] = field(default_factory=list)
    """Paths of artifacts created."""

    duration_ms: int = 0
    """Execution time in milliseconds."""
