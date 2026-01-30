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

# Custom commands for specific notification types
# Available variables: {title}, {message}

# on_complete = "terminal-notifier -title '{title}' -message '{message}'"
# on_error = "notify-send --urgency=critical '{title}' '{message}'"
# on_waiting = "afplay /System/Library/Sounds/Ping.aiff"

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
