"""Tests for goal-first CLI invocation.

Ensures the primary use case `sunwell "goal"` works without crashing.
These tests catch parameter signature mismatches between main.py and goal.py.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock

from sunwell.interface.cli.core.main import main


class TestGoalInvocation:
    """Tests for invoking sunwell with a goal string."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_goal_invocation_parameter_compatibility(self, runner: CliRunner) -> None:
        """Goal invocation passes all parameters correctly to run_goal.
        
        This test catches signature mismatches between main.py's ctx.invoke()
        and the run_goal function signature. The bug that prompted this test
        was open_studio being passed but not accepted.
        """
        # Mock run_goal_unified to avoid actual execution
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            result = runner.invoke(main, ["test goal"])
            
            # Should not crash with "unexpected keyword argument"
            # Exit code 1 is OK (might fail for other reasons like no config)
            # but we should not get a TypeError from parameter mismatch
            assert "unexpected keyword argument" not in result.output
            assert "got an unexpected keyword argument" not in (result.exception or "")

    def test_goal_with_plan_flag(self, runner: CliRunner) -> None:
        """Goal with --plan flag works."""
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            result = runner.invoke(main, ["--plan", "test goal"])
            assert "unexpected keyword argument" not in result.output

    def test_goal_with_converge_flag(self, runner: CliRunner) -> None:
        """Goal with --converge flag works."""
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            result = runner.invoke(main, ["--converge", "test goal"])
            assert "unexpected keyword argument" not in result.output

    def test_goal_with_all_flags(self, runner: CliRunner) -> None:
        """Goal with all optional flags works."""
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            result = runner.invoke(
                main,
                [
                    "--plan",
                    "--open",
                    "--converge",
                    "--converge-gates", "lint,type,test",
                    "--converge-max", "10",
                    "--verbose",
                    "--json",
                    "test goal",
                ],
            )
            assert "unexpected keyword argument" not in result.output


class TestRunGoalParameterSignature:
    """Tests to verify run_goal accepts all parameters main.py passes."""

    def test_run_goal_accepts_open_studio(self) -> None:
        """run_goal accepts open_studio parameter."""
        from sunwell.interface.cli.commands.goal import run_goal
        
        # Check the function's parameters
        import inspect
        sig = inspect.signature(run_goal.callback)
        params = list(sig.parameters.keys())
        
        assert "open_studio" in params, "run_goal must accept open_studio"

    def test_run_goal_accepts_converge_params(self) -> None:
        """run_goal accepts converge parameters."""
        from sunwell.interface.cli.commands.goal import run_goal
        
        import inspect
        sig = inspect.signature(run_goal.callback)
        params = list(sig.parameters.keys())
        
        assert "converge" in params, "run_goal must accept converge"
        assert "converge_gates" in params, "run_goal must accept converge_gates"
        assert "converge_max" in params, "run_goal must accept converge_max"

    def test_main_and_run_goal_params_compatible(self) -> None:
        """All params main.py passes to run_goal are accepted.
        
        This is the definitive test that would have caught the bug.
        """
        from sunwell.interface.cli.commands.goal import run_goal
        
        import inspect
        sig = inspect.signature(run_goal.callback)
        run_goal_params = set(sig.parameters.keys())
        
        # These are the params main.py passes via ctx.invoke
        # (from main.py lines 306-321)
        main_passes = {
            "goal",
            "dry_run",
            "open_studio",
            "json_output",
            "provider",
            "model",
            "verbose",
            "time",
            "trust",
            "workspace",
            "converge",
            "converge_gates",
            "converge_max",
        }
        
        missing = main_passes - run_goal_params
        assert not missing, f"run_goal missing params that main.py passes: {missing}"


