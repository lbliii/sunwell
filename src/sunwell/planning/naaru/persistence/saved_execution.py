"""SavedExecution - Complete state for a goal's execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sunwell.planning.naaru.artifacts import ArtifactGraph
from sunwell.planning.naaru.executor import ArtifactResult, ExecutionResult
from sunwell.planning.naaru.persistence.hashing import hash_goal
from sunwell.planning.naaru.persistence.types import ArtifactCompletion, ExecutionStatus


PERSISTENCE_VERSION = "1.0"


@dataclass(slots=True)
class SavedExecution:
    """Complete state for a goal's execution.

    Combines plan (ArtifactGraph), checkpoint (progress), and trace (events).

    Attributes:
        goal: Original goal text
        goal_hash: Deterministic hash for lookup
        graph: The artifact graph (plan)
        status: Current execution status
        completed: Completed artifacts with metadata
        failed: Failed artifacts with error messages
        content_hashes: Content hashes for incremental rebuild
        current_wave: Wave currently being executed (for resume)
        created_at: When the plan was created
        updated_at: When the execution was last updated
        model_distribution: Count of each model tier used
    """

    goal: str
    graph: ArtifactGraph
    goal_hash: str = ""
    status: ExecutionStatus = ExecutionStatus.PLANNED
    completed: dict[str, ArtifactCompletion] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    content_hashes: dict[str, str] = field(default_factory=dict)
    current_wave: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    model_distribution: dict[str, int] = field(
        default_factory=lambda: {"small": 0, "medium": 0, "large": 0}
    )

    def __post_init__(self) -> None:
        """Initialize goal_hash if not provided."""
        if not self.goal_hash:
            self.goal_hash = hash_goal(self.goal)

    @property
    def completed_ids(self) -> set[str]:
        """Get set of completed artifact IDs.

        Note: Returns a new set each call. For internal use,
        prefer using self.completed.keys() directly when possible.
        """
        return set(self.completed.keys())

    @property
    def failed_ids(self) -> set[str]:
        """Get set of failed artifact IDs.

        Note: Returns a new set each call. For internal use,
        prefer using self.failed.keys() directly when possible.
        """
        return set(self.failed.keys())

    @property
    def pending_ids(self) -> set[str]:
        """Get set of pending artifact IDs.

        Optimized: Uses dict.keys() views directly to avoid
        intermediate set allocations.
        """
        # Use dict.keys() views directly - set subtraction works with them
        all_ids = set(self.graph)
        return all_ids - self.completed.keys() - self.failed.keys()

    @property
    def is_complete(self) -> bool:
        """Check if all artifacts are completed or failed."""
        return len(self.pending_ids) == 0

    @property
    def progress_percent(self) -> float:
        """Get completion percentage."""
        total = len(self.graph)
        if total == 0:
            return 100.0
        return (len(self.completed) / total) * 100

    def get_remaining_artifacts(self) -> list[str]:
        """Get artifact IDs that haven't been completed or failed."""
        return list(self.pending_ids)

    def get_resume_wave(self) -> int:
        """Find which wave to resume from.

        Returns:
            Index of first incomplete wave
        """
        waves = self.graph.execution_waves()
        for i, wave in enumerate(waves):
            if not all(aid in self.completed for aid in wave):
                return i
        return len(waves)  # All complete

    def mark_completed(self, result: ArtifactResult) -> None:
        """Mark an artifact as completed.

        Args:
            result: The artifact result
        """
        completion = ArtifactCompletion.from_result(result)
        self.completed[result.artifact_id] = completion
        if result.content:
            self.content_hashes[result.artifact_id] = completion.content_hash
        self.model_distribution[result.model_tier] += 1
        self.updated_at = datetime.now()

    def mark_failed(self, artifact_id: str, error: str) -> None:
        """Mark an artifact as failed.

        Args:
            artifact_id: The artifact that failed
            error: Error message
        """
        self.failed[artifact_id] = error
        self.updated_at = datetime.now()

    def update_from_result(self, result: ExecutionResult) -> None:
        """Update from an ExecutionResult.

        Args:
            result: The execution result to merge
        """
        for artifact_id, artifact_result in result.completed.items():
            self.mark_completed(artifact_result)
        for artifact_id, error in result.failed.items():
            self.mark_failed(artifact_id, error)

        # Update status
        if self.is_complete:
            self.status = (
                ExecutionStatus.COMPLETED if not self.failed else ExecutionStatus.FAILED
            )
        else:
            self.status = ExecutionStatus.IN_PROGRESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": PERSISTENCE_VERSION,
            "goal": self.goal,
            "goal_hash": self.goal_hash,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "graph": self.graph.to_dict(),
            "execution": {
                "current_wave": self.current_wave,
                "completed": {
                    aid: comp.to_dict() for aid, comp in self.completed.items()
                },
                "failed": self.failed,
            },
            "content_hashes": self.content_hashes,
            "metrics": {
                "total_artifacts": len(self.graph),
                "completed_count": len(self.completed),
                "failed_count": len(self.failed),
                "progress_percent": self.progress_percent,
                "model_distribution": self.model_distribution,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedExecution:
        """Create from dict."""
        from sunwell.planning.naaru.artifacts import ArtifactGraph

        graph = ArtifactGraph.from_dict(data["graph"])
        execution = data.get("execution", {})

        completed = {
            aid: ArtifactCompletion.from_dict(comp)
            for aid, comp in execution.get("completed", {}).items()
        }

        model_dist = data.get("metrics", {}).get(
            "model_distribution", {"small": 0, "medium": 0, "large": 0}
        )

        return cls(
            goal=data["goal"],
            goal_hash=data.get("goal_hash", hash_goal(data["goal"])),
            graph=graph,
            status=ExecutionStatus(data.get("status", "planned")),
            completed=completed,
            failed=execution.get("failed", {}),
            content_hashes=data.get("content_hashes", {}),
            current_wave=execution.get("current_wave", 0),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(),
            model_distribution=model_dist,
        )
