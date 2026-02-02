"""Base notification channel protocol and configuration.

Defines the interface that all notification channels must implement.
"""

from dataclasses import dataclass, field
from typing import Protocol

from sunwell.interface.cli.notifications.system import NotificationType


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Configuration for a notification channel.
    
    Attributes:
        enabled: Whether the channel is enabled
        priority: Priority for routing (lower = higher priority)
        types: Notification types to route to this channel (None = all)
        name: Human-readable channel name
    """
    
    enabled: bool = True
    priority: int = 1
    types: tuple[NotificationType, ...] | None = None
    name: str = "channel"
    
    def accepts_type(self, notification_type: NotificationType) -> bool:
        """Check if this channel accepts the given notification type.
        
        Args:
            notification_type: Type to check
            
        Returns:
            True if the channel accepts this type
        """
        if self.types is None:
            return True
        return notification_type in self.types
    
    @classmethod
    def from_dict(cls, data: dict, name: str = "channel") -> "ChannelConfig":
        """Create config from dictionary.
        
        Args:
            data: Configuration dictionary
            name: Channel name
            
        Returns:
            ChannelConfig instance
        """
        types = None
        if "types" in data:
            type_strs = data["types"]
            types = tuple(
                NotificationType(t) for t in type_strs
                if t in [nt.value for nt in NotificationType]
            )
        
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 1),
            types=types,
            name=name,
        )


class NotificationChannel(Protocol):
    """Protocol for notification channels.
    
    All notification channels must implement this interface.
    
    Example:
        class MyChannel:
            config: ChannelConfig
            
            def is_available(self) -> bool:
                return True
            
            async def send(
                self,
                title: str,
                message: str,
                notification_type: NotificationType,
            ) -> bool:
                # Send notification
                return True
    """
    
    config: ChannelConfig
    
    def is_available(self) -> bool:
        """Check if the channel is available for sending.
        
        Returns:
            True if the channel can send notifications
        """
        ...
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a notification through this channel.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data (file path, session ID, etc.)
            
        Returns:
            True if the notification was sent successfully
        """
        ...


@dataclass
class BaseChannel:
    """Base class for notification channels.
    
    Provides common functionality for all channels.
    """
    
    config: ChannelConfig = field(default_factory=ChannelConfig)
    
    def is_available(self) -> bool:
        """Check if the channel is available.
        
        Override in subclasses to check for specific requirements
        (e.g., terminal-notifier installed, webhook URL configured).
        
        Returns:
            True if enabled and available
        """
        return self.config.enabled
    
    def accepts(self, notification_type: NotificationType) -> bool:
        """Check if this channel accepts the given notification type.
        
        Args:
            notification_type: Type to check
            
        Returns:
            True if the channel is available and accepts this type
        """
        return self.is_available() and self.config.accepts_type(notification_type)
