"""Smoke tests for CLI commands and interfaces.

Tests that the CLI commands work correctly without crashing.
"""

import pytest
from click.testing import CliRunner

from sunwell.interface.cli.core.main import main


class TestDeprecatedCommandsRemoved:
    """Verify deprecated commands have been removed."""

    def test_ask_command_removed(self) -> None:
        """ask command has been removed (was deprecated)."""
        commands = main.list_commands(None)
        assert "ask" not in commands, "'ask' command should have been removed"

    def test_apply_command_removed(self) -> None:
        """apply command has been removed (was deprecated)."""
        commands = main.list_commands(None)
        assert "apply" not in commands, "'apply' command should have been removed"


class TestMainGoalFirstInterface:
    """Tests for the main goal-first interface."""

    def test_help_shows_goal_examples(self) -> None:
        """Help shows goal-first usage examples."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Build a REST API" in result.output or "Just tell it what you want" in result.output

    def test_version_flag(self) -> None:
        """--version works."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()

    def test_chat_command_exists(self) -> None:
        """chat command is registered and accessible."""
        commands = main.list_commands(None)
        assert "chat" in commands

    def test_setup_command_exists(self) -> None:
        """setup command is registered and accessible."""
        commands = main.list_commands(None)
        assert "setup" in commands


class TestCommandRegistration:
    """Tests that all expected commands are registered."""

    @pytest.mark.parametrize("cmd", [
        "agent",
        "bind",
        "config",
        "chat",
        "setup",
        # RFC-110: "skill" removed - execution moved to Agent
        "lens",
        "runtime",
        "plan",
        "verify",
        "bootstrap",
        "team",
        "intel",
        "project",
        "workflow",
        "security",
    ])
    def test_command_registered(self, cmd: str) -> None:
        """Core commands are registered."""
        commands = main.list_commands(None)
        assert cmd in commands, f"Command '{cmd}' not registered"
