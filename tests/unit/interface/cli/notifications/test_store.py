"""Tests for notification history store."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sunwell.interface.cli.notifications.store import (
    NotificationRecord,
    NotificationStore,
    get_notification_store,
)
from sunwell.interface.cli.notifications.system import NotificationType


class TestNotificationRecord:
    """Test NotificationRecord dataclass."""

    def test_create_record_via_factory(self) -> None:
        """Create a notification record using the factory method."""
        record = NotificationRecord.create(
            notification_type=NotificationType.SUCCESS,
            title="Test Title",
            message="Test message",
            delivered=True,
            channel="desktop",
        )

        assert len(record.id) == 8  # UUID shortened
        assert record.type == "success"  # Stored as string
        assert record.delivered is True

    def test_create_record_direct(self) -> None:
        """Create record directly with all string fields."""
        record = NotificationRecord(
            id="test-123",
            timestamp="2024-01-15T10:30:00+00:00",
            type="success",
            title="Test Title",
            message="Test message",
            delivered=True,
            channel="desktop",
        )

        assert record.id == "test-123"
        assert record.type == "success"
        assert record.delivered is True

    def test_to_dict(self) -> None:
        """Serialize record to dict."""
        record = NotificationRecord(
            id="test-456",
            timestamp="2024-01-15T10:30:00+00:00",
            type="error",
            title="Error",
            message="Something failed",
            delivered=False,
            channel="slack",
            context={"file": "test.py", "line": 42},
        )

        data = record.to_dict()

        assert data["id"] == "test-456"
        assert data["type"] == "error"
        assert data["delivered"] is False
        assert data["context"]["file"] == "test.py"

    def test_from_dict(self) -> None:
        """Deserialize record from dict."""
        data = {
            "id": "test-789",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "type": "warning",
            "title": "Warning",
            "message": "Be careful",
            "delivered": True,
            "channel": "desktop",
        }

        record = NotificationRecord.from_dict(data)

        assert record.id == "test-789"
        assert record.type == "warning"  # Stored as string
        assert record.title == "Warning"

    def test_roundtrip(self) -> None:
        """Round-trip serialization."""
        original = NotificationRecord.create(
            notification_type=NotificationType.INFO,
            title="Info",
            message="Information",
            delivered=True,
            channel="webhook",
            context={"key": "value"},
        )

        data = original.to_dict()
        restored = NotificationRecord.from_dict(data)

        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.context == original.context


class TestNotificationStore:
    """Test NotificationStore persistence."""

    def test_create_store(self, tmp_path: Path) -> None:
        """Create store initializes correctly."""
        store = NotificationStore(workspace=tmp_path)

        assert store.workspace == tmp_path
        # Storage path exists after first write
        assert store.storage_path == tmp_path / ".sunwell" / "notifications.jsonl"

    def test_append_and_count(self, tmp_path: Path) -> None:
        """Append records and count them."""
        store = NotificationStore(workspace=tmp_path)

        record1 = NotificationRecord.create(
            notification_type=NotificationType.SUCCESS,
            title="Test 1",
            message="Message 1",
            delivered=True,
            channel="desktop",
        )
        record2 = NotificationRecord.create(
            notification_type=NotificationType.ERROR,
            title="Test 2",
            message="Message 2",
            delivered=False,
            channel="slack",
        )

        store.append(record1)
        store.append(record2)

        assert store.count() == 2

    def test_get_recent(self, tmp_path: Path) -> None:
        """Get recent notifications in reverse order."""
        store = NotificationStore(workspace=tmp_path)
        base_time = datetime.now()

        for i in range(5):
            # Create with incrementing timestamps
            record = NotificationRecord(
                id=str(i),
                timestamp=(base_time + timedelta(seconds=i)).isoformat(),
                type="info",
                title=f"Test {i}",
                message=f"Message {i}",
                delivered=True,
                channel="desktop",
            )
            store.append(record)

        recent = store.get_recent(limit=3)

        assert len(recent) == 3
        # Most recent first
        assert recent[0].id == "4"
        assert recent[1].id == "3"
        assert recent[2].id == "2"

    def test_get_by_type(self, tmp_path: Path) -> None:
        """Filter notifications by type."""
        store = NotificationStore(workspace=tmp_path)

        store.append(NotificationRecord.create(
            notification_type=NotificationType.SUCCESS,
            title="Success",
            message="Done",
        ))
        store.append(NotificationRecord.create(
            notification_type=NotificationType.ERROR,
            title="Error 1",
            message="Failed",
        ))
        store.append(NotificationRecord.create(
            notification_type=NotificationType.ERROR,
            title="Error 2",
            message="Failed again",
        ))

        errors = store.get_by_type(NotificationType.ERROR)

        assert len(errors) == 2
        assert all(r.type == "error" for r in errors)

    def test_get_undelivered(self, tmp_path: Path) -> None:
        """Get undelivered notifications."""
        store = NotificationStore(workspace=tmp_path)

        store.append(NotificationRecord.create(
            notification_type=NotificationType.INFO,
            title="Delivered",
            message="OK",
            delivered=True,
        ))
        store.append(NotificationRecord.create(
            notification_type=NotificationType.INFO,
            title="Not Delivered",
            message="Queued",
            delivered=False,
        ))

        undelivered = store.get_undelivered()

        assert len(undelivered) == 1
        assert undelivered[0].title == "Not Delivered"

    def test_get_since(self, tmp_path: Path) -> None:
        """Get notifications since a timestamp."""
        store = NotificationStore(workspace=tmp_path)
        now = datetime.now()

        store.append(NotificationRecord(
            id="old",
            timestamp=(now - timedelta(hours=2)).isoformat(),
            type="info",
            title="Old",
            message="Old message",
        ))
        store.append(NotificationRecord(
            id="new",
            timestamp=(now - timedelta(minutes=30)).isoformat(),
            type="info",
            title="New",
            message="New message",
        ))

        since = store.get_since(now - timedelta(hours=1))

        assert len(since) == 1
        assert since[0].id == "new"

    def test_clear(self, tmp_path: Path) -> None:
        """Clear all notifications."""
        store = NotificationStore(workspace=tmp_path)

        for i in range(3):
            store.append(NotificationRecord.create(
                notification_type=NotificationType.INFO,
                title=f"Test {i}",
                message=f"Message {i}",
            ))

        assert store.count() == 3

        store.clear()

        assert store.count() == 0

    def test_persistence(self, tmp_path: Path) -> None:
        """Data persists across store instances."""
        store1 = NotificationStore(workspace=tmp_path)
        store1.append(NotificationRecord.create(
            notification_type=NotificationType.SUCCESS,
            title="Persistent",
            message="Should survive",
        ))

        # Create new store instance
        store2 = NotificationStore(workspace=tmp_path)

        assert store2.count() == 1
        records = store2.get_recent(limit=10)
        assert records[0].title == "Persistent"


class TestGetNotificationStore:
    """Test convenience function."""

    def test_get_store(self, tmp_path: Path) -> None:
        """Get store for workspace."""
        store = get_notification_store(tmp_path)

        assert isinstance(store, NotificationStore)
        assert store.workspace == tmp_path
