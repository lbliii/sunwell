"""Multi-channel notification system.

Provides pluggable notification channels with routing and fallback support.

Channels:
- DesktopChannel: Native desktop notifications (macOS, Linux, Windows)
- SlackChannel: Slack webhook notifications
- WebhookChannel: Generic HTTP webhook notifications
- NtfyChannel: ntfy.sh push notifications
- PushoverChannel: Pushover API notifications

Usage:
    from sunwell.interface.cli.notifications.channels import (
        ChannelRouter,
        DesktopChannel,
        SlackChannel,
    )
    
    router = ChannelRouter()
    router.add_channel(DesktopChannel(config), priority=1)
    router.add_channel(SlackChannel(webhook_url), priority=2)
    
    await router.send("Title", "Message", NotificationType.SUCCESS)
"""

from sunwell.interface.cli.notifications.channels.base import (
    ChannelConfig,
    NotificationChannel,
)
from sunwell.interface.cli.notifications.channels.desktop import DesktopChannel
from sunwell.interface.cli.notifications.channels.router import ChannelRouter
from sunwell.interface.cli.notifications.channels.slack import SlackChannel
from sunwell.interface.cli.notifications.channels.webhook import WebhookChannel

__all__ = [
    # Protocol and base
    "NotificationChannel",
    "ChannelConfig",
    # Channels
    "DesktopChannel",
    "SlackChannel",
    "WebhookChannel",
    # Router
    "ChannelRouter",
]
