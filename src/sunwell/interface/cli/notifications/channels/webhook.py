"""Generic HTTP webhook notification channel.

Sends notifications to any HTTP endpoint via POST requests.

Setup:
    Configure in .sunwell/config.toml:
    [notifications.channels.webhook]
    enabled = true
    url = "https://example.com/webhook"
    method = "POST"
    headers = { "Authorization" = "Bearer xxx" }
"""

import logging
from dataclasses import dataclass, field

from sunwell.interface.cli.notifications.channels.base import BaseChannel, ChannelConfig
from sunwell.interface.cli.notifications.system import NotificationType

logger = logging.getLogger(__name__)


@dataclass
class WebhookChannel(BaseChannel):
    """Generic HTTP webhook notification channel.
    
    Sends notifications to any HTTP endpoint.
    
    Example:
        >>> channel = WebhookChannel(
        ...     url="https://example.com/webhook",
        ...     headers={"Authorization": "Bearer token"},
        ... )
        >>> await channel.send("Title", "Message", NotificationType.SUCCESS)
    """
    
    url: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 10.0
    
    def __post_init__(self) -> None:
        # Set channel name
        if self.config.name == "channel":
            object.__setattr__(
                self, "config",
                ChannelConfig(
                    enabled=self.config.enabled,
                    priority=self.config.priority,
                    types=self.config.types,
                    name="webhook",
                )
            )
    
    def is_available(self) -> bool:
        """Check if webhook channel is available."""
        if not self.config.enabled:
            return False
        if not self.url:
            return False
        if not self.url.startswith(("http://", "https://")):
            logger.warning(f"Invalid webhook URL: {self.url}")
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
        """Send a notification via HTTP webhook.
        
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
            logger.warning("httpx not installed, cannot send webhook notifications")
            return False
        
        # Build JSON payload
        payload = {
            "title": title,
            "message": message,
            "type": notification_type.value,
            "source": "sunwell",
        }
        
        # Add context if available
        if context:
            payload["context"] = context
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=self.method,
                    url=self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                
                # Accept 2xx status codes as success
                if 200 <= response.status_code < 300:
                    return True
                else:
                    logger.warning(
                        f"Webhook returned {response.status_code}: {response.text[:100]}"
                    )
                    return False
        except Exception as e:
            logger.debug(f"Webhook notification failed: {e}")
            return False
    
    @classmethod
    def from_config(cls, data: dict) -> "WebhookChannel":
        """Create WebhookChannel from config dictionary.
        
        Args:
            data: Configuration dictionary with keys:
                - enabled: bool
                - url: str
                - method: str (optional, default: POST)
                - headers: dict (optional)
                - priority: int (optional)
                - types: list[str] (optional)
                - timeout: float (optional, default: 10.0)
                
        Returns:
            WebhookChannel instance
        """
        channel_config = ChannelConfig.from_dict(data, name="webhook")
        
        return cls(
            config=channel_config,
            url=data.get("url", ""),
            method=data.get("method", "POST"),
            headers=data.get("headers", {}),
            timeout=data.get("timeout", 10.0),
        )
