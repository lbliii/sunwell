"""Notification history storage.

Stores all notifications for recall and debugging using append-only JSONL.

Storage location: .sunwell/notifications.jsonl

Example usage:
    store = NotificationStore(workspace)
    await store.record(notification)
    history = store.get_recent(limit=10)
"""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from sunwell.interface.cli.notifications.system import NotificationType

logger = logging.getLogger(__name__)

# Storage file name
HISTORY_FILENAME = "notifications.jsonl"

# Maximum history entries to keep (for pruning)
MAX_HISTORY_ENTRIES = 1000

# Retention period
RETENTION_DAYS = 30


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    """A recorded notification.
    
    Attributes:
        id: Unique identifier
        timestamp: When the notification was created
        type: Notification type (info, success, warning, error, waiting)
        title: Notification title
        message: Notification body
        delivered: Whether the notification was successfully delivered
        channel: Channel used for delivery (desktop, slack, webhook, etc.)
        context: Optional context data (file path, session ID, etc.)
    """
    
    id: str
    timestamp: str
    type: str
    title: str
    message: str
    delivered: bool = True
    channel: str = "desktop"
    context: dict | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if data["context"] is None:
            del data["context"]
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "NotificationRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            type=data["type"],
            title=data["title"],
            message=data["message"],
            delivered=data.get("delivered", True),
            channel=data.get("channel", "desktop"),
            context=data.get("context"),
        )
    
    @classmethod
    def create(
        cls,
        notification_type: NotificationType,
        title: str,
        message: str,
        *,
        delivered: bool = True,
        channel: str = "desktop",
        context: dict | None = None,
    ) -> "NotificationRecord":
        """Create a new notification record.
        
        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification body
            delivered: Whether delivery succeeded
            channel: Delivery channel
            context: Optional context data
            
        Returns:
            NotificationRecord instance
        """
        import uuid
        
        return cls(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            type=notification_type.value,
            title=title,
            message=message,
            delivered=delivered,
            channel=channel,
            context=context,
        )


@dataclass
class NotificationStore:
    """Persistent notification history store.
    
    Uses append-only JSONL for storage. Thread-safe for concurrent access.
    
    Example:
        >>> store = NotificationStore(Path("/workspace"))
        >>> record = NotificationRecord.create(
        ...     NotificationType.SUCCESS, "Build done", "Completed in 5s"
        ... )
        >>> store.append(record)
        >>> recent = store.get_recent(limit=5)
    """
    
    workspace: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    @property
    def storage_path(self) -> Path:
        """Path to the JSONL storage file."""
        return self.workspace / ".sunwell" / HISTORY_FILENAME
    
    def append(self, record: NotificationRecord) -> None:
        """Append a notification record to history.
        
        Args:
            record: Notification record to store
        """
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
    
    def get_recent(self, limit: int = 10) -> list[NotificationRecord]:
        """Get most recent notifications.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of notification records (newest first)
        """
        records = list(self._read_all())
        records.reverse()  # Newest first
        return records[:limit]
    
    def get_today(self) -> list[NotificationRecord]:
        """Get all notifications from today.
        
        Returns:
            List of today's notifications (newest first)
        """
        today = datetime.now().date()
        records = [
            r for r in self._read_all()
            if datetime.fromisoformat(r.timestamp).date() == today
        ]
        records.reverse()
        return records
    
    def get_by_type(
        self,
        notification_type: NotificationType,
        limit: int = 50,
    ) -> list[NotificationRecord]:
        """Get notifications filtered by type.
        
        Args:
            notification_type: Type to filter by
            limit: Maximum number of records
            
        Returns:
            Filtered notifications (newest first)
        """
        records = [
            r for r in self._read_all()
            if r.type == notification_type.value
        ]
        records.reverse()
        return records[:limit]
    
    def get_since(self, since: datetime) -> list[NotificationRecord]:
        """Get notifications since a given time.
        
        Args:
            since: Start time
            
        Returns:
            Notifications since the given time (newest first)
        """
        records = [
            r for r in self._read_all()
            if datetime.fromisoformat(r.timestamp) >= since
        ]
        records.reverse()
        return records
    
    def get_undelivered(self) -> list[NotificationRecord]:
        """Get notifications that failed to deliver.
        
        Returns:
            Undelivered notifications
        """
        return [r for r in self._read_all() if not r.delivered]
    
    def count(self) -> int:
        """Count total notifications in history.
        
        Returns:
            Number of notification records
        """
        return sum(1 for _ in self._read_all())
    
    def prune(self, *, keep_recent: int = MAX_HISTORY_ENTRIES) -> int:
        """Prune old notifications to limit storage.
        
        Keeps the most recent entries and removes older ones.
        Also removes entries older than RETENTION_DAYS.
        
        Args:
            keep_recent: Number of recent entries to keep
            
        Returns:
            Number of entries removed
        """
        with self._lock:
            if not self.storage_path.exists():
                return 0
            
            records = list(self._read_all_unsafe())
            original_count = len(records)
            
            # Filter by retention period
            cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
            records = [
                r for r in records
                if datetime.fromisoformat(r.timestamp) >= cutoff
            ]
            
            # Keep only recent entries
            if len(records) > keep_recent:
                records = records[-keep_recent:]
            
            # Rewrite file
            with open(self.storage_path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record.to_dict()) + "\n")
            
            return original_count - len(records)
    
    def clear(self) -> None:
        """Clear all notification history."""
        with self._lock:
            if self.storage_path.exists():
                self.storage_path.unlink()
    
    def _read_all(self) -> Iterator[NotificationRecord]:
        """Read all records from storage (thread-safe).
        
        Yields:
            Notification records in chronological order
        """
        with self._lock:
            yield from self._read_all_unsafe()
    
    def _read_all_unsafe(self) -> Iterator[NotificationRecord]:
        """Read all records without locking.
        
        Yields:
            Notification records in chronological order
        """
        if not self.storage_path.exists():
            return
        
        with open(self.storage_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    yield NotificationRecord.from_dict(data)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"Skipping malformed record: {e}")


def get_notification_store(workspace: Path | None = None) -> NotificationStore:
    """Get a notification store for the given workspace.
    
    Args:
        workspace: Workspace root (uses cwd if None)
        
    Returns:
        NotificationStore instance
    """
    if workspace is None:
        workspace = Path.cwd()
    return NotificationStore(workspace=workspace)
