"""Desktop notification channel.

Sends native desktop notifications using platform-specific mechanisms:
- macOS: terminal-notifier (if installed), osascript fallback
- Linux: notify-send
- Windows: PowerShell toast notifications
- Fallback: Terminal bell
"""

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass, field

from sunwell.interface.cli.notifications.channels.base import BaseChannel, ChannelConfig
from sunwell.interface.cli.notifications.system import (
    NotificationConfig,
    NotificationType,
    Platform,
    detect_focus_mode,
    detect_platform,
)

logger = logging.getLogger(__name__)


def has_command(cmd: str) -> bool:
    """Check if a command is available on the system."""
    return shutil.which(cmd) is not None


@dataclass
class DesktopChannel(BaseChannel):
    """Desktop notification channel.
    
    Sends native desktop notifications using platform-specific mechanisms.
    
    Example:
        >>> channel = DesktopChannel()
        >>> await channel.send("Title", "Message", NotificationType.SUCCESS)
    """
    
    notification_config: NotificationConfig = field(default_factory=NotificationConfig)
    _platform: Platform = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        self._platform = detect_platform()
        # Set channel name
        if self.config.name == "channel":
            object.__setattr__(
                self, "config",
                ChannelConfig(
                    enabled=self.config.enabled,
                    priority=self.config.priority,
                    types=self.config.types,
                    name="desktop",
                )
            )
    
    def is_available(self) -> bool:
        """Check if desktop notifications are available."""
        if not self.config.enabled:
            return False
        if not self.notification_config.enabled:
            return False
        if not self.notification_config.desktop:
            return False
        
        # Check platform-specific availability
        if self._platform == Platform.MACOS:
            return True  # osascript always available
        elif self._platform == Platform.LINUX:
            return has_command("notify-send")
        elif self._platform == Platform.WINDOWS:
            return True  # PowerShell always available
        
        return False
    
    async def send(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        *,
        context: dict | None = None,
    ) -> bool:
        """Send a desktop notification.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type of notification
            context: Optional context data (for deep linking)
            
        Returns:
            True if sent successfully
        """
        if not self.is_available():
            return False
        
        # Check Focus mode
        skip_sound = False
        if detect_focus_mode():
            from sunwell.interface.cli.notifications.system import FocusModeBehavior
            
            behavior = self.notification_config.focus_mode_behavior
            if behavior == FocusModeBehavior.QUEUE:
                # Don't send when queuing
                return False
            elif behavior == FocusModeBehavior.SKIP_SOUND:
                skip_sound = True
        
        try:
            if self._platform == Platform.MACOS:
                if has_command("terminal-notifier"):
                    await self._notify_terminal_notifier(
                        title, message, notification_type,
                        skip_sound=skip_sound,
                        context=context,
                    )
                else:
                    await self._notify_osascript(
                        title, message, notification_type,
                        skip_sound=skip_sound,
                    )
            elif self._platform == Platform.LINUX:
                await self._notify_linux(title, message, notification_type)
            elif self._platform == Platform.WINDOWS:
                await self._notify_windows(
                    title, message, notification_type,
                    skip_sound=skip_sound,
                )
            else:
                # Fallback to terminal bell
                if self.notification_config.sound and not skip_sound:
                    print("\a", end="", flush=True)
                return False
            
            return True
        except Exception as e:
            logger.debug(f"Desktop notification failed: {e}")
            return False
    
    async def _notify_terminal_notifier(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        *,
        skip_sound: bool = False,
        context: dict | None = None,
    ) -> None:
        """Send notification via terminal-notifier (macOS)."""
        args = [
            "terminal-notifier",
            "-title", title,
            "-message", message,
            "-group", "sunwell",
        ]
        
        # Add custom icon if configured (PNG or ICNS recommended for macOS)
        if self.notification_config.icon_path and self.notification_config.icon_path.exists():
            args.extend(["-appIcon", str(self.notification_config.icon_path)])
        
        if self.notification_config.sound and not skip_sound:
            sounds = {
                NotificationType.SUCCESS: "Glass",
                NotificationType.ERROR: "Basso",
                NotificationType.WAITING: "Ping",
                NotificationType.WARNING: "Purr",
                NotificationType.INFO: "Pop",
            }
            args.extend(["-sound", sounds.get(notification_type, "default")])
        
        # Add deep link if context has file path
        if context and "file" in context:
            file_path = context["file"]
            line = context.get("line", 1)
            # VS Code URI
            args.extend(["-open", f"vscode://file/{file_path}:{line}"])
        
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
        *,
        skip_sound: bool = False,
    ) -> None:
        """Send notification via osascript (macOS fallback)."""
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        
        if self.notification_config.sound and not skip_sound:
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
        """Send notification via notify-send (Linux)."""
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
        ]
        
        # Add custom icon if configured (SVG or PNG supported on Linux)
        if self.notification_config.icon_path and self.notification_config.icon_path.exists():
            args.extend(["--icon", str(self.notification_config.icon_path)])
        
        args.extend([title, message])
        
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
        *,
        skip_sound: bool = False,
    ) -> None:
        """Send notification via PowerShell toast (Windows)."""
        audio_xml = '<audio silent="true"/>' if skip_sound else ""
        
        # Add app logo override if icon is configured (PNG recommended)
        logo_xml = ""
        if self.notification_config.icon_path and self.notification_config.icon_path.exists():
            icon_path = str(self.notification_config.icon_path).replace("\\", "/")
            logo_xml = f'<image placement="appLogoOverride" src="file:///{icon_path}"/>'
        
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastGeneric">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                    {logo_xml}
                </binding>
            </visual>
            {audio_xml}
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
