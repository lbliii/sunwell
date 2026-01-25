"""Unit tests for ConvergenceLoop (RFC-123)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.events import EventType
from sunwell.agent.validation.gates import GateType
from sunwell.agent.convergence.loop import ConvergenceLoop
from sunwell.agent.convergence.types import ConvergenceConfig, ConvergenceStatus


@pytest.fixture
def mock_model():
    """Create a mock model for testing."""
    model = MagicMock()
    model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
    return model


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with a test file."""
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1\n")
    return tmp_path


class TestConvergenceLoopInit:
    """Tests for ConvergenceLoop initialization."""

    def test_default_config(self, mock_model, tmp_workspace):
        """Should use default config when none provided."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        assert loop.config.max_iterations == 5
        assert loop.result is None

    def test_custom_config(self, mock_model, tmp_workspace):
        """Should accept custom config."""
        config = ConvergenceConfig(max_iterations=3)
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace, config=config)
        assert loop.config.max_iterations == 3


class TestConvergenceLoopRun:
    """Tests for ConvergenceLoop.run() method."""

    @pytest.mark.asyncio
    async def test_stable_on_first_try(self, mock_model, tmp_workspace):
        """Should return STABLE if all gates pass immediately."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(
            model=mock_model,
            cwd=tmp_workspace,
            config=config,
        )

        # Mock: lint passes immediately
        loop._check_lint = AsyncMock(return_value=(True, []))

        test_file = tmp_workspace / "test.py"
        events = [e async for e in loop.run([test_file])]

        assert loop.result is not None
        assert loop.result.status == ConvergenceStatus.STABLE
        assert loop.result.iteration_count == 1

    @pytest.mark.asyncio
    async def test_emits_start_event(self, mock_model, tmp_workspace):
        """Should emit convergence_start event."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(
            model=mock_model,
            cwd=tmp_workspace,
            config=config,
        )
        loop._check_lint = AsyncMock(return_value=(True, []))

        test_file = tmp_workspace / "test.py"
        events = [e async for e in loop.run([test_file])]

        start_events = [e for e in events if e.type == EventType.CONVERGENCE_START]
        assert len(start_events) == 1
        assert "files" in start_events[0].data
        assert "gates" in start_events[0].data

    @pytest.mark.asyncio
    async def test_emits_stable_event(self, mock_model, tmp_workspace):
        """Should emit convergence_stable event on success."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(
            model=mock_model,
            cwd=tmp_workspace,
            config=config,
        )
        loop._check_lint = AsyncMock(return_value=(True, []))

        test_file = tmp_workspace / "test.py"
        events = [e async for e in loop.run([test_file])]

        stable_events = [e for e in events if e.type == EventType.CONVERGENCE_STABLE]
        assert len(stable_events) == 1
        assert "iterations" in stable_events[0].data

    @pytest.mark.asyncio
    async def test_escalates_on_max_iterations(self, mock_model, tmp_workspace):
        """Should escalate if max iterations reached."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=3,
            escalate_after_same_error=10,  # High to prevent stuck detection
        )
        loop = ConvergenceLoop(
            model=mock_model,
            cwd=tmp_workspace,
            config=config,
        )

        # Mock: always fail
        loop._check_lint = AsyncMock(return_value=(False, ["persistent error"]))
        
        # Mock fixer to be an async generator that yields nothing
        async def mock_fix_errors(*args, **kwargs):
            return
            yield  # Makes this an async generator
        
        loop._fixer.fix_errors = mock_fix_errors

        test_file = tmp_workspace / "test.py"
        events = [e async for e in loop.run([test_file])]

        assert loop.result is not None
        assert loop.result.status == ConvergenceStatus.ESCALATED
        assert loop.result.iteration_count == 3

    @pytest.mark.asyncio
    async def test_emits_iteration_events(self, mock_model, tmp_workspace):
        """Should emit iteration start and complete events."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            max_iterations=5,
        )
        loop = ConvergenceLoop(
            model=mock_model,
            cwd=tmp_workspace,
            config=config,
        )
        loop._check_lint = AsyncMock(return_value=(True, []))

        test_file = tmp_workspace / "test.py"
        events = [e async for e in loop.run([test_file])]

        iter_start = [e for e in events if e.type == EventType.CONVERGENCE_ITERATION_START]
        iter_complete = [e for e in events if e.type == EventType.CONVERGENCE_ITERATION_COMPLETE]

        assert len(iter_start) >= 1
        assert len(iter_complete) >= 1


class TestConvergenceLoopGateChecks:
    """Tests for individual gate check methods."""

    @pytest.mark.asyncio
    async def test_check_syntax_valid(self, mock_model, tmp_workspace):
        """Should pass for valid Python syntax."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        
        test_file = tmp_workspace / "valid.py"
        test_file.write_text("x = 1\nprint(x)\n")

        passed, errors = await loop._check_syntax([test_file])
        assert passed is True
        assert errors == []

    @pytest.mark.asyncio
    async def test_check_syntax_invalid(self, mock_model, tmp_workspace):
        """Should fail for invalid Python syntax."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        
        test_file = tmp_workspace / "invalid.py"
        test_file.write_text("def broken(\n")

        passed, errors = await loop._check_syntax([test_file])
        assert passed is False
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_check_syntax_skips_non_python(self, mock_model, tmp_workspace):
        """Should skip non-Python files."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        
        test_file = tmp_workspace / "data.json"
        test_file.write_text('{"key": "value"}')

        passed, errors = await loop._check_syntax([test_file])
        assert passed is True


class TestConvergenceLoopStuckDetection:
    """Tests for stuck error detection."""

    def test_check_stuck_errors_false_initially(self, mock_model, tmp_workspace):
        """Should not detect stuck errors initially."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        
        results = [
            MagicMock(gate=GateType.LINT, errors=("E501",)),
        ]
        
        assert loop._check_stuck_errors(results) is False

    def test_check_stuck_errors_after_threshold(self, mock_model, tmp_workspace):
        """Should detect stuck after threshold repetitions."""
        config = ConvergenceConfig(escalate_after_same_error=2)
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace, config=config)
        
        # Simulate error history
        loop._error_history["lint:E501 line too long"] = 2
        
        results = [
            MagicMock(gate=GateType.LINT, errors=("E501 line too long",)),
        ]
        
        assert loop._check_stuck_errors(results) is True


class TestConvergenceLoopTimeout:
    """Tests for timeout handling."""

    def test_elapsed_ms(self, mock_model, tmp_workspace):
        """Should track elapsed time."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace)
        loop._start_time = 0
        
        # Elapsed should be calculated from start time
        with patch("time.monotonic", return_value=1.5):
            assert loop._elapsed_ms() == 1500

    def test_check_timeout(self, mock_model, tmp_workspace):
        """Should detect timeout correctly."""
        config = ConvergenceConfig(timeout_seconds=10)
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_workspace, config=config)
        loop._start_time = 0
        
        with patch("time.monotonic", return_value=5):
            assert loop._check_timeout() is False
        
        with patch("time.monotonic", return_value=15):
            assert loop._check_timeout() is True
