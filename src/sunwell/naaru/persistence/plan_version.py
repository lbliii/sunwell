"""Plan versioning support (RFC-120)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class PlanVersion:
    """A single version of a plan.

    Attributes:
        version: Version number (1, 2, 3, ...)
        plan_id: Hash of goal (same as goal_hash)
        goal: The goal text
        artifacts: List of artifact IDs in this version
        tasks: List of task descriptions
        score: Harmonic score if available
        created_at: When this version was created
        reason: Why this version exists (e.g., "Initial plan", "Resonance round 2")
        added_artifacts: Artifacts added since previous version
        removed_artifacts: Artifacts removed since previous version
        modified_artifacts: Artifacts modified since previous version
    """

    version: int
    plan_id: str
    goal: str
    artifacts: tuple[str, ...]
    tasks: tuple[str, ...]
    created_at: datetime
    reason: str
    score: float | None = None
    added_artifacts: tuple[str, ...] = ()
    removed_artifacts: tuple[str, ...] = ()
    modified_artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "plan_id": self.plan_id,
            "goal": self.goal,
            "artifacts": list(self.artifacts),
            "tasks": list(self.tasks),
            "score": self.score,
            "created_at": self.created_at.isoformat(),
            "reason": self.reason,
            "added_artifacts": list(self.added_artifacts),
            "removed_artifacts": list(self.removed_artifacts),
            "modified_artifacts": list(self.modified_artifacts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanVersion:
        """Create from dict."""
        return cls(
            version=data["version"],
            plan_id=data["plan_id"],
            goal=data["goal"],
            artifacts=tuple(data.get("artifacts", [])),
            tasks=tuple(data.get("tasks", [])),
            score=data.get("score"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            reason=data.get("reason", "Unknown"),
            added_artifacts=tuple(data.get("added_artifacts", [])),
            removed_artifacts=tuple(data.get("removed_artifacts", [])),
            modified_artifacts=tuple(data.get("modified_artifacts", [])),
        )


@dataclass(frozen=True, slots=True)
class PlanDiff:
    """Diff between two plan versions.

    Attributes:
        plan_id: The plan ID
        v1: First version number
        v2: Second version number
        added: Artifacts added in v2
        removed: Artifacts removed in v2
        modified: Artifacts present in both but changed
    """

    plan_id: str
    v1: int
    v2: int
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "plan_id": self.plan_id,
            "v1": self.v1,
            "v2": self.v2,
            "added": list(self.added),
            "removed": list(self.removed),
            "modified": list(self.modified),
        }
