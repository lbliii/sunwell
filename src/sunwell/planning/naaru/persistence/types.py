"""Type definitions for plan persistence."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sunwell.planning.naaru.executor import ArtifactResult


class ExecutionStatus(Enum):
    """Status of a saved execution."""

    PLANNED = "planned"  # Graph created, not started
    IN_PROGRESS = "in_progress"  # Executing waves
    PAUSED = "paused"  # Interrupted, can resume
    COMPLETED = "completed"  # All artifacts done
    FAILED = "failed"  # Execution failed


@dataclass(frozen=True, slots=True)
class ArtifactCompletion:
    """Record of a completed artifact.

    Attributes:
        artifact_id: The artifact that was created
        content_hash: SHA-256 hash of output (truncated to 16 chars)
        model_tier: Model tier used (small/medium/large)
        duration_ms: Creation time in milliseconds
        verified: Whether the artifact passed verification
        completed_at: When the artifact was completed
    """

    artifact_id: str
    content_hash: str
    model_tier: str = "medium"
    duration_ms: int = 0
    verified: bool = False
    completed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "content_hash": self.content_hash,
            "model_tier": self.model_tier,
            "duration_ms": self.duration_ms,
            "verified": self.verified,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactCompletion:
        """Create from dict."""
        return cls(
            artifact_id=data["artifact_id"],
            content_hash=data["content_hash"],
            model_tier=data.get("model_tier", "medium"),
            duration_ms=data.get("duration_ms", 0),
            verified=data.get("verified", False),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if "completed_at" in data
            else datetime.now(),
        )

    @classmethod
    def from_result(cls, result: ArtifactResult) -> ArtifactCompletion:
        """Create from ArtifactResult."""
        from sunwell.planning.naaru.persistence.hashing import hash_content

        content_hash = hash_content(result.content) if result.content else ""
        return cls(
            artifact_id=result.artifact_id,
            content_hash=content_hash,
            model_tier=result.model_tier,
            duration_ms=int(result.duration.total_seconds() * 1000),
            verified=result.verified,
        )
