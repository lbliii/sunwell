"""Intervention detection for identifying when human help is needed.

Detects patterns that suggest the agent is stuck or misbehaving,
signaling that human intervention may be required.

Example:
    >>> detector = InterventionDetector()
    >>> signal = detector.record_file_edit("/path/to/file.py")
    >>> if signal:
    ...     print(f"INTERVENTION: {signal.reason} - {signal.suggested_action}")
"""

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class InterventionReason(Enum):
    """Reasons for recommending human intervention."""

    CONSECUTIVE_FAILURES = "consecutive_failures"
    """Multiple consecutive tool/task failures."""

    SAME_FILE_EDITED_REPEATEDLY = "same_file_edited_repeatedly"
    """Same file edited many times (may be stuck in a loop)."""

    BUDGET_LOW = "budget_low"
    """Token or cost budget running low."""

    VALIDATION_GATE_FAILED_TWICE = "validation_gate_failed_twice"
    """Same validation gate failed multiple times."""

    SCOPE_LIMIT_APPROACHING = "scope_limit_approaching"
    """Approaching scope limits (files modified, etc.)."""

    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    """Circuit breaker tripped due to failures."""

    LONG_RUNNING = "long_running"
    """Task running longer than expected."""

    STUCK_ON_SAME_ERROR = "stuck_on_same_error"
    """Same error keeps occurring."""


@dataclass(frozen=True, slots=True)
class InterventionSignal:
    """Signal that human intervention may be needed.

    Attributes:
        reason: Why intervention is recommended
        details: Human-readable explanation
        severity: info, warning, or critical
        suggested_action: What the human should do
    """

    reason: InterventionReason
    details: str
    severity: str  # "info", "warning", "critical"
    suggested_action: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "reason": self.reason.value,
            "details": self.details,
            "severity": self.severity,
            "suggested_action": self.suggested_action,
        }


