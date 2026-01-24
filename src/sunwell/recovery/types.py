"""Type definitions for Recovery & Review system (RFC-125).

Immutable data structures for recovery state and artifacts.
All types are frozen dataclasses with slots for performance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactStatus(Enum):
    """Status of a single artifact in recovery state."""

    PASSED = "passed"
    """All gates passed — artifact is valid."""

    FAILED = "failed"
    """Gate(s) failed — needs review."""

    WAITING = "waiting"
    """Blocked on failed dependency."""

    SKIPPED = "skipped"
    """User chose to skip."""

    FIXED = "fixed"
    """User fixed manually."""


@dataclass(frozen=True, slots=True)
class RecoveryArtifact:
    """A single artifact with its validation state.

    Captures both the content and validation results so user
    can review what was generated and what went wrong.

    Attributes:
        path: File path for the artifact
        content: Generated content (may have errors)
        status: Current validation status
        errors: Specific error messages (empty if passed)
        depends_on: Artifact IDs this depends on
    """

    path: Path
    content: str
    status: ArtifactStatus
    errors: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()

    @property
    def needs_review(self) -> bool:
        """True if this artifact requires user attention."""
        return self.status == ArtifactStatus.FAILED

    @property
    def is_resolved(self) -> bool:
        """True if this artifact is in a resolved state."""
        return self.status in (ArtifactStatus.PASSED, ArtifactStatus.FIXED, ArtifactStatus.SKIPPED)

    def with_status(self, status: ArtifactStatus) -> RecoveryArtifact:
        """Return a new artifact with updated status."""
        return RecoveryArtifact(
            path=self.path,
            content=self.content,
            status=status,
            errors=self.errors,
            depends_on=self.depends_on,
        )

    def with_content(self, content: str) -> RecoveryArtifact:
        """Return a new artifact with updated content (marks as FIXED)."""
        return RecoveryArtifact(
            path=self.path,
            content=content,
            status=ArtifactStatus.FIXED,
            errors=(),  # Clear errors since content changed
            depends_on=self.depends_on,
        )


@dataclass
class RecoveryState:
    """Complete state for recovery/review workflow.

    Saved to: .sunwell/recovery/{goal_hash}.json

    This captures everything needed to:
    1. Show user what succeeded vs failed
    2. Provide context for agent to retry
    3. Allow user to manually fix and resume

    Attributes:
        goal: Original goal text
        goal_hash: Deterministic hash for lookup
        run_id: Unique run identifier
        artifacts: All artifacts with their states
        failed_gate: Which gate triggered the failure
        failure_reason: Why the failure occurred
        error_details: Detailed error messages
        iteration_history: History of convergence iterations
        fix_attempts: History of fix attempts
        created_at: When recovery state was created
        updated_at: When last modified
    """

    goal: str
    goal_hash: str
    run_id: str

    artifacts: dict[str, RecoveryArtifact] = field(default_factory=dict)

    failed_gate: str | None = None
    failure_reason: str = ""
    error_details: list[str] = field(default_factory=list)

    iteration_history: list[dict[str, Any]] = field(default_factory=list)
    fix_attempts: list[dict[str, Any]] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def passed_artifacts(self) -> list[RecoveryArtifact]:
        """Artifacts that passed validation."""
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.PASSED]

    @property
    def failed_artifacts(self) -> list[RecoveryArtifact]:
        """Artifacts that failed validation."""
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.FAILED]

    @property
    def waiting_artifacts(self) -> list[RecoveryArtifact]:
        """Artifacts waiting on failed dependencies."""
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.WAITING]

    @property
    def fixed_artifacts(self) -> list[RecoveryArtifact]:
        """Artifacts that user fixed manually."""
        return [a for a in self.artifacts.values() if a.status == ArtifactStatus.FIXED]

    @property
    def recovery_possible(self) -> bool:
        """True if any artifacts passed — worth recovering."""
        return len(self.passed_artifacts) > 0

    @property
    def is_resolved(self) -> bool:
        """True if all artifacts are in a resolved state."""
        return all(a.is_resolved for a in self.artifacts.values())

    @property
    def summary(self) -> str:
        """Short summary for display."""
        passed = len(self.passed_artifacts)
        failed = len(self.failed_artifacts)
        waiting = len(self.waiting_artifacts)
        return f"✅ {passed} passed, ⚠️ {failed} failed, ⏸️ {waiting} waiting"

    def mark_fixed(self, path: str, new_content: str) -> None:
        """Mark an artifact as fixed with new content."""
        if path in self.artifacts:
            self.artifacts[path] = self.artifacts[path].with_content(new_content)
            self.updated_at = datetime.now()

    def mark_skipped(self, path: str) -> None:
        """Mark an artifact as skipped."""
        if path in self.artifacts:
            self.artifacts[path] = self.artifacts[path].with_status(ArtifactStatus.SKIPPED)
            self.updated_at = datetime.now()


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    """Lightweight summary for listing recoveries.

    Used by `sunwell review --list` to show pending recoveries
    without loading full state.
    """

    goal_hash: str
    goal_preview: str  # First 80 chars of goal
    run_id: str
    passed: int
    failed: int
    waiting: int
    created_at: datetime

    @property
    def total(self) -> int:
        """Total artifact count."""
        return self.passed + self.failed + self.waiting

    @property
    def age_str(self) -> str:
        """Human-readable age (e.g., '2 hours ago')."""
        delta = datetime.now() - self.created_at
        if delta.days > 0:
            return f"{delta.days} days ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        minutes = delta.seconds // 60
        return f"{minutes} minutes ago"
