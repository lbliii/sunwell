"""Integration tests for CLI main entry point and command routing."""

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest

from sunwell.interface.cli.core.main import GoalFirstGroup, main


class TestGoalFirstGroup:
    """Test the goal-first command parsing."""

    def test_goal_first_group_exists(self) -> None:
        """Test GoalFirstGroup class exists and can be instantiated."""
        group = GoalFirstGroup("test")
        assert isinstance(group, click.Group)
        assert group.name == "test"

    def test_goal_first_group_inherits_from_click_group(self) -> None:
        """Test GoalFirstGroup is a proper Click group."""
        group = GoalFirstGroup("test")
        # Verify it has the expected methods
        assert hasattr(group, "parse_args")
        assert hasattr(group, "list_commands")


class TestMainCommand:
    """Test the main CLI command."""

    def test_main_command_exists(self) -> None:
        """Test main command is defined."""
        assert main is not None
        assert callable(main)

    def test_main_has_options(self) -> None:
        """Test main command has expected options."""
        param_names = {p.name for p in main.params if hasattr(p, "name")}
        
        # Verify key options exist
        assert "plan" in param_names or any("plan" in str(p) for p in main.params)
        assert "verbose" in param_names or any("verbose" in str(p) for p in main.params)


class TestCommandRegistration:
    """Test that all commands are properly registered."""

    def test_chat_command_registered(self) -> None:
        """Test chat command is registered."""
        commands = main.list_commands(None)
        assert "chat" in commands

    def test_setup_command_registered(self) -> None:
        """Test setup command is registered."""
        commands = main.list_commands(None)
        assert "setup" in commands

    def test_agent_command_registered(self) -> None:
        """Test agent command is registered."""
        commands = main.list_commands(None)
        assert "agent" in commands

    def test_team_command_registered(self) -> None:
        """Test team command is registered."""
        commands = main.list_commands(None)
        assert "team" in commands

    def test_bootstrap_command_registered(self) -> None:
        """Test bootstrap command is registered."""
        commands = main.list_commands(None)
        assert "bootstrap" in commands

    def test_internal_command_registered(self) -> None:
        """Test internal command group is registered (CLI Core Refactor)."""
        commands = main.list_commands(None)
        assert "internal" in commands

    def test_config_command_is_group(self) -> None:
        """Test config command is now a group with subcommands (CLI Core Refactor)."""
        config_cmd = main.commands.get("config")
        assert config_cmd is not None
        # Config should be a group, not a simple command
        assert hasattr(config_cmd, "commands")
        assert "show" in config_cmd.commands
        assert "get" in config_cmd.commands
        assert "set" in config_cmd.commands


class TestCLICoreRefactor:
    """Tests specific to the CLI Core Refactor changes."""

    def test_deprecated_commands_removed(self) -> None:
        """Test deprecated ask/apply commands have been removed."""
        commands = main.list_commands(None)
        assert "ask" not in commands, "Deprecated 'ask' command should be removed"
        assert "apply" not in commands, "Deprecated 'apply' command should be removed"

    def test_internal_group_has_expected_subcommands(self) -> None:
        """Test internal group contains expected subcommands."""
        internal_cmd = main.commands.get("internal")
        assert internal_cmd is not None
        assert hasattr(internal_cmd, "commands")
        
        # Check for some key internal commands
        internal_commands = internal_cmd.commands
        assert "backlog" in internal_commands
        assert "workflow" in internal_commands

    def test_async_runner_module_exists(self) -> None:
        """Test async_runner module can be imported."""
        from sunwell.interface.cli.core.async_runner import async_command, run_async
        
        assert callable(run_async)
        assert callable(async_command)
