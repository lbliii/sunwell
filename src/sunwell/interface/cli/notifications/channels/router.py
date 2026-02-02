"""Multi-channel notification router.

Routes notifications to multiple channels with priority and fallback support.

Example:
    router = ChannelRouter()
    router.add_channel(DesktopChannel(config), priority=1)
    router.add_channel(SlackChannel(webhook_url), priority=2)
    
    # Sends to desktop first, falls back to Slack if desktop fails
    await router.send("Title", "Message", NotificationType.SUCCESS)
"""

import logging
from dataclasses import dataclass, field

from sunwell.interface.cli.notifications.channels.base import NotificationChannel
from sunwell.interface.cli.notifications.system import NotificationType

logger = logging.getLogger(__name__)


@dataclass
class ChannelRouter:
    """Multi-channel notification router.
    
    Routes notifications to channels based on priority and type filters.
    Supports fallback to lower-priority channels if higher-priority ones fail.
    
    Attributes:
        channels: List of (priority, channel) tuples
        fallback: Whether to try next channel if current fails
        parallel: Whether to send to all matching channels in parallel
    """
    
    fallback: bool = True
    parallel: bool = False
    _channels: list[tuple[int, NotificationChannel]] = field(
        default_factory=list, init=False
    )
    
    def add_channel(
        self,
        channel: NotificationChannel,
        priority: int | None = None,
    ) -> None:
        """Add a channel to the router.
        
        Args:
            channel: Notification channel to add
            priority: Priority override (uses channel config priority if None)
        """
        prio = priority if priority is not None else channel.config.priority
        self._channels.append((prio, channel))
        # Keep sorted by priority (lower = higher priority)
        self._channels.sort(key=lambda x: x[0])
    
    def remove_channel(self, channel: NotificationChannel) -> bool:
        """Remove a channel from the router.
        
        Args:
            channel: Channel to remove
            
        Returns:
            True if channel was found and removed
        """
        for i, (_, c) in enumerate(self._channels):
            if c is channel:
                self._channels.pop(i)
                return True
        return False
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a notification through configured channels.
        
        Routes to channels based on priority. If fallback is enabled,
        tries the next channel if the current one fails.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data
            
        Returns:
            True if at least one channel succeeded
        """
        if not self._channels:
            logger.debug("No channels configured for routing")
            return False
        
        # Get channels that accept this notification type
        matching_channels = [
            (prio, ch) for prio, ch in self._channels
            if ch.is_available() and ch.config.accepts_type(notification_type)
        ]
        
        if not matching_channels:
            logger.debug(f"No channels available for {notification_type.value}")
            return False
        
        if self.parallel:
            return await self._send_parallel(
                matching_channels, title, message, notification_type, context
            )
        else:
            return await self._send_sequential(
                matching_channels, title, message, notification_type, context
            )
    
    async def _send_sequential(
        self,
        channels: list[tuple[int, NotificationChannel]],
        title: str,
        message: str,
        notification_type: NotificationType,
        context: dict | None,
    ) -> bool:
        """Send to channels sequentially with optional fallback.
        
        Args:
            channels: List of (priority, channel) tuples
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data
            
        Returns:
            True if at least one channel succeeded
        """
        for priority, channel in channels:
            try:
                success = await channel.send(
                    title, message, notification_type, context=context
                )
                if success:
                    logger.debug(
                        f"Notification sent via {channel.config.name} (priority={priority})"
                    )
                    return True
                elif not self.fallback:
                    # Don't try other channels
                    return False
                else:
                    logger.debug(
                        f"Channel {channel.config.name} failed, trying next..."
                    )
            except Exception as e:
                logger.debug(f"Channel {channel.config.name} error: {e}")
                if not self.fallback:
                    return False
        
        logger.debug("All channels failed")
        return False
    
    async def _send_parallel(
        self,
        channels: list[tuple[int, NotificationChannel]],
        title: str,
        message: str,
        notification_type: NotificationType,
        context: dict | None,
    ) -> bool:
        """Send to all channels in parallel.
        
        Args:
            channels: List of (priority, channel) tuples
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data
            
        Returns:
            True if at least one channel succeeded
        """
        import asyncio
        
        tasks = [
            channel.send(title, message, notification_type, context=context)
            for _, channel in channels
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        successes = sum(
            1 for r in results
            if r is True  # Explicit True, not exceptions
        )
        
        if successes > 0:
            logger.debug(f"Notification sent to {successes}/{len(channels)} channels")
            return True
        
        logger.debug("All parallel channels failed")
        return False
    
    @property
    def channel_count(self) -> int:
        """Get number of configured channels."""
        return len(self._channels)
    
    @property
    def channels(self) -> list[NotificationChannel]:
        """Get list of channels (sorted by priority)."""
        return [ch for _, ch in self._channels]
    
    def get_channels_for_type(
        self,
        notification_type: NotificationType,
    ) -> list[NotificationChannel]:
        """Get channels that accept a specific notification type.
        
        Args:
            notification_type: Type to filter by
            
        Returns:
            List of matching channels
        """
        return [
            ch for _, ch in self._channels
            if ch.is_available() and ch.config.accepts_type(notification_type)
        ]
    
    @classmethod
    def from_config(cls, config: dict) -> "ChannelRouter":
        """Create a ChannelRouter from configuration.
        
        Args:
            config: Configuration dictionary with structure:
                {
                    "fallback": true,
                    "parallel": false,
                    "channels": {
                        "desktop": { "enabled": true, "priority": 1 },
                        "slack": { "enabled": true, "webhook_url": "...", "priority": 2 },
                        "webhook": { "enabled": false, "url": "..." },
                    }
                }
                
        Returns:
            Configured ChannelRouter instance
        """
        from sunwell.interface.cli.notifications.channels.desktop import DesktopChannel
        from sunwell.interface.cli.notifications.channels.slack import SlackChannel
        from sunwell.interface.cli.notifications.channels.webhook import WebhookChannel
        from sunwell.interface.cli.notifications.system import NotificationConfig
        
        router = cls(
            fallback=config.get("fallback", True),
            parallel=config.get("parallel", False),
        )
        
        channels_config = config.get("channels", {})
        
        # Desktop channel
        if "desktop" in channels_config:
            desktop_config = channels_config["desktop"]
            if desktop_config.get("enabled", True):
                channel = DesktopChannel(
                    config=ChannelConfig.from_dict(desktop_config, name="desktop"),
                    notification_config=NotificationConfig.from_dict(
                        desktop_config.get("notification", {})
                    ),
                )
                router.add_channel(channel)
        
        # Slack channel
        if "slack" in channels_config:
            slack_config = channels_config["slack"]
            if slack_config.get("enabled", False):
                channel = SlackChannel.from_config(slack_config)
                router.add_channel(channel)
        
        # Webhook channel
        if "webhook" in channels_config:
            webhook_config = channels_config["webhook"]
            if webhook_config.get("enabled", False):
                channel = WebhookChannel.from_config(webhook_config)
                router.add_channel(channel)
        
        return router


# Import ChannelConfig for from_config method
from sunwell.interface.cli.notifications.channels.base import ChannelConfig
