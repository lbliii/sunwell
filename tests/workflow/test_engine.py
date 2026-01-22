"""Tests for WorkflowEngine (RFC-086)."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from sunwell.workflow import (
    WorkflowEngine,
    WorkflowResult,
    WorkflowChain,
    WorkflowStep,
    WorkflowExecution,
    WorkflowTier,
)
from sunwell.workflow.engine import WriterContext


class TestWorkflowEngine:
    """Test WorkflowEngine execution."""

    @pytest.fixture
    def state_dir(self) -> Path:
        """Create a temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def simple_chain(self) -> WorkflowChain:
        """Create a simple test chain."""
        return WorkflowChain(
            name="test-chain",
            description="A test workflow chain",
            steps=(
                WorkflowStep(skill="step-1", purpose="First step"),
                WorkflowStep(skill="step-2", purpose="Second step"),
                WorkflowStep(skill="step-3", purpose="Third step"),
            ),
            checkpoint_after=(),
            tier=WorkflowTier.FAST,
        )

    @pytest.fixture
    def context(self, state_dir: Path) -> WriterContext:
        """Create a test context."""
        return WriterContext(
            lens=None,
            target_file=None,
            working_dir=state_dir,
        )

    @pytest.mark.asyncio
    async def test_execute_simple_chain(
        self,
        state_dir: Path,
        simple_chain: WorkflowChain,
        context: WriterContext,
    ) -> None:
        """Test executing a simple chain without checkpoints."""
        engine = WorkflowEngine(state_dir=state_dir)
        result = await engine.execute(simple_chain, context)

        assert result.status == "completed"
        assert len(result.execution.completed_steps) == 3
        # All steps completed successfully
        assert all(s.status == "success" for s in result.execution.completed_steps)

    @pytest.mark.asyncio
    async def test_execution_generates_id(
        self,
        state_dir: Path,
        simple_chain: WorkflowChain,
        context: WriterContext,
    ) -> None:
        """Test that execution generates a unique ID."""
        engine = WorkflowEngine(state_dir=state_dir)
        result = await engine.execute(simple_chain, context)

        assert result.execution.id.startswith("wf-")
        assert simple_chain.name in result.execution.id

    @pytest.mark.asyncio
    async def test_step_results_tracked(
        self,
        state_dir: Path,
        simple_chain: WorkflowChain,
        context: WriterContext,
    ) -> None:
        """Test that step results are properly tracked."""
        engine = WorkflowEngine(state_dir=state_dir)
        result = await engine.execute(simple_chain, context)

        for step_result in result.execution.completed_steps:
            assert step_result.status == "success"
            assert step_result.started_at is not None
            assert step_result.completed_at is not None
            assert step_result.duration_s is not None
            assert step_result.duration_s >= 0

    @pytest.mark.asyncio
    async def test_execution_progress(
        self,
        state_dir: Path,
        simple_chain: WorkflowChain,
        context: WriterContext,
    ) -> None:
        """Test that progress is tracked correctly."""
        engine = WorkflowEngine(state_dir=state_dir)
        result = await engine.execute(simple_chain, context)

        # After completion, all steps should be done
        assert len(result.execution.completed_steps) == len(simple_chain.steps)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_pause_and_resume(
        self,
        state_dir: Path,
        context: WriterContext,
    ) -> None:
        """Test pausing and resuming a workflow."""
        # Create a chain with checkpoints
        chain = WorkflowChain(
            name="checkpoint-chain",
            description="Chain with checkpoints",
            steps=(
                WorkflowStep(skill="step-1", purpose="First step"),
                WorkflowStep(skill="step-2", purpose="Second step"),
                WorkflowStep(skill="step-3", purpose="Third step"),
            ),
            checkpoint_after=(0,),  # Checkpoint after first step
            tier=WorkflowTier.FULL,
        )

        engine = WorkflowEngine(state_dir=state_dir)

        # Mock _confirm_continue to return False (pause)
        async def mock_confirm(_):
            return False

        engine._confirm_continue = mock_confirm  # type: ignore

        result = await engine.execute(chain, context)

        # Should be paused after first step
        assert result.status == "paused"
        assert len(result.execution.completed_steps) == 1


class TestWorkflowChain:
    """Test WorkflowChain dataclass."""

    def test_chain_creation(self) -> None:
        """Test creating a workflow chain."""
        chain = WorkflowChain(
            name="test",
            description="Test chain",
            steps=(
                WorkflowStep(skill="s1", purpose="p1"),
                WorkflowStep(skill="s2", purpose="p2"),
            ),
        )

        assert chain.name == "test"
        assert len(chain.steps) == 2
        assert chain.tier == WorkflowTier.LIGHT

    def test_chain_with_checkpoints(self) -> None:
        """Test chain with checkpoint configuration."""
        chain = WorkflowChain(
            name="test",
            description="Test",
            steps=(
                WorkflowStep(skill="s1", purpose="p1"),
                WorkflowStep(skill="s2", purpose="p2"),
                WorkflowStep(skill="s3", purpose="p3"),
            ),
            checkpoint_after=(0, 1),
        )

        assert 0 in chain.checkpoint_after
        assert 1 in chain.checkpoint_after
        assert 2 not in chain.checkpoint_after


class TestWorkflowExecution:
    """Test WorkflowExecution dataclass."""

    def test_execution_progress(self) -> None:
        """Test progress calculation."""
        chain = WorkflowChain(
            name="test",
            description="Test",
            steps=(
                WorkflowStep(skill="s1", purpose="p1"),
                WorkflowStep(skill="s2", purpose="p2"),
            ),
        )

        execution = WorkflowExecution(
            id="test-123",
            chain=chain,
            current_step=1,
        )

        assert execution.progress_pct == 50.0

    def test_execution_is_complete(self) -> None:
        """Test is_complete property."""
        chain = WorkflowChain(
            name="test",
            description="Test",
            steps=(
                WorkflowStep(skill="s1", purpose="p1"),
            ),
        )

        execution = WorkflowExecution(
            id="test-123",
            chain=chain,
            current_step=0,
        )
        assert not execution.is_complete

        execution.current_step = 1
        assert execution.is_complete

    def test_execution_to_dict(self) -> None:
        """Test serialization to dictionary."""
        chain = WorkflowChain(
            name="test",
            description="Test",
            steps=(
                WorkflowStep(skill="s1", purpose="p1"),
            ),
        )

        execution = WorkflowExecution(
            id="test-123",
            chain=chain,
        )

        data = execution.to_dict()

        assert data["id"] == "test-123"
        assert data["chain"] == "test"
        assert data["current_step"] == 0
        assert data["total_steps"] == 1
        assert "started_at" in data
        assert "updated_at" in data
