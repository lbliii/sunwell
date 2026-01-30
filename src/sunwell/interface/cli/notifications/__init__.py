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
"""

from sunwell.interface.cli.notifications.config import (
    create_example_config_file,
    get_config_section,
    load_notification_config,
)
from sunwell.interface.cli.notifications.system import (
    Notifier,
    NotificationConfig,
    NotificationType,
    notify,
    notify_complete,
    notify_error,
    notify_waiting,
)

__all__ = [
    "Notifier",
    "NotificationConfig",
    "NotificationType",
    "notify",
    "notify_complete",
    "notify_error",
    "notify_waiting",
    "load_notification_config",
    "create_example_config_file",
    "get_config_section",
]
