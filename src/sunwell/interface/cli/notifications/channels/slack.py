"""Slack webhook notification channel.

Sends notifications to Slack via incoming webhooks.

Setup:
1. Create an Incoming Webhook in your Slack workspace
2. Copy the webhook URL
3. Configure in .sunwell/config.toml:
   [notifications.channels.slack]
   enabled = true
   webhook_url = "https://hooks.slack.com/services/..."
"""

import logging
from dataclasses import dataclass, field

from sunwell.interface.cli.notifications.channels.base import BaseChannel, ChannelConfig
from sunwell.interface.cli.notifications.system import NotificationType

logger = logging.getLogger(__name__)


@dataclass
class SlackChannel(BaseChannel):
    """Slack webhook notification channel.
    
    Sends notifications to Slack via incoming webhooks.
    
    Example:
        >>> channel = SlackChannel(
        ...     webhook_url="https://hooks.slack.com/services/...",
        ... )
        >>> await channel.send("Build Complete", "All tests passed", NotificationType.SUCCESS)
    """
    
    webhook_url: str = ""
    username: str = "Sunwell"
    icon_emoji: str = ":star:"
    
    def __post_init__(self) -> None:
        # Set channel name
        if self.config.name == "channel":
            object.__setattr__(
                self, "config",
                ChannelConfig(
                    enabled=self.config.enabled,
                    priority=self.config.priority,
                    types=self.config.types,
                    name="slack",
                )
            )
    
    def is_available(self) -> bool:
        """Check if Slack channel is available."""
        if not self.config.enabled:
            return False
        if not self.webhook_url:
            return False
        if not self.webhook_url.startswith("https://hooks.slack.com/"):
            logger.warning("Invalid Slack webhook URL")
            return False
        return True
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a notification to Slack.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data
            
        Returns:
            True if sent successfully
        """
        if not self.is_available():
            return False
        
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed, cannot send Slack notifications")
            return False
        
        # Build Slack message
        color = self._get_color(notification_type)
        emoji = self._get_emoji(notification_type)
        
        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} {title}",
                    "text": message,
                    "footer": "Sunwell",
                }
            ],
        }
        
        # Add context fields if available
        if context:
            fields = []
            if "file" in context:
                fields.append({
                    "title": "File",
                    "value": context["file"],
                    "short": True,
                })
            if "line" in context:
                fields.append({
                    "title": "Line",
                    "value": str(context["line"]),
                    "short": True,
                })
            if "session_id" in context:
                fields.append({
                    "title": "Session",
                    "value": context["session_id"],
                    "short": True,
                })
            if fields:
                payload["attachments"][0]["fields"] = fields
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(
                        f"Slack webhook returned {response.status_code}: {response.text}"
                    )
                    return False
        except Exception as e:
            logger.debug(f"Slack notification failed: {e}")
            return False
    
    def _get_color(self, notification_type: NotificationType) -> str:
        """Get Slack attachment color for notification type."""
        colors = {
            NotificationType.SUCCESS: "good",  # Green
            NotificationType.ERROR: "danger",  # Red
            NotificationType.WARNING: "warning",  # Yellow
            NotificationType.WAITING: "#9b59b6",  # Purple
            NotificationType.INFO: "#3498db",  # Blue
        }
        return colors.get(notification_type, "#808080")
    
    def _get_emoji(self, notification_type: NotificationType) -> str:
        """Get emoji for notification type."""
        emojis = {
            NotificationType.SUCCESS: "✦",
            NotificationType.ERROR: "✗",
            NotificationType.WARNING: "⚠",
            NotificationType.WAITING: "⊗",
            NotificationType.INFO: "ℹ",
        }
        return emojis.get(notification_type, "•")
    
    @classmethod
    def from_config(cls, data: dict) -> "SlackChannel":
        """Create SlackChannel from config dictionary.
        
        Args:
            data: Configuration dictionary with keys:
                - enabled: bool
                - webhook_url: str
                - priority: int (optional)
                - types: list[str] (optional)
                - username: str (optional)
                - icon_emoji: str (optional)
                
        Returns:
            SlackChannel instance
        """
        channel_config = ChannelConfig.from_dict(data, name="slack")
        
        return cls(
            config=channel_config,
            webhook_url=data.get("webhook_url", ""),
            username=data.get("username", "Sunwell"),
            icon_emoji=data.get("icon_emoji", ":star:"),
        )
