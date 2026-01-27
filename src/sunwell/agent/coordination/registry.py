"""SubagentRegistry — Track spawned subagents and their lifecycle.

Inspired by moltbot's subagent-registry.ts but adapted for sunwell's
async/Python patterns and free-threading awareness.

Features:
- In-memory registry with optional disk persistence
- Listener pattern for lifecycle events
- Resume capability after process restart
- Thread-safe with explicit locking (3.14t compatible)
- Batch spawn and await for parallel task execution
"""

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.loop.config import LoopConfig
    from sunwell.planning.naaru.types import Task

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

    # =========================================================================
    # Heartbeat Monitoring (Agentic Infrastructure Phase 2)
    # =========================================================================
    last_heartbeat: datetime | None = None
    """When the last heartbeat was received."""

    heartbeat_interval_seconds: int = 30
    """Expected heartbeat interval. Used to detect stale subagents."""

    progress: float | None = None
    """Execution progress (0.0-1.0) if reported."""

    status_message: str | None = None
    """Current status message from the subagent."""

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

    @property
    def is_stale(self) -> bool:
        """True if no heartbeat received within 2x expected interval.

        A stale subagent may be hung and should be investigated or cancelled.
        """
        if not self.is_running:
            return False

        # Use last_heartbeat if available, otherwise started_at
        last_contact = self.last_heartbeat or self.started_at
        if last_contact is None:
            return False

        threshold_seconds = self.heartbeat_interval_seconds * 2
        elapsed = (datetime.now() - last_contact).total_seconds()
        return elapsed > threshold_seconds

    @property
    def seconds_since_heartbeat(self) -> float | None:
        """Seconds since last heartbeat (or start if no heartbeat yet)."""
        if not self.is_running:
            return None
        last_contact = self.last_heartbeat or self.started_at
        if last_contact is None:
            return None
        return (datetime.now() - last_contact).total_seconds()

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
            # Heartbeat fields
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "progress": self.progress,
            "status_message": self.status_message,
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
            # Heartbeat fields
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]) if data.get("last_heartbeat") else None,
            heartbeat_interval_seconds=data.get("heartbeat_interval_seconds", 30),
            progress=data.get("progress"),
            status_message=data.get("status_message"),
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

    # =========================================================================
    # Batch Operations (Agentic Infrastructure Phase 2)
    # =========================================================================

    def spawn_parallel(
        self,
        parent: SessionContext,
        tasks: list[Task],
        config: LoopConfig,
    ) -> list[SubagentRecord]:
        """Register subagents for parallelizable tasks.

        Creates SubagentRecords for each task, respecting:
        - max_concurrent_subagents from config
        - max_subagent_depth from config

        Does NOT actually execute the subagents - that's the executor's job.
        This just registers them in the registry.

        Args:
            parent: Parent session context
            tasks: Tasks to spawn subagents for
            config: Loop configuration with subagent limits

        Returns:
            List of registered SubagentRecords

        Raises:
            ValueError: If spawn depth exceeded or too many concurrent subagents
        """
        from sunwell.agent.context.session import SpawnDepthExceededError

        # Check depth limit
        if parent.spawn_depth >= config.max_subagent_depth:
            raise SpawnDepthExceededError(parent.spawn_depth, config.max_subagent_depth)

        # Check concurrent limit
        current_active = len(self.list_active())
        if current_active + len(tasks) > config.max_concurrent_subagents:
            available = max(0, config.max_concurrent_subagents - current_active)
            raise ValueError(
                f"Cannot spawn {len(tasks)} subagents: "
                f"only {available} slots available "
                f"(max={config.max_concurrent_subagents}, active={current_active})"
            )

        records: list[SubagentRecord] = []
        for task in tasks:
            # Create child session ID
            child_session_id = uuid.uuid4().hex[:16]

            record = self.register(
                child_session_id=child_session_id,
                parent_session_id=parent.session_id,
                task=task.description,
                cleanup=config.subagent_cleanup,
                label=task.id,
            )
            records.append(record)

        logger.info(
            "Spawned %d subagents for parent %s",
            len(records),
            parent.session_id,
        )
        return records

    async def await_all(
        self,
        records: list[SubagentRecord],
        timeout: float,
        poll_interval: float = 0.5,
    ) -> dict[str, SubagentOutcome]:
        """Wait for all subagents to complete.

        Polls the registry until all subagents have completed or timeout.

        Args:
            records: Subagent records to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: How often to check status in seconds

        Returns:
            Dict mapping run_id to outcome

        Note:
            Subagents that don't complete within timeout are marked as TIMEOUT.
        """
        run_ids = {r.run_id for r in records}
        start_time = asyncio.get_event_loop().time()
        results: dict[str, SubagentOutcome] = {}

        while run_ids - set(results.keys()):
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                # Mark remaining as timeout
                for run_id in run_ids - set(results.keys()):
                    self.mark_complete(run_id, SubagentOutcome.TIMEOUT)
                    results[run_id] = SubagentOutcome.TIMEOUT
                logger.warning(
                    "Subagent await timed out after %.1fs, %d timed out",
                    timeout,
                    len(run_ids) - len([o for o in results.values() if o != SubagentOutcome.TIMEOUT]),
                )
                break

            # Check status
            for run_id in run_ids - set(results.keys()):
                record = self.get(run_id)
                if record and record.is_complete and record.outcome:
                    results[run_id] = record.outcome

            # Wait before next poll
            if run_ids - set(results.keys()):
                await asyncio.sleep(poll_interval)

        return results

    def count_active_for_parent(self, parent_session_id: str) -> int:
        """Count active subagents for a specific parent.

        Args:
            parent_session_id: Parent session ID

        Returns:
            Number of currently running subagents
        """
        with self._lock:
            return sum(
                1 for r in self._runs.values()
                if r.parent_session_id == parent_session_id and r.is_running
            )

    # =========================================================================
    # Heartbeat Monitoring (Agentic Infrastructure Phase 2)
    # =========================================================================

    def heartbeat(
        self,
        run_id: str,
        progress: float | None = None,
        status: str | None = None,
    ) -> SubagentRecord | None:
        """Record a heartbeat from a subagent.

        Should be called periodically by running subagents to indicate
        they are still alive and making progress.

        Args:
            run_id: The run ID of the subagent
            progress: Optional progress (0.0-1.0)
            status: Optional status message

        Returns:
            Updated record or None if not found
        """
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                logger.warning("Heartbeat for unknown run %s", run_id)
                return None

            if not record.is_running:
                logger.warning("Heartbeat for non-running subagent %s", run_id)
                return None

            record.last_heartbeat = datetime.now()
            if progress is not None:
                record.progress = max(0.0, min(1.0, progress))
            if status is not None:
                record.status_message = status

            self._persist()

        self._notify_listeners(record, "heartbeat")
        logger.debug(
            "Heartbeat from %s: progress=%.1f%% status=%s",
            run_id,
            (record.progress or 0) * 100,
            status,
        )
        return record

    def get_stale(self, threshold_seconds: float | None = None) -> list[SubagentRecord]:
        """Get subagents that haven't sent heartbeat recently.

        A subagent is considered stale if:
        - It is running
        - No heartbeat received within threshold (default: 2x heartbeat_interval)

        Args:
            threshold_seconds: Custom threshold (default: use 2x heartbeat_interval)

        Returns:
            List of stale subagent records
        """
        with self._lock:
            stale: list[SubagentRecord] = []
            for record in self._runs.values():
                if not record.is_running:
                    continue

                # Use custom threshold or record's default
                if threshold_seconds is not None:
                    last_contact = record.last_heartbeat or record.started_at
                    if last_contact is None:
                        continue
                    elapsed = (datetime.now() - last_contact).total_seconds()
                    if elapsed > threshold_seconds:
                        stale.append(record)
                elif record.is_stale:
                    stale.append(record)

            return stale

    async def cancel_stale(
        self,
        threshold_seconds: float | None = None,
        reason: str = "No heartbeat received",
    ) -> int:
        """Cancel subagents that appear hung.

        Marks stale subagents as CANCELLED and notifies listeners.

        Args:
            threshold_seconds: Custom threshold (default: use is_stale property)
            reason: Reason message to include

        Returns:
            Number of subagents cancelled
        """
        stale = self.get_stale(threshold_seconds)
        cancelled = 0

        for record in stale:
            self.mark_complete(
                record.run_id,
                SubagentOutcome.CANCELLED,
                error_message=reason,
            )
            cancelled += 1
            logger.warning(
                "Cancelled stale subagent %s (last heartbeat: %s)",
                record.run_id,
                record.seconds_since_heartbeat,
            )

        if cancelled > 0:
            logger.info("Cancelled %d stale subagents", cancelled)

        return cancelled

    def list_with_progress(self) -> list[tuple[SubagentRecord, float | None]]:
        """List all running subagents with their progress.

        Returns:
            List of (record, progress) tuples for running subagents
        """
        with self._lock:
            return [
                (r, r.progress)
                for r in self._runs.values()
                if r.is_running
            ]

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
        """Notify all listeners of an event and emit hooks."""
        with self._lock:
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(record, event_type)
            except Exception:
                logger.exception("Listener failed for event %s", event_type)

        # Emit hook events
        self._emit_hook(record, event_type)

    def _emit_hook(self, record: SubagentRecord, event_type: str) -> None:
        """Emit hook events for subagent lifecycle."""
        from sunwell.agent.hooks import HookEvent, emit_hook_sync

        hook_event: HookEvent | None = None
        hook_data: dict[str, str | int | float | None] = {
            "run_id": record.run_id,
            "child_session_id": record.child_session_id,
            "parent_session_id": record.parent_session_id,
            "task": record.task,
        }

        if event_type == "register":
            hook_event = HookEvent.SUBAGENT_SPAWN
        elif event_type == "start":
            hook_event = HookEvent.SUBAGENT_START
        elif event_type == "heartbeat":
            hook_event = HookEvent.SUBAGENT_HEARTBEAT
            hook_data["progress"] = record.progress
            hook_data["status"] = record.status_message
        elif event_type == "complete":
            hook_event = HookEvent.SUBAGENT_COMPLETE
            hook_data["outcome"] = record.outcome.value if record.outcome else None
            hook_data["duration_ms"] = record.duration_ms

        if hook_event:
            emit_hook_sync(hook_event, **hook_data)

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
