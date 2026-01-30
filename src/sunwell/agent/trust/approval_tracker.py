"""Approval pattern tracking for adaptive trust.

Tracks user approval decisions to learn patterns and suggest
autonomy upgrades when users consistently approve certain operations.

Thread Safety:
    Uses threading.Lock for thread-safe operations (Python 3.14t compatible).
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sunwell.agent.intent.dag import IntentNode, IntentPath

logger = logging.getLogger(__name__)

# Default threshold for suggesting auto-approve
DEFAULT_APPROVAL_THRESHOLD = 10

# Minimum approval ratio to suggest upgrade (approvals / total decisions)
MIN_APPROVAL_RATIO = 0.9


@dataclass(slots=True)
class ApprovalPattern:
    """Tracks approval history for a specific intent path.

    Attributes:
        intent_path: The DAG path being tracked, e.g., ("ACT", "WRITE", "CREATE")
        approval_count: Number of times user approved this path
        rejection_count: Number of times user rejected this path
        last_decision: Timestamp of most recent decision
        last_approved: Whether the last decision was an approval
    """

    intent_path: tuple[str, ...]
    approval_count: int = 0
    rejection_count: int = 0
    last_decision: datetime | None = None
    last_approved: bool | None = None

    @property
    def total_decisions(self) -> int:
        """Total number of decisions made for this path."""
        return self.approval_count + self.rejection_count

    @property
    def approval_ratio(self) -> float:
        """Ratio of approvals to total decisions (0.0-1.0)."""
        if self.total_decisions == 0:
            return 0.0
        return self.approval_count / self.total_decisions

    def record(self, approved: bool) -> None:
        """Record a new decision."""
        if approved:
            self.approval_count += 1
        else:
            self.rejection_count += 1
        self.last_decision = datetime.now(timezone.utc)
        self.last_approved = approved

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "intent_path": list(self.intent_path),
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "last_decision": self.last_decision.isoformat() if self.last_decision else None,
            "last_approved": self.last_approved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalPattern":
        """Deserialize from dictionary."""
        last_decision = None
        if data.get("last_decision"):
            last_decision = datetime.fromisoformat(data["last_decision"])

        return cls(
            intent_path=tuple(data["intent_path"]),
            approval_count=data.get("approval_count", 0),
            rejection_count=data.get("rejection_count", 0),
            last_decision=last_decision,
            last_approved=data.get("last_approved"),
        )


@dataclass
class ApprovalTracker:
    """Tracks approval patterns to learn user preferences.

    Persists approval history to disk and provides methods to:
    - Record approval/rejection decisions
    - Query candidates for auto-approve upgrade
    - Check if a specific path should trigger upgrade suggestion

    Thread-safe for concurrent access.

    Example:
        >>> tracker = ApprovalTracker(workspace)
        >>> tracker.record_decision(path, approved=True)
        >>> if tracker.should_suggest_upgrade(path):
        ...     print("Consider auto-approving this operation type")
    """

    workspace: Path
    """Workspace root directory."""

    approval_threshold: int = DEFAULT_APPROVAL_THRESHOLD
    """Number of approvals before suggesting auto-approve."""

    min_approval_ratio: float = MIN_APPROVAL_RATIO
    """Minimum approval ratio (0.0-1.0) to suggest upgrade."""

    _patterns: dict[tuple[str, ...], ApprovalPattern] = field(
        default_factory=dict, init=False
    )
    """In-memory pattern cache."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Thread safety lock."""

    _loaded: bool = field(default=False, init=False)
    """Whether patterns have been loaded from disk."""

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace)

    @property
    def _storage_path(self) -> Path:
        """Path to approval history storage file."""
        return self.workspace / ".sunwell" / "trust" / "approval-history.jsonl"

    def _ensure_loaded(self) -> None:
        """Load patterns from disk if not already loaded."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            if self._storage_path.exists():
                try:
                    with open(self._storage_path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            data = json.loads(line)
                            pattern = ApprovalPattern.from_dict(data)
                            self._patterns[pattern.intent_path] = pattern
                    logger.debug(
                        "Loaded %d approval patterns from %s",
                        len(self._patterns),
                        self._storage_path,
                    )
                except Exception as e:
                    logger.warning("Failed to load approval history: %s", e)

            self._loaded = True

    def _save_pattern(self, pattern: ApprovalPattern) -> None:
        """Append pattern update to storage file."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "a") as f:
                f.write(json.dumps(pattern.to_dict()) + "\n")
        except Exception as e:
            logger.warning("Failed to save approval pattern: %s", e)

    def _path_to_key(self, path: IntentPath) -> tuple[str, ...]:
        """Convert IntentPath to storage key (tuple of node values)."""
        return tuple(node.value for node in path)

    def record_decision(self, path: IntentPath, approved: bool) -> None:
        """Record a user's approval or rejection decision.

        Args:
            path: The intent DAG path for this decision
            approved: True if user approved, False if rejected
        """
        self._ensure_loaded()
        key = self._path_to_key(path)

        with self._lock:
            if key not in self._patterns:
                self._patterns[key] = ApprovalPattern(intent_path=key)

            pattern = self._patterns[key]
            pattern.record(approved)
            self._save_pattern(pattern)

        logger.debug(
            "Recorded %s for path %s (total: %d approvals, %d rejections)",
            "approval" if approved else "rejection",
            key,
            pattern.approval_count,
            pattern.rejection_count,
        )

    def get_pattern(self, path: IntentPath) -> ApprovalPattern | None:
        """Get the approval pattern for a specific path.

        Args:
            path: The intent DAG path to look up

        Returns:
            ApprovalPattern if found, None otherwise
        """
        self._ensure_loaded()
        key = self._path_to_key(path)
        return self._patterns.get(key)

    def should_suggest_upgrade(self, path: IntentPath) -> bool:
        """Check if this path should trigger an auto-approve upgrade suggestion.

        Criteria:
        - At least `approval_threshold` total approvals
        - Approval ratio >= `min_approval_ratio`
        - Not already suggested (would be in auto-approve config)

        Args:
            path: The intent DAG path to check

        Returns:
            True if upgrade should be suggested
        """
        pattern = self.get_pattern(path)
        if pattern is None:
            return False

        # Check threshold
        if pattern.approval_count < self.approval_threshold:
            return False

        # Check ratio
        if pattern.approval_ratio < self.min_approval_ratio:
            return False

        return True

    def get_auto_approve_candidates(
        self,
        threshold: int | None = None,
    ) -> list[tuple[tuple[str, ...], ApprovalPattern]]:
        """Get all paths that are candidates for auto-approve.

        Args:
            threshold: Override approval threshold (default: self.approval_threshold)

        Returns:
            List of (path_key, pattern) tuples meeting criteria
        """
        self._ensure_loaded()
        threshold = threshold or self.approval_threshold

        candidates: list[tuple[tuple[str, ...], ApprovalPattern]] = []

        with self._lock:
            for key, pattern in self._patterns.items():
                if (
                    pattern.approval_count >= threshold
                    and pattern.approval_ratio >= self.min_approval_ratio
                ):
                    candidates.append((key, pattern))

        # Sort by approval count descending
        candidates.sort(key=lambda x: x[1].approval_count, reverse=True)
        return candidates

    def get_statistics(self) -> dict:
        """Get summary statistics for approval patterns.

        Returns:
            Dictionary with stats like total_decisions, paths_tracked, etc.
        """
        self._ensure_loaded()

        with self._lock:
            total_approvals = sum(p.approval_count for p in self._patterns.values())
            total_rejections = sum(p.rejection_count for p in self._patterns.values())
            candidates = len(self.get_auto_approve_candidates())

            return {
                "paths_tracked": len(self._patterns),
                "total_approvals": total_approvals,
                "total_rejections": total_rejections,
                "total_decisions": total_approvals + total_rejections,
                "auto_approve_candidates": candidates,
            }

    def clear(self) -> None:
        """Clear all approval patterns (for testing)."""
        with self._lock:
            self._patterns.clear()
            if self._storage_path.exists():
                self._storage_path.unlink()
            self._loaded = True
