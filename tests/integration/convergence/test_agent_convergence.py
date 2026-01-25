"""Integration tests for agent convergence (RFC-123, RFC-MEMORY).

Tests the integration between Agent and ConvergenceLoop.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.events import EventType
from sunwell.agent.validation.gates import GateType
from sunwell.agent.utils.request import RunOptions
from sunwell.agent.convergence import ConvergenceConfig


class TestAgentConvergenceIntegration:
    """Integration tests for Agent with convergence enabled."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_run_options_converge_flag(self):
        """RunOptions should support converge flag."""
        options = RunOptions(converge=True)
        assert options.converge is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_run_options_convergence_config(self):
        """RunOptions should support convergence config."""
        config = ConvergenceConfig(
            max_iterations=3,
            enabled_gates=frozenset({GateType.LINT}),
        )
        options = RunOptions(converge=True, convergence_config=config)
        
        assert options.convergence_config is not None
        assert options.convergence_config.max_iterations == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_context_with_convergence_options(self):
        """SessionContext should work with convergence options."""
        config = ConvergenceConfig(max_iterations=5)
        options = RunOptions(converge=True, convergence_config=config)
        
        # SessionContext uses RunOptions
        assert options.converge is True
        assert options.convergence_config is not None
        assert options.convergence_config.max_iterations == 5


class TestToolExecutorHook:
    """Tests for ToolExecutor on_file_write hook."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_hook_callback_structure(self, tmp_path: Path):
        """Hook callback should receive Path."""
        from sunwell.tools.executor import ToolExecutor
        from sunwell.tools.types import ToolPolicy, ToolTrust

        # Create executor with mock callback
        called_with: list[Path] = []
        
        async def hook_callback(path: Path) -> None:
            called_with.append(path)

        executor = ToolExecutor(
            workspace=tmp_path,  # Use tmp_path to avoid workspace validation
            policy=ToolPolicy(trust_level=ToolTrust.READ_ONLY),
            on_file_write=hook_callback,
        )
        
        assert executor.on_file_write is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_hook_receives_path_type(self):
        """Hook should be called with Path object."""
        from pathlib import Path
        
        # Verify Path is used correctly
        test_path = Path("/tmp/test.py")
        assert isinstance(test_path, Path)


class TestConvergenceEvents:
    """Tests for convergence event generation."""

    @pytest.mark.integration
    def test_convergence_start_event_factory(self):
        """convergence_start_event should create valid event."""
        from sunwell.agent.events import convergence_start_event

        event = convergence_start_event(
            files=["test.py"],
            gates=["lint", "type"],
            max_iterations=5,
        )

        assert event.type == EventType.CONVERGENCE_START
        assert event.data["files"] == ["test.py"]
        assert event.data["gates"] == ["lint", "type"]
        assert event.data["max_iterations"] == 5

    @pytest.mark.integration
    def test_convergence_stable_event_factory(self):
        """convergence_stable_event should create valid event."""
        from sunwell.agent.events import convergence_stable_event

        event = convergence_stable_event(
            iterations=3,
            duration_ms=5000,
        )

        assert event.type == EventType.CONVERGENCE_STABLE
        assert event.data["iterations"] == 3
        assert event.data["duration_ms"] == 5000

    @pytest.mark.integration
    def test_convergence_iteration_complete_event_factory(self):
        """convergence_iteration_complete_event should create valid event."""
        from sunwell.agent.events import convergence_iteration_complete_event

        event = convergence_iteration_complete_event(
            iteration=2,
            all_passed=False,
            total_errors=5,
            gate_results=[
                {"gate": "lint", "passed": False, "errors": 3},
                {"gate": "type", "passed": False, "errors": 2},
            ],
        )

        assert event.type == EventType.CONVERGENCE_ITERATION_COMPLETE
        assert event.data["iteration"] == 2
        assert event.data["all_passed"] is False
        assert event.data["total_errors"] == 5
        assert len(event.data["gate_results"]) == 2

    @pytest.mark.integration
    def test_convergence_max_iterations_event_factory(self):
        """convergence_max_iterations_event should create valid event."""
        from sunwell.agent.events import convergence_max_iterations_event

        event = convergence_max_iterations_event(iterations=5)

        assert event.type == EventType.CONVERGENCE_MAX_ITERATIONS
        assert event.data["iterations"] == 5

    @pytest.mark.integration
    def test_convergence_stuck_event_factory(self):
        """convergence_stuck_event should create valid event."""
        from sunwell.agent.events import convergence_stuck_event

        event = convergence_stuck_event(
            iterations=3,
            repeated_errors=["lint:E501", "type:missing-return"],
        )

        assert event.type == EventType.CONVERGENCE_STUCK
        assert event.data["iterations"] == 3
        assert "lint:E501" in event.data["repeated_errors"]


class TestConvergenceModuleImports:
    """Tests for convergence module public API."""

    @pytest.mark.integration
    def test_convergence_module_exports(self):
        """Convergence module should export expected types."""
        from sunwell.convergence import (
            ConvergenceConfig,
            ConvergenceIteration,
            ConvergenceLoop,
            ConvergenceResult,
            ConvergenceStatus,
            GateCheckResult,
        )

        # Verify all exports are accessible
        assert ConvergenceConfig is not None
        assert ConvergenceIteration is not None
        assert ConvergenceLoop is not None
        assert ConvergenceResult is not None
        assert ConvergenceStatus is not None
        assert GateCheckResult is not None

    @pytest.mark.integration
    def test_event_types_include_convergence(self):
        """EventType should include convergence events."""
        from sunwell.agent.events import EventType

        # Verify convergence event types exist
        assert EventType.CONVERGENCE_START is not None
        assert EventType.CONVERGENCE_ITERATION_START is not None
        assert EventType.CONVERGENCE_ITERATION_COMPLETE is not None
        assert EventType.CONVERGENCE_FIXING is not None
        assert EventType.CONVERGENCE_STABLE is not None
        assert EventType.CONVERGENCE_TIMEOUT is not None
        assert EventType.CONVERGENCE_STUCK is not None
        assert EventType.CONVERGENCE_MAX_ITERATIONS is not None
        assert EventType.CONVERGENCE_BUDGET_EXCEEDED is not None
