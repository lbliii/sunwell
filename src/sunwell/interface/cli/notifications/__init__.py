"""Cross-platform notification system for Sunwell.

Provides system notifications when:
- Tasks complete (success or failure)
- User input is needed
- Session ends

Supports:
- macOS: terminal-notifier, osascript
- Linux: notify-send
- Windows: powershell toast
- Fallback: terminal bell

Features:
- Notification history with `sunwell notifications`
- Focus mode awareness (macOS)
- Smart batching for rapid-fire notifications
- Multi-channel routing (desktop, Slack, webhooks)
- Deep links to VS Code / terminal

Usage:
    from sunwell.interface.cli.notifications import (
        Notifier,
        notify,
        NotificationConfig,
    )
    
    # Simple notification
    notify("Task complete", "Auth system implemented")
    
    # With config
    notifier = Notifier(config)
    await notifier.send_complete("Build finished", duration=12.5)
    
    # With batching
    batched = BatchedNotifier(notifier, window_ms=5000)
    await batched.send_complete("Task 1")  # Queued
    await batched.send_complete("Task 2")  # Queued
    # After 5 seconds: "2 tasks completed"
    
    # With deep links
    await notifier.send(
        "Error in file",
        "Syntax error on line 42",
        NotificationType.ERROR,
        context={"file": "/path/to/file.py", "line": 42},
    )  # Click opens VS Code at the file:line
    
    # Multi-channel routing
    router = ChannelRouter()
    router.add_channel(DesktopChannel(), priority=1)
    router.add_channel(SlackChannel(webhook_url="..."), priority=2)
    await router.send("Title", "Message", NotificationType.SUCCESS)
    
    # Access history
    store = get_notification_store(workspace)
    recent = store.get_recent(limit=10)
"""

from sunwell.interface.cli.notifications.batcher import (
    BatchedNotifier,
    PendingNotification,
    create_batched_notifier,
)
from sunwell.interface.cli.notifications.channels import (
    ChannelConfig,
    ChannelRouter,
    DesktopChannel,
    NotificationChannel,
    SlackChannel,
    WebhookChannel,
)
from sunwell.interface.cli.notifications.config import (
    create_example_config_file,
    create_notifier,
    get_config_section,
    load_notification_config,
)
from sunwell.interface.cli.notifications.deeplinks import (
    create_deep_link,
    create_file_context,
    create_session_context,
)
from sunwell.interface.cli.notifications.store import (
    NotificationRecord,
    NotificationStore,
    get_notification_store,
)
from sunwell.interface.cli.notifications.system import (
    FocusModeBehavior,
    Notifier,
    NotificationConfig,
    NotificationType,
    detect_focus_mode,
    notify,
    notify_complete,
    notify_error,
    notify_waiting,
)

__all__ = [
    # Core
    "Notifier",
    "NotificationConfig",
    "NotificationType",
    "FocusModeBehavior",
    "detect_focus_mode",
    # Batching
    "BatchedNotifier",
    "PendingNotification",
    "create_batched_notifier",
    # Channels
    "NotificationChannel",
    "ChannelConfig",
    "ChannelRouter",
    "DesktopChannel",
    "SlackChannel",
    "WebhookChannel",
    # Deep links
    "create_deep_link",
    "create_file_context",
    "create_session_context",
    # Convenience functions
    "notify",
    "notify_complete",
    "notify_error",
    "notify_waiting",
    # Config
    "load_notification_config",
    "create_example_config_file",
    "get_config_section",
    "create_notifier",
    # History
    "NotificationStore",
    "NotificationRecord",
    "get_notification_store",
]
