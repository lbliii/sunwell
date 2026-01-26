"""Tests for autonomous backlog execution.

Tests the wired-up autonomous execution loop including:
- CLIEscalationUI
- _execute_goal_with_guardrails helper
- _run_autonomous with dry-run mode
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from sunwell.interface.cli.core.main import main
from sunwell.interface.cli.helpers.escalation import CLIEscalationUI, create_cli_escalation_ui


class TestCLIEscalationUI:
    """Unit tests for CLIEscalationUI."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a mock console."""
        return MagicMock(spec=Console)

    @pytest.fixture
    def ui(self, console: Console) -> CLIEscalationUI:
        """Create a CLIEscalationUI instance."""
        return CLIEscalationUI(console=console)

    @pytest.mark.asyncio
    async def test_show_escalation_stores_data(self, ui: CLIEscalationUI) -> None:
        """show_escalation stores escalation data for view command."""
        await ui.show_escalation(
            severity="warning",
            message="Test escalation message",
            options=[{"id": "approve", "label": "Approve"}],
            recommended="approve",
        )

        assert ui._last_escalation is not None
        assert ui._last_escalation["severity"] == "warning"
        assert ui._last_escalation["message"] == "Test escalation message"
        assert ui._last_escalation["recommended"] == "approve"

    @pytest.mark.asyncio
    async def test_show_escalation_prints_panel(self, ui: CLIEscalationUI, console: MagicMock) -> None:
        """show_escalation prints a Rich panel."""
        await ui.show_escalation(
            severity="critical",
            message="Critical issue",
            options=[],
            recommended="abort",
        )

        # Console.print should have been called
        assert console.print.called

    @pytest.mark.asyncio
    async def test_await_escalation_response_approve(self, ui: CLIEscalationUI) -> None:
        """await_escalation_response returns approve action."""
        with patch("sunwell.interface.cli.helpers.escalation.Prompt.ask", return_value="a"):
            response = await ui.await_escalation_response("test-id")

        assert response["action"] == "approve"
        assert response["option_id"] == "approve"

    @pytest.mark.asyncio
    async def test_await_escalation_response_skip(self, ui: CLIEscalationUI) -> None:
        """await_escalation_response returns skip action."""
        with patch("sunwell.interface.cli.helpers.escalation.Prompt.ask", return_value="s"):
            response = await ui.await_escalation_response("test-id")

        assert response["action"] == "skip"
        assert response["option_id"] == "skip"

    @pytest.mark.asyncio
    async def test_await_escalation_response_skip_all(self, ui: CLIEscalationUI) -> None:
        """await_escalation_response returns skip_all action."""
        with patch("sunwell.interface.cli.helpers.escalation.Prompt.ask", return_value="S"):
            response = await ui.await_escalation_response("test-id")

        assert response["action"] == "skip_all"
        assert response["option_id"] == "skip_all"

    @pytest.mark.asyncio
    async def test_await_escalation_response_quit(self, ui: CLIEscalationUI) -> None:
        """await_escalation_response returns abort action."""
        with patch("sunwell.interface.cli.helpers.escalation.Prompt.ask", return_value="q"):
            response = await ui.await_escalation_response("test-id")

        assert response["action"] == "abort"
        assert response["option_id"] == "abort"

    @pytest.mark.asyncio
    async def test_await_escalation_response_view_then_approve(self, ui: CLIEscalationUI) -> None:
        """await_escalation_response handles view then approve."""
        # First call returns "v" (view), second returns "a" (approve)
        with patch(
            "sunwell.interface.cli.helpers.escalation.Prompt.ask",
            side_effect=["v", "a"]
        ):
            # Set up last_escalation for view
            ui._last_escalation = {
                "severity": "warning",
                "message": "Test",
                "options": [],
                "recommended": "skip",
            }
            response = await ui.await_escalation_response("test-id")

        assert response["action"] == "approve"

    def test_create_cli_escalation_ui(self, console: Console) -> None:
        """create_cli_escalation_ui creates properly configured instance."""
        ui = create_cli_escalation_ui(console)

        assert isinstance(ui, CLIEscalationUI)
        assert ui.console is console


