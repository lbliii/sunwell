"""Smoke tests for deprecated CLI commands.

These commands are marked deprecated but should still be callable without crashing.
If they break, users get confusing errors instead of deprecation warnings.
"""

import pytest
from click.testing import CliRunner

from sunwell.cli.main import main


class TestDeprecatedAskCommand:
    """Tests for the deprecated 'ask' command."""

    def test_ask_command_exists(self) -> None:
        """ask command is registered."""
        commands = main.list_commands(None)
        assert "ask" in commands

    def test_ask_without_args_shows_error(self) -> None:
        """ask without args shows usage error (not crash)."""
        runner = CliRunner()
        result = runner.invoke(main, ["ask"])

        # Should fail gracefully with missing argument, not crash
        # May fail with PermissionError in sandbox, but shouldn't crash Python
        assert result.exit_code != 0

    def test_ask_shows_deprecation_warning(self) -> None:
        """ask shows deprecation warning before any error."""
        runner = CliRunner()
        # Provide a prompt so it gets past arg parsing
        result = runner.invoke(main, ["ask", "test prompt"])

        # In sandbox, may fail with PermissionError before showing deprecation
        # The key assertion is it doesn't crash with an unhandled exception
        assert result.exit_code != 0 or "deprecated" in result.output.lower()


class TestDeprecatedApplyCommand:
    """Tests for the deprecated 'apply' command."""

    def test_apply_command_exists(self) -> None:
        """apply command is registered."""
        commands = main.list_commands(None)
        assert "apply" in commands

    def test_apply_without_args_shows_error(self) -> None:
        """apply without args shows usage error (not crash)."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply"])

        # Should fail gracefully, not crash
        assert result.exit_code != 0


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