@dataclass
class InterventionDetector:
    """Detects situations requiring human intervention.

    Tracks various patterns that suggest the agent may need help:
    - Consecutive failures
    - Same file edited repeatedly
    - Budget warnings
    - Validation gate failures
    - Long-running tasks

    Attributes:
        consecutive_failure_threshold: Failures before signaling (default 3)
        file_edit_threshold: Edits to same file before signaling (default 5)
        budget_warning_threshold: Budget ratio to warn at (default 0.2)
        long_running_minutes: Minutes before long-running warning (default 30)
    """

    consecutive_failure_threshold: int = 3
    """Number of consecutive failures before signaling."""

    file_edit_threshold: int = 5
    """Number of edits to same file before signaling."""

    budget_warning_threshold: float = 0.2
    """Budget ratio remaining to trigger warning (0.0-1.0)."""

    long_running_minutes: int = 30
    """Minutes before task is considered long-running."""

    error_repeat_threshold: int = 3
    """Number of times same error can repeat before signaling."""

    # Tracking state (mutable)
    _file_edit_counts: dict[str, int] = field(default_factory=dict, init=False)
    _consecutive_failures: int = field(default=0, init=False)
    _gate_failures: dict[str, int] = field(default_factory=dict, init=False)
    _error_counts: dict[str, int] = field(default_factory=dict, init=False)
    _start_time: float = field(default_factory=time, init=False)
    _budget_warning_emitted: bool = field(default=False, init=False)

    def record_file_edit(self, path: str) -> InterventionSignal | None:
        """Record a file edit and check for intervention signal.

        Args:
            path: Path to the file being edited

        Returns:
            InterventionSignal if threshold exceeded, None otherwise
        """
        self._file_edit_counts[path] = self._file_edit_counts.get(path, 0) + 1
        count = self._file_edit_counts[path]

        if count >= self.file_edit_threshold:
            return InterventionSignal(
                reason=InterventionReason.SAME_FILE_EDITED_REPEATEDLY,
                details=f"{path} edited {count} times",
                severity="warning",
                suggested_action="Review changes - agent may be stuck in a loop",
            )
        return None

    def record_failure(self, error: str | None = None) -> InterventionSignal | None:
        """Record a failure and check for intervention signal.

        Args:
            error: Optional error message for pattern tracking

        Returns:
            InterventionSignal if threshold exceeded, None otherwise
        """
        self._consecutive_failures += 1

        # Track error patterns
        if error:
            error_key = error[:100]  # Truncate for grouping
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

            if self._error_counts[error_key] >= self.error_repeat_threshold:
                return InterventionSignal(
                    reason=InterventionReason.STUCK_ON_SAME_ERROR,
                    details=f"Error occurred {self._error_counts[error_key]} times: {error_key}",
                    severity="warning",
                    suggested_action="Investigate recurring error - may need code changes",
                )

        if self._consecutive_failures >= self.consecutive_failure_threshold:
            return InterventionSignal(
                reason=InterventionReason.CONSECUTIVE_FAILURES,
                details=f"{self._consecutive_failures} consecutive failures",
                severity="warning",
                suggested_action="Check agent logs - may need manual intervention",
            )
        return None

    def record_success(self) -> None:
        """Record a success, resetting consecutive failure count."""
        self._consecutive_failures = 0

    def check_budget(self, remaining_ratio: float) -> InterventionSignal | None:
        """Check if budget is running low.

        Args:
            remaining_ratio: Ratio of budget remaining (0.0-1.0)

        Returns:
            InterventionSignal if below threshold, None otherwise
        """
        if self._budget_warning_emitted:
            return None

        if remaining_ratio <= self.budget_warning_threshold:
            self._budget_warning_emitted = True
            severity = "warning" if remaining_ratio > 0.1 else "critical"
            return InterventionSignal(
                reason=InterventionReason.BUDGET_LOW,
                details=f"{remaining_ratio*100:.0f}% budget remaining",
                severity=severity,
                suggested_action="Consider stopping or extending budget",
            )
        return None

    def record_gate_failure(self, gate_name: str) -> InterventionSignal | None:
        """Record a validation gate failure.

        Args:
            gate_name: Name of the gate that failed

        Returns:
            InterventionSignal if same gate failed multiple times
        """
        self._gate_failures[gate_name] = self._gate_failures.get(gate_name, 0) + 1
        count = self._gate_failures[gate_name]

        if count >= 2:
            return InterventionSignal(
                reason=InterventionReason.VALIDATION_GATE_FAILED_TWICE,
                details=f"Gate '{gate_name}' failed {count} times",
                severity="warning",
                suggested_action="Agent may be stuck on validation - review code",
            )
        return None

    def check_running_time(self) -> InterventionSignal | None:
        """Check if task has been running too long.

        Returns:
            InterventionSignal if running longer than threshold
        """
        elapsed_minutes = (time() - self._start_time) / 60

        if elapsed_minutes >= self.long_running_minutes:
            return InterventionSignal(
                reason=InterventionReason.LONG_RUNNING,
                details=f"Task running for {elapsed_minutes:.0f} minutes",
                severity="info",
                suggested_action="Check progress - task may need review",
            )
        return None

    def reset(self) -> None:
        """Reset all tracking state."""
        self._file_edit_counts = {}
        self._consecutive_failures = 0
        self._gate_failures = {}
        self._error_counts = {}
        self._start_time = time()
        self._budget_warning_emitted = False

    def get_summary(self) -> dict[str, Any]:
        """Get summary of current intervention tracking state.

        Returns:
            Dictionary with tracking statistics
        """
        elapsed_minutes = (time() - self._start_time) / 60
        return {
            "consecutive_failures": self._consecutive_failures,
            "file_edits": dict(self._file_edit_counts),
            "gate_failures": dict(self._gate_failures),
            "error_counts": dict(self._error_counts),
            "elapsed_minutes": round(elapsed_minutes, 1),
            "budget_warning_emitted": self._budget_warning_emitted,
        }
