"""Scope Tracking for Autonomy Guardrails (RFC-048).

Tracks and enforces scope limits on autonomous operations.
"""

from datetime import datetime
from pathlib import Path

from sunwell.quality.guardrails.types import (
    FileChange,
    ScopeCheckResult,
    ScopeLimits,
)


class ScopeTracker:
    """Track scope usage and enforce limits.

    Scope limits exist because even SAFE actions can become dangerous
    at scale. This tracker maintains session-level state and enforces
    both per-goal and per-session limits.
    """

    def __init__(self, limits: ScopeLimits | None = None):
        """Initialize scope tracker.

        Args:
            limits: Scope limits configuration (uses defaults if not provided)
        """
        self.limits = limits or ScopeLimits()
        self.session_files: set[Path] = set()
        self.session_lines_changed: int = 0
        self.session_goals_completed: int = 0
        self.session_start: datetime = datetime.now()
        self._goal_start: datetime | None = None

    def start_goal(self) -> None:
        """Mark the start of a new goal."""
        self._goal_start = datetime.now()

    def check_goal(
        self,
        planned_changes: list[FileChange],
        goal_id: str = "",
    ) -> ScopeCheckResult:
        """Check if a goal fits within limits.

        Args:
            planned_changes: List of planned file changes
            goal_id: Optional goal ID for error messages

        Returns:
            ScopeCheckResult indicating pass/fail and reason
        """
        # Check per-goal file limit
        files_count = len(planned_changes)
        if files_count > self.limits.max_files_per_goal:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Goal touches {files_count} files "
                    f"(limit: {self.limits.max_files_per_goal})"
                ),
                limit_type="files_per_goal",
            )

        # Check per-goal line limit
        lines_count = sum(
            c.lines_added + c.lines_removed for c in planned_changes
        )
        if lines_count > self.limits.max_lines_changed_per_goal:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Goal changes {lines_count} lines "
                    f"(limit: {self.limits.max_lines_changed_per_goal})"
                ),
                limit_type="lines_per_goal",
            )

        # Check per-goal duration (if goal has started)
        if self._goal_start:
            elapsed = datetime.now() - self._goal_start
            max_seconds = self.limits.max_duration_per_goal_minutes * 60
            if elapsed.total_seconds() > max_seconds:
                return ScopeCheckResult(
                    passed=False,
                    reason=(
                        f"Goal duration exceeded "
                        f"{self.limits.max_duration_per_goal_minutes} minutes"
                    ),
                    limit_type="duration_per_goal",
                )

        # Check session file limit
        new_files = {c.path for c in planned_changes}
        new_session_files = len(self.session_files | new_files)
        if new_session_files > self.limits.max_files_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Session would touch {new_session_files} files "
                    f"(limit: {self.limits.max_files_per_session})"
                ),
                limit_type="files_per_session",
            )

        # Check session line limit
        new_session_lines = self.session_lines_changed + lines_count
        if new_session_lines > self.limits.max_lines_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Session would change {new_session_lines} lines "
                    f"(limit: {self.limits.max_lines_per_session})"
                ),
                limit_type="lines_per_session",
            )

        # Check session goal limit
        if self.session_goals_completed >= self.limits.max_goals_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Session completed {self.session_goals_completed} goals "
                    f"(limit: {self.limits.max_goals_per_session})"
                ),
                limit_type="goals_per_session",
            )

        # Check session duration
        elapsed = datetime.now() - self.session_start
        max_seconds = self.limits.max_duration_per_session_hours * 3600
        if elapsed.total_seconds() > max_seconds:
            return ScopeCheckResult(
                passed=False,
                reason=(
                    f"Session duration exceeded "
                    f"{self.limits.max_duration_per_session_hours} hours"
                ),
                limit_type="duration_per_session",
            )

        # Check source+test requirement
        if self.limits.require_tests_for_source_changes:
            source_files = [c for c in planned_changes if self._is_source_file(c.path)]
            test_files = [c for c in planned_changes if self._is_test_file(c.path)]

            if source_files and not test_files:
                return ScopeCheckResult(
                    passed=False,
                    reason="Source changes require corresponding test changes",
                    limit_type="require_tests",
                )

        return ScopeCheckResult(passed=True, reason="Within limits")

    def record_goal_completion(self, changes: list[FileChange]) -> None:
        """Record completed goal for session tracking.

        Args:
            changes: List of file changes that were made
        """
        self.session_files.update(c.path for c in changes)
        self.session_lines_changed += sum(
            c.lines_added + c.lines_removed for c in changes
        )
        self.session_goals_completed += 1
        self._goal_start = None

    def get_session_stats(self) -> dict:
        """Get current session statistics.

        Returns:
            Dictionary with session stats
        """
        elapsed = datetime.now() - self.session_start
        return {
            "files_touched": len(self.session_files),
            "lines_changed": self.session_lines_changed,
            "goals_completed": self.session_goals_completed,
            "duration_minutes": elapsed.total_seconds() / 60,
            "limits": {
                "files_remaining": (
                    self.limits.max_files_per_session - len(self.session_files)
                ),
                "lines_remaining": (
                    self.limits.max_lines_per_session - self.session_lines_changed
                ),
                "goals_remaining": (
                    self.limits.max_goals_per_session - self.session_goals_completed
                ),
            },
        }

    def can_continue(self) -> ScopeCheckResult:
        """Check if session can continue (no limits exceeded).

        Returns:
            ScopeCheckResult indicating if session can continue
        """
        # Check goal limit
        if self.session_goals_completed >= self.limits.max_goals_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session goal limit reached ({self.limits.max_goals_per_session})",
                limit_type="goals_per_session",
            )

        # Check file limit
        if len(self.session_files) >= self.limits.max_files_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session file limit reached ({self.limits.max_files_per_session})",
                limit_type="files_per_session",
            )

        # Check line limit
        if self.session_lines_changed >= self.limits.max_lines_per_session:
            return ScopeCheckResult(
                passed=False,
                reason=f"Session line limit reached ({self.limits.max_lines_per_session})",
                limit_type="lines_per_session",
            )

        # Check duration
        elapsed = datetime.now() - self.session_start
        max_seconds = self.limits.max_duration_per_session_hours * 3600
        if elapsed.total_seconds() > max_seconds:
            max_hours = self.limits.max_duration_per_session_hours
            return ScopeCheckResult(
                passed=False,
                reason=f"Session duration limit reached ({max_hours}h)",
                limit_type="duration_per_session",
            )

        return ScopeCheckResult(passed=True, reason="Session can continue")

    def reset_session(self) -> None:
        """Reset session tracking (start fresh)."""
        self.session_files = set()
        self.session_lines_changed = 0
        self.session_goals_completed = 0
        self.session_start = datetime.now()
        self._goal_start = None

    def _is_source_file(self, path: Path) -> bool:
        """Check if path is a source file (not test/docs)."""
        path_str = str(path)
        # Not a test file
        if self._is_test_file(path):
            return False
        # Not docs
        if "docs/" in path_str or path_str.endswith(".md"):
            return False
        # Is Python/source
        return path_str.endswith((".py", ".js", ".ts", ".jsx", ".tsx"))

    def _is_test_file(self, path: Path) -> bool:
        """Check if path is a test file."""
        path_str = str(path)
        return (
            "tests/" in path_str
            or "test_" in path.name
            or path.name.endswith("_test.py")
        )
