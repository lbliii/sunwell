"""Smart notification batching.

Aggregates rapid-fire notifications into summaries to reduce notification fatigue.

Example:
    batcher = NotificationBatcher(notifier, window_ms=5000)
    await batcher.add(NotificationType.SUCCESS, "Task 1 done", "Details 1")
    await batcher.add(NotificationType.SUCCESS, "Task 2 done", "Details 2")
    # After 5 seconds, sends: "2 tasks completed"
"""

import asyncio
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sunwell.interface.cli.notifications.system import NotificationType

if TYPE_CHECKING:
    from sunwell.interface.cli.notifications.system import Notifier

logger = logging.getLogger(__name__)

# Default batch window in milliseconds
DEFAULT_BATCH_WINDOW_MS = 5000


@dataclass
class PendingNotification:
    """A notification waiting in the batch queue.
    
    Attributes:
        notification_type: Type of notification
        title: Notification title
        message: Notification body
        timestamp: When the notification was added
        context: Optional context data
    """
    
    notification_type: NotificationType
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict | None = None


@dataclass
class BatchedNotifier:
    """Notification batcher that aggregates rapid-fire notifications.
    
    Wraps a Notifier and batches notifications by type within a time window.
    When the window expires, sends a summary notification.
    
    Example:
        >>> notifier = Notifier(config)
        >>> batched = BatchedNotifier(notifier, window_ms=5000)
        >>> await batched.send_complete("Task 1")
        >>> await batched.send_complete("Task 2")
        >>> # After 5 seconds: "2 tasks completed"
    
    Attributes:
        notifier: The underlying notifier to send to
        window_ms: Batch window in milliseconds
        enabled: Whether batching is enabled
    """
    
    notifier: "Notifier"
    window_ms: int = DEFAULT_BATCH_WINDOW_MS
    enabled: bool = True
    
    _pending: dict[NotificationType, list[PendingNotification]] = field(
        default_factory=lambda: defaultdict(list), init=False
    )
    _flush_tasks: dict[NotificationType, asyncio.Task] = field(
        default_factory=dict, init=False
    )
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a notification (potentially batched).
        
        If batching is disabled, sends immediately.
        Otherwise, queues the notification and schedules a flush.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data
            
        Returns:
            True if queued/sent successfully
        """
        if not self.enabled:
            return await self.notifier.send(
                title, message, notification_type, context=context
            )
        
        # Add to pending batch
        pending = PendingNotification(
            notification_type=notification_type,
            title=title,
            message=message,
            context=context,
        )
        
        with self._lock:
            self._pending[notification_type].append(pending)
            
            # Schedule flush if not already scheduled
            if notification_type not in self._flush_tasks:
                self._flush_tasks[notification_type] = asyncio.create_task(
                    self._schedule_flush(notification_type)
                )
        
        return True
    
    async def send_complete(
        self,
        message: str,
        *,
        duration: float | None = None,
        tasks: int | None = None,
        context: dict | None = None,
    ) -> bool:
        """Send a completion notification (potentially batched).
        
        Args:
            message: Completion message
            duration: Duration in seconds
            tasks: Number of tasks completed
            context: Optional context data
            
        Returns:
            True if queued/sent
        """
        title = "✦ Sunwell Complete"
        body = message
        if duration is not None:
            body += f" ({duration:.1f}s)"
        if tasks is not None:
            body += f" • {tasks} tasks"
        
        return await self.send(title, body, NotificationType.SUCCESS, context=context)
    
    async def send_error(
        self,
        message: str,
        *,
        details: str = "",
        context: dict | None = None,
    ) -> bool:
        """Send an error notification (potentially batched).
        
        Args:
            message: Error message
            details: Additional details
            context: Optional context data
            
        Returns:
            True if queued/sent
        """
        title = "✗ Sunwell Error"
        body = message
        if details:
            body += f": {details}"
        
        return await self.send(title, body, NotificationType.ERROR, context=context)
    
    async def send_waiting(
        self,
        message: str = "Input needed",
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a waiting notification (NOT batched - always immediate).
        
        Waiting notifications should always be sent immediately
        since they require user action.
        
        Args:
            message: Waiting message
            context: Optional context data
            
        Returns:
            True if sent
        """
        # Waiting notifications bypass batching - they need immediate attention
        return await self.notifier.send_waiting(message)
    
    async def flush(self, notification_type: NotificationType | None = None) -> int:
        """Flush pending notifications immediately.
        
        Args:
            notification_type: Type to flush (None = all types)
            
        Returns:
            Number of notifications flushed
        """
        if notification_type is not None:
            return await self._flush_type(notification_type)
        
        # Flush all types
        total = 0
        with self._lock:
            types = list(self._pending.keys())
        
        for ntype in types:
            total += await self._flush_type(ntype)
        
        return total
    
    async def flush_all(self) -> int:
        """Flush all pending notifications immediately.
        
        Returns:
            Number of notifications flushed
        """
        return await self.flush(None)
    
    async def _schedule_flush(self, notification_type: NotificationType) -> None:
        """Schedule a flush after the batch window expires.
        
        Args:
            notification_type: Type to flush
        """
        try:
            await asyncio.sleep(self.window_ms / 1000.0)
            await self._flush_type(notification_type)
        except asyncio.CancelledError:
            pass
        finally:
            with self._lock:
                self._flush_tasks.pop(notification_type, None)
    
    async def _flush_type(self, notification_type: NotificationType) -> int:
        """Flush pending notifications of a specific type.
        
        Args:
            notification_type: Type to flush
            
        Returns:
            Number of notifications flushed
        """
        with self._lock:
            pending = self._pending.pop(notification_type, [])
            # Cancel scheduled flush if exists
            task = self._flush_tasks.pop(notification_type, None)
            if task and not task.done():
                task.cancel()
        
        if not pending:
            return 0
        
        # Create summary notification
        count = len(pending)
        
        if count == 1:
            # Single notification - send as-is
            n = pending[0]
            await self.notifier.send(
                n.title, n.message, n.notification_type, context=n.context
            )
        else:
            # Multiple notifications - send summary
            title, message = self._create_summary(notification_type, pending)
            await self.notifier.send(title, message, notification_type)
        
        return count
    
    def _create_summary(
        self,
        notification_type: NotificationType,
        pending: list[PendingNotification],
    ) -> tuple[str, str]:
        """Create a summary notification from multiple pending notifications.
        
        Args:
            notification_type: Type of notifications
            pending: List of pending notifications
            
        Returns:
            Tuple of (title, message)
        """
        count = len(pending)
        
        if notification_type == NotificationType.SUCCESS:
            title = "✦ Sunwell Complete"
            message = f"{count} tasks completed"
        elif notification_type == NotificationType.ERROR:
            title = "✗ Sunwell Errors"
            message = f"{count} errors occurred"
            # Include first error for context
            if pending:
                first_msg = pending[0].message
                if len(first_msg) > 50:
                    first_msg = first_msg[:47] + "..."
                message += f" (first: {first_msg})"
        elif notification_type == NotificationType.WARNING:
            title = "⚠ Sunwell Warnings"
            message = f"{count} warnings"
        elif notification_type == NotificationType.INFO:
            title = "✦ Sunwell"
            message = f"{count} notifications"
        else:
            title = "✦ Sunwell"
            message = f"{count} notifications"
        
        return title, message
    
    @property
    def pending_count(self) -> int:
        """Get total number of pending notifications."""
        with self._lock:
            return sum(len(p) for p in self._pending.values())
    
    def pending_by_type(self) -> dict[str, int]:
        """Get count of pending notifications by type."""
        with self._lock:
            return {
                ntype.value: len(pending)
                for ntype, pending in self._pending.items()
            }


def create_batched_notifier(
    notifier: "Notifier",
    *,
    enabled: bool = True,
    window_ms: int = DEFAULT_BATCH_WINDOW_MS,
) -> BatchedNotifier:
    """Create a batched notifier wrapper.
    
    Args:
        notifier: The underlying notifier
        enabled: Whether batching is enabled
        window_ms: Batch window in milliseconds
        
    Returns:
        BatchedNotifier instance
    """
    return BatchedNotifier(
        notifier=notifier,
        enabled=enabled,
        window_ms=window_ms,
    )
