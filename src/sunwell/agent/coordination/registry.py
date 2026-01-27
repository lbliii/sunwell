"""SubagentRegistry — Track spawned subagents and their lifecycle.

Inspired by moltbot's subagent-registry.ts but adapted for sunwell's
async/Python patterns and free-threading awareness.

Features:
- In-memory registry with optional disk persistence
- Listener pattern for lifecycle events
- Resume capability after process restart
- Thread-safe with explicit locking (3.14t compatible)
"""

import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class SubagentOutcome(Enum):
    """Outcome of a subagent run."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class SubagentRecord:
    """Track a spawned subagent."""

    run_id: str
    """Unique run identifier."""

    child_session_id: str
    """Session ID of the spawned subagent."""

    parent_session_id: str
    """Session ID of the parent that spawned this subagent."""

    task: str
    """Task/goal assigned to the subagent."""

    cleanup: Literal["delete", "keep"]
    """Cleanup policy for session state after completion."""

    created_at: datetime
    """When the subagent was registered."""

    label: str | None = None
    """Optional label for identification."""

    started_at: datetime | None = None
    """When the subagent started execution (may be delayed)."""

    ended_at: datetime | None = None
    """When the subagent completed (success or failure)."""

    outcome: SubagentOutcome | None = None
    """Outcome of the run (ok, error, timeout, cancelled)."""

    error_message: str | None = None
    """Error message if outcome is ERROR."""

    @property
    def is_pending(self) -> bool:
        """True if not yet started."""
        return self.started_at is None

    @property
    def is_running(self) -> bool:
        """True if started but not ended."""
        return self.started_at is not None and self.ended_at is None

    @property
    def is_complete(self) -> bool:
        """True if ended (success or failure)."""
        return self.ended_at is not None

    @property
    def duration_ms(self) -> int | None:
        """Duration in milliseconds if complete."""
        if self.started_at is None or self.ended_at is None:
            return None
        delta = self.ended_at - self.started_at
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "run_id": self.run_id,
            "child_session_id": self.child_session_id,
            "parent_session_id": self.parent_session_id,
            "task": self.task,
            "cleanup": self.cleanup,
            "label": self.label,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "outcome": self.outcome.value if self.outcome else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SubagentRecord:
        """Deserialize from persistence."""
        return cls(
            run_id=data["run_id"],
            child_session_id=data["child_session_id"],
            parent_session_id=data["parent_session_id"],
            task=data["task"],
            cleanup=data["cleanup"],
            label=data.get("label"),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            outcome=SubagentOutcome(data["outcome"]) if data.get("outcome") else None,
            error_message=data.get("error_message"),
        )


# Type alias for listener callbacks
SubagentListener = Callable[[SubagentRecord, str], None]
"""Listener callback: (record, event_type) where event_type is 'register', 'start', 'complete'."""


@dataclass
class SubagentRegistry:
    """In-memory registry for tracking active subagents.

    Thread-safe with explicit locking for Python 3.14t free-threading.
    Supports optional disk persistence for crash recovery.

    Usage:
        registry = SubagentRegistry()

        # Register a new subagent
        record = registry.register(
            child_session_id="abc123",
            parent_session_id="parent456",
            task="Implement auth module",
        )

        # Mark as started
        registry.mark_started(record.run_id)

        # Mark as complete
        registry.mark_complete(record.run_id, SubagentOutcome.OK)

        # List subagents for a parent
        children = registry.list_for_parent("parent456")
    """

    _runs: dict[str, SubagentRecord] = field(default_factory=dict)
    """All registered subagent runs."""

    _listeners: set[SubagentListener] = field(default_factory=set)
    """Registered lifecycle listeners."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    _persistence_path: Path | None = None
    """Optional path for disk persistence."""

    def register(
        self,
        child_session_id: str,
        parent_session_id: str,
        task: str,
        cleanup: Literal["delete", "keep"] = "delete",
        label: str | None = None,
    ) -> SubagentRecord:
        """Register a new subagent run.

        Args:
            child_session_id: Session ID of the spawned subagent
            parent_session_id: Session ID of the parent
            task: Task/goal for the subagent
            cleanup: Cleanup policy after completion
            label: Optional label for identification

        Returns:
            The created SubagentRecord
        """
        run_id = uuid.uuid4().hex[:16]
        record = SubagentRecord(
            run_id=run_id,
            child_session_id=child_session_id,
            parent_session_id=parent_session_id,
            task=task,
            cleanup=cleanup,
            label=label,
            created_at=datetime.now(),
        )

        with self._lock:
            self._runs[run_id] = record
            self._persist()

        self._notify_listeners(record, "register")
        logger.debug("Registered subagent %s for parent %s", run_id, parent_session_id)
        return record

    def mark_started(self, run_id: str) -> SubagentRecord | None:
        """Mark a subagent as started.

        Args:
            run_id: The run ID to mark

        Returns:
            Updated record or None if not found
        """
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                logger.warning("Cannot mark started: run %s not found", run_id)
                return None
            record.started_at = datetime.now()
            self._persist()

        self._notify_listeners(record, "start")
        logger.debug("Subagent %s started", run_id)
        return record

    def mark_complete(
        self,
        run_id: str,
        outcome: SubagentOutcome,
        error_message: str | None = None,
    ) -> SubagentRecord | None:
        """Mark a subagent as complete.

        Args:
            run_id: The run ID to mark
            outcome: The outcome (ok, error, timeout, cancelled)
            error_message: Optional error message if outcome is ERROR

        Returns:
            Updated record or None if not found
        """
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                logger.warning("Cannot mark complete: run %s not found", run_id)
                return None
            record.ended_at = datetime.now()
            record.outcome = outcome
            record.error_message = error_message
            self._persist()

        self._notify_listeners(record, "complete")
        logger.debug("Subagent %s completed with outcome %s", run_id, outcome.value)
        return record

    def get(self, run_id: str) -> SubagentRecord | None:
        """Get a subagent record by run ID."""
        with self._lock:
            return self._runs.get(run_id)

    def list_for_parent(self, parent_session_id: str) -> list[SubagentRecord]:
        """List all subagents for a parent session.

        Args:
            parent_session_id: The parent session ID

        Returns:
            List of subagent records (may be empty)
        """
        with self._lock:
            return [
                r for r in self._runs.values()
                if r.parent_session_id == parent_session_id
            ]

    def list_active(self) -> list[SubagentRecord]:
        """List all active (running) subagents."""
        with self._lock:
            return [r for r in self._runs.values() if r.is_running]

    def list_pending(self) -> list[SubagentRecord]:
        """List all pending (not yet started) subagents."""
        with self._lock:
            return [r for r in self._runs.values() if r.is_pending]

    def remove(self, run_id: str) -> bool:
        """Remove a subagent record.

        Args:
            run_id: The run ID to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if run_id in self._runs:
                del self._runs[run_id]
                self._persist()
                logger.debug("Removed subagent %s", run_id)
                return True
            return False

    def cleanup_completed(self, max_age_hours: int = 24) -> int:
        """Remove completed subagents older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours for completed subagents

        Returns:
            Number of records removed
        """
        cutoff = datetime.now()
        removed = 0

        with self._lock:
            to_remove = []
            for run_id, record in self._runs.items():
                if not record.is_complete:
                    continue
                if record.ended_at is None:
                    continue
                age_hours = (cutoff - record.ended_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(run_id)

            for run_id in to_remove:
                del self._runs[run_id]
                removed += 1

            if removed > 0:
                self._persist()
                logger.info("Cleaned up %d completed subagents", removed)

        return removed

    def add_listener(self, listener: SubagentListener) -> Callable[[], None]:
        """Add a lifecycle listener.

        Args:
            listener: Callback (record, event_type) for lifecycle events

        Returns:
            Unsubscribe function
        """
        with self._lock:
            self._listeners.add(listener)
        return lambda: self._remove_listener(listener)

    def _remove_listener(self, listener: SubagentListener) -> None:
        """Remove a listener."""
        with self._lock:
            self._listeners.discard(listener)

    def _notify_listeners(self, record: SubagentRecord, event_type: str) -> None:
        """Notify all listeners of an event."""
        with self._lock:
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(record, event_type)
            except Exception:
                logger.exception("Listener failed for event %s", event_type)

    def set_persistence_path(self, path: Path) -> None:
        """Set the persistence path and load existing data.

        Args:
            path: Path to the persistence file (JSON)
        """
        self._persistence_path = path
        self._restore()

    def _persist(self) -> None:
        """Persist current state to disk (if path is set)."""
        if self._persistence_path is None:
            return

        try:
            data = {
                "version": 1,
                "runs": {run_id: record.to_dict() for run_id, record in self._runs.items()},
            }
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(json.dumps(data, indent=2))
        except Exception:
            logger.exception("Failed to persist subagent registry")

    def _restore(self) -> None:
        """Restore state from disk (if path is set and exists)."""
        if self._persistence_path is None or not self._persistence_path.exists():
            return

        try:
            data = json.loads(self._persistence_path.read_text())
            if data.get("version") != 1:
                logger.warning("Unknown registry version, skipping restore")
                return

            with self._lock:
                for run_id, record_data in data.get("runs", {}).items():
                    self._runs[run_id] = SubagentRecord.from_dict(record_data)

            logger.info("Restored %d subagent records from disk", len(self._runs))
        except Exception:
            logger.exception("Failed to restore subagent registry")

    def clear(self) -> None:
        """Clear all records (for testing)."""
        with self._lock:
            self._runs.clear()
            self._persist()


# Global registry instance (lazily initialized)
_global_registry: SubagentRegistry | None = None
_global_registry_lock = threading.Lock()


def get_registry() -> SubagentRegistry:
    """Get the global SubagentRegistry instance.

    The registry is lazily initialized on first access.
    Thread-safe.
    """
    global _global_registry
    if _global_registry is None:
        with _global_registry_lock:
            if _global_registry is None:
                _global_registry = SubagentRegistry()
    return _global_registry


def reset_registry_for_tests() -> None:
    """Reset the global registry (for testing only)."""
    global _global_registry
    with _global_registry_lock:
        if _global_registry is not None:
            _global_registry.clear()
        _global_registry = None
