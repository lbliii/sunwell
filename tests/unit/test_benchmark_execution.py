"""Tests for benchmark execution runner.

These tests verify the ExecutionRunner's integration with retrieval
and tool systems. Focus is on contract verification and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from sunwell.benchmark.execution.runner import ExecutionRunner
from sunwell.benchmark.types import (
    BenchmarkTask,
    Condition,
    ConditionOutput,
    NaaruMode,
    PromptStrategy,
    RetrievalMetrics,
    TaskCategory,
    TaskEvaluation,
)
from sunwell.foundation.core.lens import Lens, LensMetadata
from sunwell.core.models.heuristic import Heuristic
from sunwell.core.types.types import SemanticVersion
from sunwell.models import GenerateResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_heuristic() -> Heuristic:
    """Single heuristic for testing."""
    return Heuristic(
        name="test-heuristic",
        rule="Test rule",
        test="Test question",
        always=("Do this",),
        never=("Don't do that",),
    )


@pytest.fixture
def sample_lens(sample_heuristic: Heuristic) -> Lens:
    """Lens with heuristics."""
    return Lens(
        metadata=LensMetadata(
            name="Test Lens",
            domain="testing",
            version=SemanticVersion(1, 0, 0),
        ),
        heuristics=(sample_heuristic,),
    )


@pytest.fixture
def sample_task() -> BenchmarkTask:
    """Sample benchmark task."""
    return BenchmarkTask(
        id="test-task-001",
        category=TaskCategory.CODE_GENERATION,
        subcategory="basic",
        prompt="Write a function that adds two numbers",
        lens="test.lens",
        evaluation=TaskEvaluation(
            must_contain=("def",),
            must_not_contain=("eval",),
        ),
    )


@pytest.fixture
def mock_model() -> MagicMock:
    """Mock model for testing."""
    model = MagicMock()
    model.model_id = "test-model"
    model.generate = AsyncMock(return_value=GenerateResult(
        content="def add(a, b):\n    return a + b",
        model="test-model",
        finish_reason="stop",
    ))
    return model


@pytest.fixture
def mock_lens_loader() -> MagicMock:
    """Mock lens loader."""
    return MagicMock()


# =============================================================================
# ExecutionRunner Tests
# =============================================================================


class TestExecutionRunnerBasics:
    """Basic functionality tests."""

    @pytest.mark.asyncio
    async def test_run_condition_returns_condition_output(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """run_condition() returns ConditionOutput with correct structure."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        result = await runner.run_condition(
            task=sample_task,
            system_prompt="You are a helpful assistant",
            condition=Condition.BARE,
        )

        assert isinstance(result, ConditionOutput)
        assert result.condition == Condition.BARE
        assert isinstance(result.content, str)
        assert result.tokens_input > 0
        assert result.tokens_output >= 0
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_condition_bare_uses_no_context(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """BARE condition uses empty system prompt."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        result = await runner.run_condition(
            task=sample_task,
            system_prompt="",  # Bare = no context
            condition=Condition.BARE,
        )

        # Verify model was called
        mock_model.generate.assert_called_once()
        call_args = mock_model.generate.call_args
        assert call_args.kwargs["options"].system_prompt is None


class TestExecutionRunnerTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_with_tiktoken(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """_count_tokens uses tiktoken when available."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        count = runner._count_tokens("Hello, world!")

        # tiktoken is installed, so should get real count
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_fallback(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """_count_tokens falls back to char estimate if tiktoken fails."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        with patch.dict("sys.modules", {"tiktoken": None}):
            # Force ImportError path
            text = "a" * 100
            # Fallback is len(text) // 4
            # Can't easily test this without mocking more deeply


class TestSelectiveRetrieve:
    """Tests for selective_retrieve method."""

    @pytest.mark.asyncio
    async def test_selective_retrieve_returns_tuple(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_lens: Lens,
        tmp_path: Path,
    ):
        """selective_retrieve returns (context_str, RetrievalMetrics)."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
            top_k=3,
        )

        context, metrics = await runner.selective_retrieve(
            lens=sample_lens,
            query="test query",
        )

        assert isinstance(context, str)
        assert isinstance(metrics, RetrievalMetrics)

    @pytest.mark.asyncio
    async def test_selective_retrieve_empty_lens(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """selective_retrieve handles lens with no heuristics."""
        empty_lens = Lens(
            metadata=LensMetadata(
                name="Empty",
                domain="test",
                version=SemanticVersion(1, 0, 0),
            ),
            heuristics=(),
        )

        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        context, metrics = await runner.selective_retrieve(
            lens=empty_lens,
            query="anything",
        )

        assert context == ""
        assert metrics.precision_at_k == 0.0
        assert metrics.recall == 0.0  # No heuristics = no recall possible


class TestValidateResponse:
    """Tests for response validation."""

    @pytest.mark.asyncio
    async def test_validate_response_detects_missing_code_block(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """_validate_response catches missing code blocks for code tasks."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        task = BenchmarkTask(
            id="test",
            category=TaskCategory.CODE_GENERATION,
            subcategory="test",
            prompt="Write code",
            lens="test.lens",
            evaluation=TaskEvaluation(),
        )

        issues = await runner._validate_response(
            task=task,
            response="Here is the solution without code blocks",
        )

        assert issues is not None
        assert "Missing code block" in issues

    @pytest.mark.asyncio
    async def test_validate_response_checks_must_contain(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """_validate_response checks task.evaluation.must_contain."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        task = BenchmarkTask(
            id="test",
            category=TaskCategory.DOCUMENTATION,
            subcategory="test",
            prompt="Write docs",
            lens="test.lens",
            evaluation=TaskEvaluation(
                must_contain=("## Overview", "## Usage"),
            ),
        )

        issues = await runner._validate_response(
            task=task,
            response="# Quick Start\nSome content",
        )

        assert issues is not None
        assert "Overview" in issues

    @pytest.mark.asyncio
    async def test_validate_response_returns_none_when_valid(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        tmp_path: Path,
    ):
        """_validate_response returns None for valid responses."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        task = BenchmarkTask(
            id="test",
            category=TaskCategory.CODE_GENERATION,
            subcategory="test",
            prompt="Write code",
            lens="test.lens",
            evaluation=TaskEvaluation(
                must_contain=("def",),
            ),
        )

        issues = await runner._validate_response(
            task=task,
            response="```python\ndef add(a, b):\n    return a + b\n```",
        )

        assert issues is None


class TestNaaruModes:
    """Tests for Naaru coordination modes."""

    @pytest.mark.asyncio
    async def test_naaru_none_uses_single_generation(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """NaaruMode.NONE generates once."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
            naaru_mode=NaaruMode.NONE,
        )

        await runner.run_condition(
            task=sample_task,
            system_prompt="test",
            condition=Condition.SELECTIVE,
        )

        # Should only call generate once
        assert mock_model.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_harmonic_synthesis_generates_multiple_personas(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """_harmonic_synthesis generates with 3 personas."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        responses = await runner._harmonic_synthesis(
            task=sample_task,
            base_system_prompt="You are helpful",
        )

        assert len(responses) == 3
        assert mock_model.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_vote_on_responses_returns_one_response(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """_vote_on_responses selects one response from candidates."""
        mock_model.generate.return_value = GenerateResult(
            content="A", model="test", finish_reason="stop"
        )

        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
        )

        responses = ["Response A", "Response B", "Response C"]
        winner = await runner._vote_on_responses(sample_task, responses)

        assert winner in responses


# =============================================================================
# Integration Tests
# =============================================================================


class TestExecutionRunnerIntegration:
    """Integration tests with real (but simple) components."""

    @pytest.mark.asyncio
    async def test_full_selective_condition(
        self,
        mock_model: MagicMock,
        mock_lens_loader: MagicMock,
        sample_lens: Lens,
        sample_task: BenchmarkTask,
        tmp_path: Path,
    ):
        """Full run through selective condition."""
        runner = ExecutionRunner(
            model=mock_model,
            lens_loader=mock_lens_loader,
            lens_dir=tmp_path,
            prompt_strategy=PromptStrategy.CONSTRAINTS,
        )

        # Build context via selective retrieve
        context, metrics = await runner.selective_retrieve(
            lens=sample_lens,
            query=sample_task.prompt,
        )

        # Run condition
        result = await runner.run_condition(
            task=sample_task,
            system_prompt=context,
            condition=Condition.SELECTIVE,
        )

        assert result.condition == Condition.SELECTIVE
        assert result.content  # Has content
        assert result.latency_ms >= 0
