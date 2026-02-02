"""Tests for notification batching."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.interface.cli.notifications.batcher import (
    BatchedNotifier,
    PendingNotification,
    create_batched_notifier,
)
from sunwell.interface.cli.notifications.system import (
    NotificationConfig,
    NotificationType,
    Notifier,
)


class TestPendingNotification:
    """Test PendingNotification dataclass."""

    def test_create_pending(self) -> None:
        """Create a pending notification."""
        pending = PendingNotification(
            notification_type=NotificationType.SUCCESS,
            title="Test",
            message="Test message",
        )

        assert pending.notification_type == NotificationType.SUCCESS
        assert pending.title == "Test"
        assert pending.context is None

    def test_pending_with_context(self) -> None:
        """Pending notification with context."""
        pending = PendingNotification(
            notification_type=NotificationType.ERROR,
            title="Error",
            message="Failed",
            context={"file": "test.py"},
        )

        assert pending.context["file"] == "test.py"


class TestBatchedNotifier:
    """Test BatchedNotifier batching behavior."""

    @pytest.fixture
    def mock_notifier(self) -> Notifier:
        """Create a mock notifier."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        notifier.send = AsyncMock(return_value=True)
        return notifier

    def test_create_batcher(self, mock_notifier: Notifier) -> None:
        """Create batched notifier."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=1000,
            enabled=True,
        )

        assert batcher.window_ms == 1000
        assert batcher.enabled is True

    def test_disabled_passthrough(self, mock_notifier: Notifier) -> None:
        """Disabled batcher passes through immediately."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=1000,
            enabled=False,
        )

        assert batcher.enabled is False

    @pytest.mark.asyncio
    async def test_send_waiting_bypasses_batch(self, mock_notifier: Notifier) -> None:
        """send_waiting should bypass batching."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=5000,  # Long window
            enabled=True,
        )

        # Mock the underlying notifier's send_waiting
        mock_notifier.send_waiting = AsyncMock(return_value=True)

        # Should send immediately, not batch
        await batcher.send_waiting("Need input")

        mock_notifier.send_waiting.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_clears_pending(self, mock_notifier: Notifier) -> None:
        """Flush sends all pending notifications."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=10000,  # Long window so no auto-flush
            enabled=True,
        )

        # Add some pending notifications
        batcher._pending[NotificationType.SUCCESS].append(
            PendingNotification(
                notification_type=NotificationType.SUCCESS,
                title="Test 1",
                message="Message 1",
            )
        )
        batcher._pending[NotificationType.SUCCESS].append(
            PendingNotification(
                notification_type=NotificationType.SUCCESS,
                title="Test 2",
                message="Message 2",
            )
        )

        await batcher.flush()

        # All pending should be cleared
        assert len(batcher._pending[NotificationType.SUCCESS]) == 0
        # Notifier send should have been called with summary
        mock_notifier.send.assert_called()

    @pytest.mark.asyncio
    async def test_summary_format_single(self, mock_notifier: Notifier) -> None:
        """Single notification doesn't get summary prefix."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=10000,
            enabled=True,
        )

        batcher._pending[NotificationType.ERROR].append(
            PendingNotification(
                notification_type=NotificationType.ERROR,
                title="Single Error",
                message="Just one error",
            )
        )

        await batcher.flush()

        # Should be called with original message, not summary
        call_args = mock_notifier.send.call_args
        assert call_args is not None
        # Check message doesn't have "2 notifications" etc.
        title, message = call_args[0][:2]
        assert "notifications" not in message.lower()

    @pytest.mark.asyncio
    async def test_summary_format_multiple(self, mock_notifier: Notifier) -> None:
        """Multiple notifications get summary."""
        batcher = BatchedNotifier(
            notifier=mock_notifier,
            window_ms=10000,
            enabled=True,
        )

        for i in range(3):
            batcher._pending[NotificationType.SUCCESS].append(
                PendingNotification(
                    notification_type=NotificationType.SUCCESS,
                    title=f"Success {i}",
                    message=f"Message {i}",
                )
            )

        await batcher.flush()

        # Should be called with summary
        call_args = mock_notifier.send.call_args
        assert call_args is not None
        title, message = call_args[0][:2]
        # Summary should mention count
        assert "3" in message or "3" in title


class TestCreateBatchedNotifier:
    """Test factory function."""

    def test_create_with_defaults(self, tmp_path: Path) -> None:
        """Create batched notifier with defaults."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)

        batcher = create_batched_notifier(notifier)

        assert isinstance(batcher, BatchedNotifier)
        assert batcher.enabled is True

    def test_create_disabled(self, tmp_path: Path) -> None:
        """Create disabled batched notifier."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)

        batcher = create_batched_notifier(notifier, enabled=False)

        assert batcher.enabled is False

    def test_create_custom_window(self, tmp_path: Path) -> None:
        """Create batched notifier with custom window."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)

        batcher = create_batched_notifier(notifier, window_ms=2000)

        assert batcher.window_ms == 2000