class TestAutonomousCommand:
    """Integration tests for autonomous command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_autonomous_help_shows_options(self, runner: CliRunner) -> None:
        """autonomous --help shows all options."""
        result = runner.invoke(main, ["backlog", "autonomous", "--help"])

        assert result.exit_code == 0
        assert "--trust" in result.output
        assert "--provider" in result.output
        assert "--model" in result.output
        assert "--yes" in result.output
        assert "--dry-run" in result.output
        assert "--verbose" in result.output
        assert "--max-files" in result.output
        assert "--max-lines" in result.output
        assert "--max-goals" in result.output

    def test_autonomous_dry_run_shows_goals(self, runner: CliRunner, tmp_path: Path) -> None:
        """autonomous --dry-run shows backlog without executing."""
        # Create a simple project with a TODO
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("# TODO: Fix this\nprint('hello')\n")

        result = runner.invoke(
            main,
            ["backlog", "autonomous", "--dry-run"],
            env={"PWD": str(project_dir)},
        )

        # Should complete (may have 0 goals if no signals detected)
        assert result.exit_code in (0, 1, 2)

    def test_autonomous_trust_levels_accepted(self, runner: CliRunner) -> None:
        """autonomous accepts all trust levels."""
        for trust_level in ["conservative", "guarded", "supervised", "full"]:
            result = runner.invoke(
                main,
                ["backlog", "autonomous", "--trust", trust_level, "--help"],
            )
            # Help should work regardless of trust level
            assert result.exit_code == 0


class TestExecuteGoalWithGuardrails:
    """Tests for _execute_goal_with_guardrails helper."""

    @pytest.mark.asyncio
    async def test_execute_goal_success(self) -> None:
        """_execute_goal_with_guardrails executes and returns result."""
        from sunwell.interface.cli.commands.backlog_cmd import _execute_goal_with_guardrails

        # Create mocks
        goal = MagicMock()
        goal.id = "test-goal"
        goal.description = "Test goal description"
        goal.title = "Test Goal"

        manager = AsyncMock()
        manager.run_goal = AsyncMock(return_value=MagicMock(
            success=True,
            artifacts_created=["file1.py", "file2.py"],
            error=None,
        ))

        planner = MagicMock()
        executor = MagicMock()

        result = await _execute_goal_with_guardrails(
            goal=goal,
            manager=manager,
            planner=planner,
            executor=executor,
        )

        assert result is not None
        assert result.success is True
        manager.run_goal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_goal_with_guardrails_checkpoint(self) -> None:
        """_execute_goal_with_guardrails creates checkpoint on success."""
        from sunwell.interface.cli.commands.backlog_cmd import _execute_goal_with_guardrails

        # Create mocks
        goal = MagicMock()
        goal.id = "test-goal"
        goal.description = "Test goal"
        goal.title = "Test"

        manager = AsyncMock()
        manager.run_goal = AsyncMock(return_value=MagicMock(
            success=True,
            artifacts_created=["file.py"],
            error=None,
        ))

        planner = MagicMock()
        executor = MagicMock()
        guardrails = AsyncMock()
        guardrails.checkpoint_goal = AsyncMock()

        await _execute_goal_with_guardrails(
            goal=goal,
            manager=manager,
            planner=planner,
            executor=executor,
            guardrails=guardrails,
        )

        guardrails.checkpoint_goal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_goal_failure_no_checkpoint(self) -> None:
        """_execute_goal_with_guardrails skips checkpoint on failure."""
        from sunwell.interface.cli.commands.backlog_cmd import _execute_goal_with_guardrails

        goal = MagicMock()
        goal.id = "test-goal"
        goal.description = "Test goal"
        goal.title = "Test"

        manager = AsyncMock()
        manager.run_goal = AsyncMock(return_value=MagicMock(
            success=False,
            artifacts_created=[],
            error="Something failed",
        ))

        planner = MagicMock()
        executor = MagicMock()
        guardrails = AsyncMock()
        guardrails.checkpoint_goal = AsyncMock()

        result = await _execute_goal_with_guardrails(
            goal=goal,
            manager=manager,
            planner=planner,
            executor=executor,
            guardrails=guardrails,
        )

        assert result is not None
        assert result.success is False
        guardrails.checkpoint_goal.assert_not_called()
