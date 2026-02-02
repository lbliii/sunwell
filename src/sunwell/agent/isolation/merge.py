"""Merge strategies and result types for worktree isolation.

Defines how worktree changes are merged back to the main workspace:
- FAST_FORWARD: No conflicts possible (different files modified)
- THREE_WAY: May have conflicts (same files modified)
- ABORT_ON_CONFLICT: Fail immediately if any conflict detected
"""

from dataclasses import dataclass
from enum import Enum


class MergeStrategy(Enum):
    """Strategy for merging worktree changes back to main."""

    FAST_FORWARD = "fast_forward"
    """Fast-forward only - fails if branches have diverged.

    Use when tasks modify completely different files and no conflicts
    are possible. Fastest and safest option.
    """

    THREE_WAY = "three_way"
    """Three-way merge - may produce merge commits.

    Use when tasks might modify overlapping files. Git will attempt
    to auto-merge, creating a merge commit if successful.
    """

    ABORT_ON_CONFLICT = "abort"
    """Attempt merge but abort if any conflicts detected.

    Tries fast-forward first, then three-way, but aborts immediately
    if any conflicts are detected rather than leaving the repo in
    a conflicted state.
    """


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Result of merging a worktree back to main.

    Attributes:
        success: Whether the merge completed successfully
        strategy_used: Which merge strategy was applied
        files_merged: Paths of files that were merged
        conflicts: Paths of files with conflicts (if success=False)
        error: Error message if merge failed
    """

    success: bool
    """Whether the merge completed successfully."""

    strategy_used: MergeStrategy
    """Which merge strategy was applied."""

    files_merged: tuple[str, ...]
    """Paths of files that were merged (relative to workspace root)."""

    conflicts: tuple[str, ...] = ()
    """Paths of files with conflicts (if success=False)."""

    error: str | None = None
    """Error message if merge failed."""

    @property
    def has_conflicts(self) -> bool:
        """True if there were merge conflicts."""
        return len(self.conflicts) > 0

    @property
    def file_count(self) -> int:
        """Number of files involved in the merge."""
        return len(self.files_merged) + len(self.conflicts)

    def __str__(self) -> str:
        """Human-readable merge result summary."""
        if self.success:
            return f"Merged {len(self.files_merged)} file(s) ({self.strategy_used.value})"
        else:
            return f"Merge failed: {len(self.conflicts)} conflict(s)"
