"""Tests for user-configurable hooks."""

import pytest
from pathlib import Path

from sunwell.interface.cli.hooks import (
    HookConfig,
    HookTriggerCondition,
    UserHooksConfig,
    load_user_hooks,
)


class TestHookConfig:
    """Test HookConfig parsing."""
    
    def test_from_dict_minimal(self) -> None:
        """Parse minimal hook config."""
        data = {
            "name": "test-hook",
            "on": ["session:end"],
            "run": "echo hello",
        }
        hook = HookConfig.from_dict(data)
        
        assert hook.name == "test-hook"
        assert hook.on == ("session:end",)
        assert hook.run == "echo hello"
        assert hook.requires == ()
        assert hook.env == ()
        assert hook.when == HookTriggerCondition.ALWAYS
        assert hook.timeout == 30
        assert hook.background is False
    
    def test_from_dict_full(self) -> None:
        """Parse fully specified hook config."""
        data = {
            "name": "full-hook",
            "on": ["task:complete", "gate:pass"],
            "run": "notify ${TASK_ID}",
            "requires": ["notify-send"],
            "env": ["SLACK_TOKEN"],
            "when": "success",
            "timeout": 60,
            "background": True,
            "cwd": "/tmp",
        }
        hook = HookConfig.from_dict(data)
        
        assert hook.name == "full-hook"
        assert hook.on == ("task:complete", "gate:pass")
        assert hook.run == "notify ${TASK_ID}"
        assert hook.requires == ("notify-send",)
        assert hook.env == ("SLACK_TOKEN",)
        assert hook.when == HookTriggerCondition.SUCCESS
        assert hook.timeout == 60
        assert hook.background is True
        assert hook.cwd == "/tmp"
    
    def test_from_dict_single_event_string(self) -> None:
        """Single event as string is converted to tuple."""
        data = {
            "name": "test",
            "on": "session:end",  # Single string, not list
            "run": "echo done",
        }
        hook = HookConfig.from_dict(data)
        assert hook.on == ("session:end",)
    
    def test_from_dict_missing_name_raises(self) -> None:
        """Missing name raises ValueError."""
        data = {
            "on": ["session:end"],
            "run": "echo test",
        }
        with pytest.raises(ValueError, match="missing required 'name' field"):
            HookConfig.from_dict(data)
    
    def test_from_dict_missing_on_raises(self) -> None:
        """Missing on raises ValueError."""
        data = {
            "name": "test",
            "run": "echo test",
        }
        with pytest.raises(ValueError, match="missing required 'on' field"):
            HookConfig.from_dict(data)
    
    def test_from_dict_missing_run_raises(self) -> None:
        """Missing run raises ValueError."""
        data = {
            "name": "test",
            "on": ["session:end"],
        }
        with pytest.raises(ValueError, match="missing required 'run' field"):
            HookConfig.from_dict(data)
    
    def test_from_dict_invalid_when_raises(self) -> None:
        """Invalid when value raises ValueError."""
        data = {
            "name": "test",
            "on": ["session:end"],
            "run": "echo test",
            "when": "invalid",
        }
        with pytest.raises(ValueError, match="invalid 'when' value"):
            HookConfig.from_dict(data)


class TestUserHooksConfig:
    """Test UserHooksConfig parsing."""
    
    def test_from_dict_empty(self) -> None:
        """Parse empty config."""
        config = UserHooksConfig.from_dict({})
        assert config.hooks == ()
        assert config.version == 1
    
    def test_from_dict_with_hooks(self) -> None:
        """Parse config with hooks."""
        data = {
            "version": 1,
            "hooks": [
                {"name": "hook1", "on": ["session:end"], "run": "echo 1"},
                {"name": "hook2", "on": ["task:complete"], "run": "echo 2"},
            ],
        }
        config = UserHooksConfig.from_dict(data)
        
        assert len(config.hooks) == 2
        assert config.hooks[0].name == "hook1"
        assert config.hooks[1].name == "hook2"
    
    def test_get_hooks_for_event(self) -> None:
        """Filter hooks by event."""
        data = {
            "hooks": [
                {"name": "hook1", "on": ["session:end"], "run": "echo 1"},
                {"name": "hook2", "on": ["task:complete", "session:end"], "run": "echo 2"},
                {"name": "hook3", "on": ["task:complete"], "run": "echo 3"},
            ],
        }
        config = UserHooksConfig.from_dict(data)
        
        session_hooks = config.get_hooks_for_event("session:end")
        assert len(session_hooks) == 2
        assert {h.name for h in session_hooks} == {"hook1", "hook2"}
        
        task_hooks = config.get_hooks_for_event("task:complete")
        assert len(task_hooks) == 2
        assert {h.name for h in task_hooks} == {"hook2", "hook3"}
        
        other_hooks = config.get_hooks_for_event("gate:fail")
        assert len(other_hooks) == 0


class TestLoadUserHooks:
    """Test loading hooks from TOML files."""
    
    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        """Non-existent file returns empty config."""
        config = load_user_hooks(tmp_path)
        assert config.hooks == ()
    
    def test_load_valid_toml(self, tmp_path: Path) -> None:
        """Load valid TOML file."""
        config_dir = tmp_path / ".sunwell"
        config_dir.mkdir()
        
        hooks_file = config_dir / "hooks.toml"
        hooks_file.write_text('''
version = 1

[[hooks]]
name = "test-hook"
on = ["session:end"]
run = "echo done"
''')
        
        config = load_user_hooks(tmp_path)
        assert len(config.hooks) == 1
        assert config.hooks[0].name == "test-hook"
    
    def test_load_invalid_toml_returns_empty(self, tmp_path: Path) -> None:
        """Invalid TOML returns empty config with warning."""
        config_dir = tmp_path / ".sunwell"
        config_dir.mkdir()
        
        hooks_file = config_dir / "hooks.toml"
        hooks_file.write_text("invalid toml {{{{")
        
        config = load_user_hooks(tmp_path)
        assert config.hooks == ()


class TestHookTriggerCondition:
    """Test HookTriggerCondition enum."""
    
    def test_values(self) -> None:
        """All expected values exist."""
        assert HookTriggerCondition.ALWAYS.value == "always"
        assert HookTriggerCondition.SUCCESS.value == "success"
        assert HookTriggerCondition.FAILURE.value == "failure"
