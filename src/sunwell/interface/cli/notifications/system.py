"""Cross-platform notification dispatch.

Detects the current platform and uses the appropriate
notification mechanism:
- macOS: terminal-notifier (if installed), osascript fallback
- Linux: notify-send
- Windows: PowerShell toast notifications
- Fallback: Terminal bell (\a)
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    WAITING = "waiting"  # User input needed


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    """Configuration for notifications.
    
    Attributes:
        enabled: Whether notifications are enabled
        desktop: Show desktop notifications
        sound: Play sound with notification
        on_complete: Custom command for completion
        on_error: Custom command for errors
        on_waiting: Custom command for waiting
    """
    
    enabled: bool = True
    desktop: bool = True
    sound: bool = True
    on_complete: str | None = None
    on_error: str | None = None
    on_waiting: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "NotificationConfig":
        """Create config from dictionary.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            NotificationConfig instance
        """
        return cls(
            enabled=data.get("enabled", True),
            desktop=data.get("desktop", True),
            sound=data.get("sound", True),
            on_complete=data.get("on_complete"),
            on_error=data.get("on_error"),
            on_waiting=data.get("on_waiting"),
        )


class Platform(Enum):
    """Supported platforms."""
    
    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


def detect_platform() -> Platform:
    """Detect the current platform.
    
    Returns:
        Platform enum value
    """
    system = platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    elif system == "linux":
        return Platform.LINUX
    elif system == "windows":
        return Platform.WINDOWS
    return Platform.UNKNOWN


def has_command(cmd: str) -> bool:
    """Check if a command is available.
    
    Args:
        cmd: Command name
        
    Returns:
        True if command exists
    """
    return shutil.which(cmd) is not None


@dataclass
class Notifier:
    """Cross-platform notification dispatcher.
    
    Automatically detects the platform and uses the
    appropriate notification mechanism.
    
    Example:
        >>> notifier = Notifier()
        >>> await notifier.send("Hello", "World")
        >>> await notifier.send_complete("Build done", duration=12.5)
    """
    
    config: NotificationConfig = field(default_factory=NotificationConfig)
    _platform: Platform = field(default=None, init=False)
    _notifier_fn: Callable | None = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        self._platform = detect_platform()
        self._notifier_fn = self._select_notifier()
    
    def _select_notifier(self) -> Callable | None:
        """Select the appropriate notifier for this platform.
        
        Returns:
            Notification function or None if not available
        """
        if not self.config.enabled or not self.config.desktop:
            return None
        
        if self._platform == Platform.MACOS:
            if has_command("terminal-notifier"):
                return self._notify_terminal_notifier
            return self._notify_osascript
        
        elif self._platform == Platform.LINUX:
            if has_command("notify-send"):
                return self._notify_linux
            return None
        
        elif self._platform == Platform.WINDOWS:
            return self._notify_windows
        
        return None
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
    ) -> bool:
        """Send a notification.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            
        Returns:
            True if notification was sent
        """
        if not self.config.enabled:
            return False
        
        # Check for custom command
        custom_cmd = self._get_custom_command(notification_type)
        if custom_cmd:
            return await self._run_custom(custom_cmd, title, message)
        
        # Use platform notifier
        if self._notifier_fn:
            try:
                await self._notifier_fn(title, message, notification_type)
                return True
            except Exception as e:
                logger.debug(f"Notification failed: {e}")
        
        # Fallback to terminal bell
        if self.config.sound:
            self._bell()
        
        return False
    
    async def send_complete(
        self,
        message: str,
        *,
        duration: float | None = None,
        tasks: int | None = None,
    ) -> bool:
        """Send a completion notification.
        
        Args:
            message: Completion message
            duration: Duration in seconds
            tasks: Number of tasks completed
            
        Returns:
            True if sent
        """
        title = "✦ Sunwell Complete"
        body = message
        if duration is not None:
            body += f" ({duration:.1f}s)"
        if tasks is not None:
            body += f" • {tasks} tasks"
        
        return await self.send(title, body, NotificationType.SUCCESS)
    
    async def send_error(self, message: str, *, details: str = "") -> bool:
        """Send an error notification.
        
        Args:
            message: Error message
            details: Additional details
            
        Returns:
            True if sent
        """
        title = "✗ Sunwell Error"
        body = message
        if details:
            body += f": {details}"
        
        return await self.send(title, body, NotificationType.ERROR)
    
    async def send_waiting(self, message: str = "Input needed") -> bool:
        """Send a waiting-for-input notification.
        
        Args:
            message: Waiting message
            
        Returns:
            True if sent
        """
        title = "⊗ Sunwell Waiting"
        return await self.send(title, message, NotificationType.WAITING)
    
    def _get_custom_command(self, notification_type: NotificationType) -> str | None:
        """Get custom command for notification type.
        
        Args:
            notification_type: Type of notification
            
        Returns:
            Custom command or None
        """
        if notification_type == NotificationType.SUCCESS:
            return self.config.on_complete
        elif notification_type == NotificationType.ERROR:
            return self.config.on_error
        elif notification_type == NotificationType.WAITING:
            return self.config.on_waiting
        return None
    
    async def _run_custom(self, cmd: str, title: str, message: str) -> bool:
        """Run a custom notification command.
        
        Args:
            cmd: Command template
            title: Notification title
            message: Notification body
            
        Returns:
            True if command succeeded
        """
        # Substitute variables
        expanded = cmd.replace("{title}", title).replace("{message}", message)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                expanded,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as e:
            logger.debug(f"Custom notification failed: {e}")
            return False
    
    async def _notify_terminal_notifier(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> None:
        """Send notification via terminal-notifier (macOS).
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
        """
        args = [
            "terminal-notifier",
            "-title", title,
            "-message", message,
            "-group", "sunwell",
        ]
        
        if self.config.sound:
            # Use appropriate sound based on type
            sounds = {
                NotificationType.SUCCESS: "Glass",
                NotificationType.ERROR: "Basso",
                NotificationType.WAITING: "Ping",
                NotificationType.WARNING: "Purr",
                NotificationType.INFO: "Pop",
            }
            args.extend(["-sound", sounds.get(notification_type, "default")])
        
        await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    
    async def _notify_osascript(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> None:
        """Send notification via osascript (macOS fallback).
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
        """
        # Escape quotes for AppleScript
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        
        if self.config.sound:
            sound_mapping = {
                NotificationType.SUCCESS: "Glass",
                NotificationType.ERROR: "Basso",
                NotificationType.WAITING: "Ping",
            }
            sound = sound_mapping.get(notification_type)
            if sound:
                script += f' sound name "{sound}"'
        
        await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    
    async def _notify_linux(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> None:
        """Send notification via notify-send (Linux).
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
        """
        urgency_map = {
            NotificationType.SUCCESS: "normal",
            NotificationType.ERROR: "critical",
            NotificationType.WAITING: "critical",
            NotificationType.WARNING: "normal",
            NotificationType.INFO: "low",
        }
        urgency = urgency_map.get(notification_type, "normal")
        
        args = [
            "notify-send",
            "--urgency", urgency,
            "--app-name", "Sunwell",
            title,
            message,
        ]
        
        await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    
    async def _notify_windows(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> None:
        """Send notification via PowerShell toast (Windows).
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
        """
        # PowerShell toast notification
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Sunwell").Show($toast)
        '''
        
        await asyncio.create_subprocess_exec(
            "powershell", "-Command", ps_script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    
    def _bell(self) -> None:
        """Ring terminal bell."""
        print("\a", end="", flush=True)


# Convenience functions


async def notify(
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.INFO,
) -> bool:
    """Send a notification with default config.
    
    Args:
        title: Notification title
        message: Notification body
        notification_type: Type of notification
        
    Returns:
        True if sent
    """
    notifier = Notifier()
    return await notifier.send(title, message, notification_type)


async def notify_complete(
    message: str,
    *,
    duration: float | None = None,
    tasks: int | None = None,
) -> bool:
    """Send a completion notification.
    
    Args:
        message: Completion message
        duration: Duration in seconds
        tasks: Number of tasks
        
    Returns:
        True if sent
    """
    notifier = Notifier()
    return await notifier.send_complete(message, duration=duration, tasks=tasks)


async def notify_error(message: str, *, details: str = "") -> bool:
    """Send an error notification.
    
    Args:
        message: Error message
        details: Additional details
        
    Returns:
        True if sent
    """
    notifier = Notifier()
    return await notifier.send_error(message, details=details)


async def notify_waiting(message: str = "Input needed") -> bool:
    """Send a waiting notification.
    
    Args:
        message: Waiting message
        
    Returns:
        True if sent
    """
    notifier = Notifier()
    return await notifier.send_waiting(message)
