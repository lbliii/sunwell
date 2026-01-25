"""External Event Store (RFC-049).

Persistent store for external events with write-ahead logging for crash recovery.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sunwell.external.types import EventSource, EventType, ExternalEvent

logger = logging.getLogger(__name__)


class ExternalEventStore:
    """Persistent store for external events with WAL for crash recovery.

    Storage structure:
    - .sunwell/external/events.jsonl — Event history
    - .sunwell/external/wal.jsonl — Write-ahead log for crash recovery
    """

    def __init__(self, root: Path):
        """Initialize event store.

        Args:
            root: Project root directory
        """
        self._root = Path(root)
        self._base_path = self._root / ".sunwell" / "external"
        self._events_path = self._base_path / "events.jsonl"
        self._wal_path = self._base_path / "wal.jsonl"

        # Ensure directory exists
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def store(self, event: ExternalEvent) -> None:
        """Store an event in the event log.

        Args:
            event: The event to store
        """
        entry = self._serialize_event(event)
        entry["stored_at"] = datetime.now(UTC).isoformat()

        with open(self._events_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    async def get_by_ref(self, external_ref: str) -> ExternalEvent | None:
        """Retrieve event by external reference.

        Args:
            external_ref: External reference ID (e.g., 'github:issue:123')

        Returns:
            The event if found, None otherwise
        """
        if not self._events_path.exists():
            return None

        # Search from end (most recent first)
        with open(self._events_path) as f:
            lines = f.readlines()

        for line in reversed(lines):
            try:
                entry = json.loads(line)
                if entry.get("external_ref") == external_ref:
                    return self._deserialize_event(entry)
            except json.JSONDecodeError:
                continue

        return None

    async def get_recent(self, limit: int = 100) -> list[ExternalEvent]:
        """Get recent events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events (newest first)
        """
        if not self._events_path.exists():
            return []

        events = []
        with open(self._events_path) as f:
            lines = f.readlines()

        for line in reversed(lines[-limit:]):
            try:
                entry = json.loads(line)
                events.append(self._deserialize_event(entry))
            except json.JSONDecodeError:
                continue

        return events

    async def wal_append(self, event: ExternalEvent, **metadata) -> None:
        """Append event to write-ahead log.

        Args:
            event: The event being processed
            **metadata: Additional metadata (status, goal_id, error)
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_id": event.id,
            "source": event.source.value,
            "event_type": event.event_type.value,
            **metadata,
        }

        with open(self._wal_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    async def recover_from_crash(self) -> list[str]:
        """Recover unprocessed events after crash.

        Called on startup to find events that were received but not processed.

        Returns:
            List of event IDs that need reprocessing
        """
        if not self._wal_path.exists():
            return []

        # Read WAL and find unprocessed events
        events_status: dict[str, str] = {}  # event_id → last status

        with open(self._wal_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    events_status[entry["event_id"]] = entry.get("status", "unknown")
                except json.JSONDecodeError:
                    continue

        # Find events that were received but not processed/failed
        unprocessed = [
            eid for eid, status in events_status.items()
            if status == "received"
        ]

        if unprocessed:
            logger.info(f"Crash recovery: {len(unprocessed)} unprocessed events")

        return unprocessed

    async def compact_wal(self, retention_days: int = 7) -> int:
        """Compact WAL by removing processed/old entries.

        Called periodically to prevent unbounded growth.

        Args:
            retention_days: Keep entries newer than this

        Returns:
            Number of entries removed
        """
        if not self._wal_path.exists():
            return 0

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        kept_lines = []
        removed = 0

        with open(self._wal_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_time = datetime.fromisoformat(entry["timestamp"])

                    # Keep recent entries or unprocessed ones
                    if entry_time > cutoff or entry.get("status") == "received":
                        kept_lines.append(line)
                    else:
                        removed += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    removed += 1

        # Rewrite WAL with kept lines
        with open(self._wal_path, "w") as f:
            for line in kept_lines:
                f.write(line)

        return removed

    def _serialize_event(self, event: ExternalEvent) -> dict:
        """Serialize event to JSON-compatible dict."""
        data = {
            "id": event.id,
            "source": event.source.value,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
            "external_url": event.external_url,
            "external_ref": event.external_ref,
        }
        # Don't store raw_payload by default (may be large/sensitive)
        return data

    def _deserialize_event(self, entry: dict) -> ExternalEvent:
        """Deserialize event from JSON dict."""
        return ExternalEvent(
            id=entry["id"],
            source=EventSource(entry["source"]),
            event_type=EventType(entry["event_type"]),
            timestamp=datetime.fromisoformat(entry["timestamp"]),
            data=entry.get("data", {}),
            external_url=entry.get("external_url"),
            external_ref=entry.get("external_ref"),
            raw_payload=None,  # Don't restore raw payload
        )
