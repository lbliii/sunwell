"""Integration tests for ExecutionManager.

Tests cover:
- Manager initialization
- ExecutionResult and DagContext dataclasses
- Event emission
- Artifact tracking
- Duration recording
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sunwell.agent.execution.manager import DagContext, ExecutionManager, ExecutionResult


# =============================================================================
# ExecutionResult Tests
# =============================================================================


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    @pytest.mark.integration
    def test_execution_result_dataclass(self) -> None:
        """ExecutionResult fields correct."""
        result = ExecutionResult(
            success=True,
            goal_id="goal-123",
            artifacts_created=("file1.py", "file2.py"),
            artifacts_failed=(),
            artifacts_skipped=("cached.py",),
            error=None,
            duration_ms=1500,
            learnings_count=3,
        )

        assert result.success is True
        assert result.goal_id == "goal-123"
        assert result.artifacts_created == ("file1.py", "file2.py")
        assert result.artifacts_failed == ()
        assert result.artifacts_skipped == ("cached.py",)
        assert result.error is None
        assert result.duration_ms == 1500
        assert result.learnings_count == 3

    @pytest.mark.integration
    def test_execution_result_with_error(self) -> None:
        """ExecutionResult captures error correctly."""
        result = ExecutionResult(
            success=False,
            goal_id="goal-456",
            artifacts_created=(),
            artifacts_failed=("broken.py",),
            error="TypeError: invalid argument",
            duration_ms=500,
        )

        assert result.success is False
        assert result.error == "TypeError: invalid argument"
        assert result.artifacts_failed == ("broken.py",)

    @pytest.mark.integration
    def test_execution_result_defaults(self) -> None:
        """ExecutionResult has sensible defaults."""
        result = ExecutionResult(
            success=True,
            goal_id="goal-789",
            artifacts_created=("file.py",),
            artifacts_failed=(),
        )

        # Check defaults
        assert result.artifacts_skipped == ()
        assert result.error is None
        assert result.duration_ms == 0
        assert result.learnings_count == 0


# =============================================================================
# DagContext Tests
# =============================================================================


class TestDagContext:
    """Tests for DagContext dataclass."""

    @pytest.mark.integration
    def test_dag_context_dataclass(self) -> None:
        """DagContext fields correct."""
        ctx = DagContext(
            total_goals=5,
            completed_goals=3,
            total_artifacts=10,
            previous_goals=("goal-1", "goal-2", "goal-3"),
            previous_artifacts=frozenset({"a.py", "b.py"}),
            learnings=("Use async", "Add tests"),
        )

        assert ctx.total_goals == 5
        assert ctx.completed_goals == 3
        assert ctx.total_artifacts == 10
        assert ctx.previous_goals == ("goal-1", "goal-2", "goal-3")
        assert "a.py" in ctx.previous_artifacts
        assert ctx.learnings == ("Use async", "Add tests")

    @pytest.mark.integration
    def test_dag_context_defaults(self) -> None:
        """DagContext has sensible defaults."""
        ctx = DagContext()

        assert ctx.total_goals == 0
        assert ctx.completed_goals == 0
        assert ctx.total_artifacts == 0
        assert ctx.previous_goals == ()
        assert ctx.previous_artifacts == frozenset()
        assert ctx.learnings == ()


# =============================================================================
# ExecutionManager Tests
# =============================================================================


class TestExecutionManager:
    """Tests for ExecutionManager."""

    @pytest.mark.integration
    def test_manager_initializes_with_workspace(self, tmp_path: Path) -> None:
        """Creates with root path."""
        manager = ExecutionManager(root=tmp_path)

        assert manager.root == tmp_path

    @pytest.mark.integration
    def test_manager_accepts_emitter(self, tmp_path: Path) -> None:
        """Manager accepts event emitter."""
        mock_emitter = MagicMock()

        manager = ExecutionManager(root=tmp_path, emitter=mock_emitter)

        assert manager.root == tmp_path
        # Emitter should be stored (implementation detail)

    @pytest.mark.integration
    def test_manager_accepts_cache_path(self, tmp_path: Path) -> None:
        """Manager accepts custom cache path."""
        cache_dir = tmp_path / "custom_cache"
        cache_dir.mkdir()

        manager = ExecutionManager(root=tmp_path, cache_path=cache_dir)

        assert manager.root == tmp_path
