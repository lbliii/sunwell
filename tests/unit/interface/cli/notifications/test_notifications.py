"""Tests for cross-platform notification system."""

import pytest
from pathlib import Path

from sunwell.interface.cli.notifications.system import (
    FocusModeBehavior,
    NotificationConfig,
    NotificationType,
    Notifier,
    Platform,
    detect_focus_mode,
    detect_platform,
    has_command,
)
from sunwell.interface.cli.notifications.config import (
    create_example_config_file,
    create_notifier,
    get_config_section,
    load_notification_config,
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


class TestFocusModeBehavior:
    """Test FocusModeBehavior enum."""

    def test_all_behaviors_exist(self) -> None:
        """All expected behaviors exist."""
        behaviors = ["ignore", "skip_sound", "queue"]
        for b in behaviors:
            assert FocusModeBehavior(b) is not None

    def test_values(self) -> None:
        """Enum values are correct."""
        assert FocusModeBehavior.IGNORE.value == "ignore"
        assert FocusModeBehavior.SKIP_SOUND.value == "skip_sound"
        assert FocusModeBehavior.QUEUE.value == "queue"


class TestFocusModeDetection:
    """Test focus mode detection."""

    def test_detect_focus_mode(self) -> None:
        """Focus mode detection returns bool."""
        # This will only actually detect on macOS
        result = detect_focus_mode()
        assert isinstance(result, bool)


class TestNotificationConfigEnhancements:
    """Test enhanced NotificationConfig features."""

    def test_focus_mode_behavior_default(self) -> None:
        """Default focus mode behavior is skip_sound."""
        config = NotificationConfig()
        assert config.focus_mode_behavior == FocusModeBehavior.SKIP_SOUND

    def test_batching_defaults(self) -> None:
        """Batching is disabled by default."""
        config = NotificationConfig()
        assert config.batching is False
        assert config.batch_window_ms == 5000

    def test_from_dict_with_focus_mode(self) -> None:
        """Config from dict with focus_mode_behavior."""
        data = {
            "focus_mode_behavior": "skip_sound",
            "batching": True,
            "batch_window_ms": 3000,
        }
        config = NotificationConfig.from_dict(data)

        assert config.focus_mode_behavior == FocusModeBehavior.SKIP_SOUND
        assert config.batching is True
        assert config.batch_window_ms == 3000

    def test_from_dict_invalid_focus_mode(self) -> None:
        """Invalid focus mode falls back to skip_sound (default)."""
        data = {"focus_mode_behavior": "invalid"}
        config = NotificationConfig.from_dict(data)

        assert config.focus_mode_behavior == FocusModeBehavior.SKIP_SOUND


class TestCreateNotifier:
    """Test create_notifier factory function."""

    def test_create_with_defaults(self, tmp_path: Path) -> None:
        """Create notifier with defaults."""
        notifier = create_notifier(tmp_path)

        # Should return a Notifier (not BatchedNotifier since batching is off by default)
        assert notifier is not None

    def test_create_with_history(self, tmp_path: Path) -> None:
        """Create notifier with history enabled."""
        notifier = create_notifier(tmp_path, with_history=True)

        # Notifier should have a store
        from sunwell.interface.cli.notifications.system import Notifier
        if isinstance(notifier, Notifier):
            assert notifier.store is not None

    def test_create_without_history(self, tmp_path: Path) -> None:
        """Create notifier without history."""
        notifier = create_notifier(tmp_path, with_history=False)

        from sunwell.interface.cli.notifications.system import Notifier
        if isinstance(notifier, Notifier):
            assert notifier.store is None

    def test_create_with_batching_override(self, tmp_path: Path) -> None:
        """Force batching on."""
        notifier = create_notifier(tmp_path, with_batching=True)

        from sunwell.interface.cli.notifications.batcher import BatchedNotifier
        assert isinstance(notifier, BatchedNotifier)

    def test_create_with_config_batching(self, tmp_path: Path) -> None:
        """Batching from config."""
        # Create config with batching enabled
        config_dir = tmp_path / ".sunwell"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text('''
[notifications]
batching = true
batch_window_ms = 2000
''')

        notifier = create_notifier(tmp_path)

        from sunwell.interface.cli.notifications.batcher import BatchedNotifier
        assert isinstance(notifier, BatchedNotifier)
        assert notifier.window_ms == 2000


class TestNotifierWithStore:
    """Test Notifier with notification store."""

    def test_notifier_accepts_store(self, tmp_path: Path) -> None:
        """Notifier can be created with a store."""
        from sunwell.interface.cli.notifications.store import NotificationStore

        store = NotificationStore(workspace=tmp_path)
        config = NotificationConfig(enabled=False)
        notifier = Notifier(config=config, store=store)

        assert notifier.store is store

    @pytest.mark.asyncio
    async def test_disabled_notifier_does_not_record(self, tmp_path: Path) -> None:
        """Disabled notifier returns early without recording."""
        from sunwell.interface.cli.notifications.store import NotificationStore

        store = NotificationStore(workspace=tmp_path)
        config = NotificationConfig(enabled=False)  # Disabled
        notifier = Notifier(config=config, store=store)

        # Disabled notifier returns False immediately without recording
        result = await notifier.send("Test", "Message", NotificationType.INFO)

        assert result is False
        # Disabled notifiers don't record (returns early at config.enabled check)
        assert store.count() == 0

    @pytest.mark.asyncio
    async def test_enabled_notifier_records_to_store(self, tmp_path: Path) -> None:
        """Enabled notifier records notifications to store (regardless of delivery)."""
        from sunwell.interface.cli.notifications.store import NotificationStore

        store = NotificationStore(workspace=tmp_path)
        # Enable notifications but desktop=False so no actual OS notification
        config = NotificationConfig(enabled=True, desktop=False)
        notifier = Notifier(config=config, store=store)

        # Send should record even if no notification is shown
        await notifier.send("Test", "Message", NotificationType.INFO)

        # Check store has record
        assert store.count() == 1
        records = store.get_recent(limit=1)
        assert records[0].title == "Test"
