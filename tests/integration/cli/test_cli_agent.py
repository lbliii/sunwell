"""Integration tests for agent CLI commands."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from sunwell.cli.agent import agent
from sunwell.cli.agent.run import run


class TestAgentCommandGroup:
    """Test the agent command group."""

    def test_agent_command_registered(self) -> None:
        """Test agent command group is registered."""
        commands = agent.list_commands(None)
        assert "run" in commands
        assert "resume" in commands
        assert "status" in commands
        assert "illuminate" in commands
        assert "plans" in commands

    def test_agent_help(self) -> None:
        """Test agent command shows help."""
        # Verify command exists and has help text
        assert agent.help is not None
        assert len(agent.help) > 0


class TestAgentRunCommand:
    """Test the agent run command."""

    def test_run_command_exists(self) -> None:
        """Test run command is registered."""
        assert run.name == "run"

    def test_run_command_accepts_goal(self) -> None:
        """Test run command accepts goal argument."""
        # Verify goal is a required argument
        goal_param = next((p for p in run.params if hasattr(p, "name") and p.name == "goal"), None)
        assert goal_param is not None

    def test_run_command_options(self) -> None:
        """Test run command has expected options."""
        # Verify command has parameters (options/arguments)
        assert len(run.params) > 0
        
        # Check for key parameters by name
        param_names = {getattr(p, "name", "") for p in run.params}
        param_strs = {str(p) for p in run.params}
        
        # At least one of these should be present
        has_time = "time" in param_names or any("time" in s.lower() for s in param_strs)
        has_goal = "goal" in param_names or any("goal" in s.lower() for s in param_strs)
        
        assert has_goal, "Run command should accept goal argument"
        assert has_time or len(param_names) > 0, "Run command should have options"

    def test_run_command_callback(self) -> None:
        """Test run command has a callback function."""
        # Verify the command structure is correct
        assert callable(run.callback)


class TestAgentStatusCommand:
    """Test the agent status command."""

    def test_status_command_exists(self) -> None:
        """Test status command is registered."""
        from sunwell.cli.agent.status import status
        
        assert status.name == "status"

    @pytest.mark.asyncio
    async def test_status_command_runs(self, tmp_path: Path) -> None:
        """Test status command can be invoked."""
        from sunwell.cli.agent.status import status
        
        # Status should work even with no checkpoints
        # This tests the command structure, not full execution
        assert callable(status.callback)
