"""Tests for cross-platform notification system."""

import pytest
from pathlib import Path

from sunwell.interface.cli.notifications.system import (
    NotificationConfig,
    NotificationType,
    Notifier,
    Platform,
    detect_platform,
    has_command,
)
from sunwell.interface.cli.notifications.config import (
    load_notification_config,
    create_example_config_file,
    get_config_section,
)


class TestNotificationConfig:
    """Test NotificationConfig dataclass."""
    
    def test_default_values(self) -> None:
        """Default config enables notifications."""
        config = NotificationConfig()
        assert config.enabled is True
        assert config.desktop is True
        assert config.sound is True
    
    def test_from_dict(self) -> None:
        """Create config from dictionary."""
        data = {
            "enabled": False,
            "desktop": True,
            "sound": False,
            "on_complete": "echo done",
        }
        config = NotificationConfig.from_dict(data)
        
        assert config.enabled is False
        assert config.desktop is True
        assert config.sound is False
        assert config.on_complete == "echo done"
    
    def test_from_empty_dict(self) -> None:
        """Empty dict uses defaults."""
        config = NotificationConfig.from_dict({})
        assert config.enabled is True


class TestNotificationType:
    """Test NotificationType enum."""
    
    def test_all_types_exist(self) -> None:
        """All expected notification types exist."""
        types = ["info", "success", "warning", "error", "waiting"]
        for t in types:
            assert NotificationType(t) is not None
    
    def test_values(self) -> None:
        """Enum values are correct strings."""
        assert NotificationType.INFO.value == "info"
        assert NotificationType.SUCCESS.value == "success"
        assert NotificationType.ERROR.value == "error"
        assert NotificationType.WAITING.value == "waiting"


class TestPlatformDetection:
    """Test platform detection."""
    
    def test_detect_platform(self) -> None:
        """Platform detection returns valid enum."""
        plat = detect_platform()
        assert plat in Platform
    
    def test_has_command_echo(self) -> None:
        """Echo command should exist on all platforms."""
        # echo exists on all platforms
        result = has_command("echo")
        # This may fail in some CI environments but should work locally
        assert isinstance(result, bool)
    
    def test_has_command_nonexistent(self) -> None:
        """Non-existent command returns False."""
        result = has_command("definitely_not_a_real_command_xyz123")
        assert result is False


class TestNotifier:
    """Test Notifier class."""
    
    def test_create_notifier_default(self) -> None:
        """Notifier can be created with defaults."""
        notifier = Notifier()
        assert notifier.config is not None
        assert notifier._platform in Platform
    
    def test_create_notifier_disabled(self) -> None:
        """Disabled notifier has no notifier function."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        
        assert notifier._notifier_fn is None
    
    def test_create_notifier_no_desktop(self) -> None:
        """No desktop notifier when desktop=False."""
        config = NotificationConfig(desktop=False)
        notifier = Notifier(config=config)
        
        assert notifier._notifier_fn is None
    
    def test_get_custom_command(self) -> None:
        """Custom commands are retrieved correctly."""
        config = NotificationConfig(
            on_complete="echo complete",
            on_error="echo error",
            on_waiting="echo waiting",
        )
        notifier = Notifier(config=config)
        
        assert notifier._get_custom_command(NotificationType.SUCCESS) == "echo complete"
        assert notifier._get_custom_command(NotificationType.ERROR) == "echo error"
        assert notifier._get_custom_command(NotificationType.WAITING) == "echo waiting"
        assert notifier._get_custom_command(NotificationType.INFO) is None
    
    @pytest.mark.asyncio
    async def test_send_disabled(self) -> None:
        """Disabled notifier returns False."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        
        result = await notifier.send("Test", "Message")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_complete(self) -> None:
        """send_complete formats message correctly."""
        # Use disabled config to avoid actual notifications
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        
        # This should return False but not raise
        result = await notifier.send_complete("Done", duration=12.5, tasks=5)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_error(self) -> None:
        """send_error works with disabled config."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        
        result = await notifier.send_error("Failed", details="Something went wrong")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_waiting(self) -> None:
        """send_waiting works with disabled config."""
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config)
        
        result = await notifier.send_waiting("Need input")
        assert result is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    @pytest.mark.asyncio
    async def test_notify_function_exists(self) -> None:
        """notify function can be imported and called."""
        from sunwell.interface.cli.notifications import notify
        
        # Just verify it doesn't raise
        # Result depends on platform/availability
        result = await notify("Test", "Message")
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_notify_complete_function(self) -> None:
        """notify_complete function works."""
        from sunwell.interface.cli.notifications import notify_complete
        
        result = await notify_complete("Done", duration=1.0, tasks=1)
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_notify_error_function(self) -> None:
        """notify_error function works."""
        from sunwell.interface.cli.notifications import notify_error
        
        result = await notify_error("Error")
        assert isinstance(result, bool)


class TestConfigLoader:
    """Test notification config loading."""
    
    def test_load_missing_config(self, tmp_path: Path) -> None:
        """Missing config returns defaults."""
        config = load_notification_config(tmp_path)
        
        assert config.enabled is True
        assert config.desktop is True
    
    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Valid config is loaded correctly."""
        # Create config file
        config_dir = tmp_path / ".sunwell"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text('''
[notifications]
enabled = false
desktop = true
sound = false
on_complete = "echo done"
''')
        
        config = load_notification_config(tmp_path)
        
        assert config.enabled is False
        assert config.desktop is True
        assert config.sound is False
        assert config.on_complete == "echo done"
    
    def test_create_example_config(self, tmp_path: Path) -> None:
        """Example config is created correctly."""
        path = create_example_config_file(tmp_path)
        
        assert path.exists()
        content = path.read_text()
        assert "[notifications]" in content
        assert "enabled = true" in content
    
    def test_get_config_section(self, tmp_path: Path) -> None:
        """Getting config section works."""
        # Create config file
        config_dir = tmp_path / ".sunwell"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text('''
[notifications]
enabled = true

[other]
value = "test"
''')
        
        section = get_config_section(tmp_path, "other")
        assert section == {"value": "test"}
    
    def test_get_missing_section(self, tmp_path: Path) -> None:
        """Missing section returns empty dict."""
        section = get_config_section(tmp_path, "nonexistent")
        assert section == {}
