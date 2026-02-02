"""Notification configuration loader.

Loads notification settings from .sunwell/config.toml.

Example config:
    [notifications]
    enabled = true
    desktop = true
    sound = true
    on_complete = "terminal-notifier -message '{message}'"
    on_waiting = "afplay /System/Library/Sounds/Ping.aiff"
"""

import logging
from pathlib import Path
from typing import Any

from sunwell.interface.cli.notifications.system import NotificationConfig

logger = logging.getLogger(__name__)

# Default config file location
CONFIG_FILENAME = "config.toml"


def load_notification_config(workspace: Path | None = None) -> NotificationConfig:
    """Load notification config from workspace.
    
    Looks for .sunwell/config.toml in the workspace and reads
    the [notifications] section.
    
    Args:
        workspace: Workspace root (uses cwd if None)
        
    Returns:
        NotificationConfig (defaults if file not found)
    """
    if workspace is None:
        workspace = Path.cwd()
    
    config_path = workspace / ".sunwell" / CONFIG_FILENAME
    
    if not config_path.exists():
        logger.debug(f"No config file at {config_path}, using defaults")
        return NotificationConfig()
    
    try:
        return _load_config_file(config_path)
    except Exception as e:
        logger.warning(f"Failed to load notification config: {e}")
        return NotificationConfig()


def _load_config_file(path: Path) -> NotificationConfig:
    """Load config from TOML file.
    
    Args:
        path: Path to config.toml
        
    Returns:
        NotificationConfig
    """
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    notifications = data.get("notifications", {})
    return NotificationConfig.from_dict(notifications)


def create_example_config_file(workspace: Path) -> Path:
    """Create an example config.toml file.
    
    Args:
        workspace: Workspace root
        
    Returns:
        Path to created file
    """
    config_dir = workspace / ".sunwell"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = config_dir / CONFIG_FILENAME
    
    content = '''# Sunwell Configuration
# This file configures Sunwell's behavior in this workspace.

[notifications]
# Enable/disable notifications
enabled = true

# Show desktop notifications (macOS, Linux, Windows)
desktop = true

# Play sound with notifications
sound = true

# Focus mode behavior (macOS): "ignore", "skip_sound", or "queue"
# - ignore: Send notifications normally
# - skip_sound: Send notification but skip sound
# - queue: Queue notifications for later
focus_mode_behavior = "skip_sound"

# Batch rapid-fire notifications into summaries
batching = false
batch_window_ms = 5000

# Custom commands for specific notification types
# Available variables: {title}, {message}

# on_complete = "terminal-notifier -title '{title}' -message '{message}'"
# on_error = "notify-send --urgency=critical '{title}' '{message}'"
# on_waiting = "afplay /System/Library/Sounds/Ping.aiff"

# Multi-channel routing (enable additional channels below)
# fallback = true

# [notifications.channels.desktop]
# enabled = true
# priority = 1

# [notifications.channels.slack]
# enabled = false
# webhook_url = "https://hooks.slack.com/services/..."
# priority = 2
# types = ["error", "waiting"]  # Only route these types

# [notifications.channels.webhook]
# enabled = false
# url = "https://example.com/webhook"
# method = "POST"
# headers = { "Authorization" = "Bearer xxx" }

[hooks]
# User hooks are configured in hooks.toml
# See .sunwell/hooks.toml for hook configuration
'''
    
    if not config_path.exists():
        config_path.write_text(content)
        logger.info(f"Created example config at {config_path}")
    
    return config_path


def get_config_section(workspace: Path | None, section: str) -> dict[str, Any]:
    """Get a specific section from config.
    
    Args:
        workspace: Workspace root
        section: Section name (e.g., "notifications")
        
    Returns:
        Dictionary of section settings (empty if not found)
    """
    if workspace is None:
        workspace = Path.cwd()
    
    config_path = workspace / ".sunwell" / CONFIG_FILENAME
    
    if not config_path.exists():
        return {}
    
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        
        return data.get(section, {})
    except Exception as e:
        logger.warning(f"Failed to read config section {section}: {e}")
        return {}


def create_notifier(
    workspace: Path | None = None,
    *,
    with_history: bool = True,
    with_batching: bool | None = None,
) -> "Notifier | BatchedNotifier":
    """Create a fully-configured notifier for a workspace.
    
    This is the recommended way to create a notifier. It:
    - Loads config from .sunwell/config.toml
    - Sets up notification history (if enabled)
    - Wraps with batching (if enabled in config or forced)
    
    Args:
        workspace: Workspace root (uses cwd if None)
        with_history: Whether to enable notification history
        with_batching: Override batching setting (None = use config)
        
    Returns:
        Configured Notifier or BatchedNotifier
        
    Example:
        >>> notifier = create_notifier(workspace)
        >>> await notifier.send_complete("Task done")
    """
    from sunwell.interface.cli.notifications.batcher import BatchedNotifier
    from sunwell.interface.cli.notifications.store import NotificationStore
    from sunwell.interface.cli.notifications.system import Notifier
    
    if workspace is None:
        workspace = Path.cwd()
    
    # Load config
    config = load_notification_config(workspace)
    
    # Create store if history enabled
    store = NotificationStore(workspace=workspace) if with_history else None
    
    # Create base notifier
    base_notifier = Notifier(config=config, store=store)
    
    # Determine if batching should be enabled
    enable_batching = with_batching if with_batching is not None else config.batching
    
    if enable_batching:
        return BatchedNotifier(
            notifier=base_notifier,
            window_ms=config.batch_window_ms,
            enabled=True,
        )
    
    return base_notifier


# Type hint imports for create_notifier return type
if True:  # Always import, but structured for type checking
    from sunwell.interface.cli.notifications.batcher import BatchedNotifier
    from sunwell.interface.cli.notifications.system import Notifier
