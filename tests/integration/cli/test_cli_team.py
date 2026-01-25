"""Integration tests for team CLI commands."""

import pytest

from sunwell.interface.cli.commands.team_cmd import team


class TestTeamCommandGroup:
    """Test the team command group."""

    def test_team_command_registered(self) -> None:
        """Test team command group is registered."""
        commands = team.list_commands(None)
        assert "status" in commands
        assert "decisions" in commands
        assert "failures" in commands
        assert "patterns" in commands
        assert "ownership" in commands
        assert "sync" in commands
        assert "onboard" in commands

    def test_team_command_help(self) -> None:
        """Test team command has help text."""
        assert team.help is not None
        assert len(team.help) > 0


class TestTeamStatusCommand:
    """Test team status command."""

    def test_status_command_exists(self) -> None:
        """Test status command is registered."""
        from sunwell.interface.cli.commands.team_cmd import status
        
        assert status.name == "status"

    def test_status_command_has_json_option(self) -> None:
        """Test status command has --json option."""
        from sunwell.interface.cli.commands.team_cmd import status
        
        param_names = {getattr(p, "name", "") for p in status.params}
        assert "as_json" in param_names or any("json" in str(p) for p in status.params)


class TestTeamDecisionsCommand:
    """Test team decisions command."""

    def test_decisions_command_exists(self) -> None:
        """Test decisions command is registered."""
        commands = team.list_commands(None)
        assert "decisions" in commands
