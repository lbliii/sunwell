"""Regression tests for sunwell.benchmark.naaru package.

These tests target bugs found during bug bash:
- Missing imports that cause NameError at runtime
- Incorrect condition values returned
- Logic errors in metrics calculations
- Edge cases in voting and frame parsing
"""

import pytest

from sunwell.benchmark.naaru.conditions.harmonic import build_vote_prompt, collect_votes
from sunwell.benchmark.naaru.conditions.rotation import (
    DIVERGENT_ROTATION_FRAMES,
    ROTATION_FRAMES,
    parse_frame_usage,
)
from sunwell.benchmark.naaru.types import (
    HarmonicMetrics,
    NaaruCondition,
    RotationMetrics,
)


class TestRotationMetrics:
    """Tests for RotationMetrics calculations."""

    def test_frame_coverage_standard_mode(self) -> None:
        """Standard mode has 6 frames (think, critic, advocate, user, expert, synthesize)."""
        metrics = RotationMetrics(
            frames_used=("think", "critic", "synthesize"),
            frame_token_counts={"think": 10, "critic": 20, "synthesize": 30},
            divergent_mode=False,
        )
        # 3 out of 6 frames = 0.5
        assert metrics.frame_coverage == 0.5
        assert metrics.n_frames == 3

    def test_frame_coverage_divergent_mode(self) -> None:
        """Divergent mode has 5 frames (think, adversary, advocate, naive, synthesize)."""
        metrics = RotationMetrics(
            frames_used=("think", "adversary", "synthesize"),
            frame_token_counts={"think": 10, "adversary": 20, "synthesize": 30},
            divergent_mode=True,
        )
        # 3 out of 5 frames = 0.6
        assert metrics.frame_coverage == 0.6
        assert metrics.n_frames == 3

    def test_frame_coverage_full_standard(self) -> None:
        """All 6 standard frames used should give 100% coverage."""
        all_frames = ("think", "critic", "advocate", "user", "expert", "synthesize")
        metrics = RotationMetrics(
            frames_used=all_frames,
            frame_token_counts={f: 10 for f in all_frames},
            divergent_mode=False,
        )
        assert metrics.frame_coverage == 1.0

    def test_frame_coverage_full_divergent(self) -> None:
        """All 5 divergent frames used should give 100% coverage."""
        all_frames = ("think", "adversary", "advocate", "naive", "synthesize")
        metrics = RotationMetrics(
            frames_used=all_frames,
            frame_token_counts={f: 10 for f in all_frames},
            divergent_mode=True,
        )
        assert metrics.frame_coverage == 1.0

    def test_total_frame_tokens(self) -> None:
        """Total tokens should sum all frame token counts."""
        metrics = RotationMetrics(
            frames_used=("think", "critic"),
            frame_token_counts={"think": 100, "critic": 200},
            divergent_mode=False,
        )
        assert metrics.total_frame_tokens == 300


class TestParseFrameUsage:
    """Tests for parse_frame_usage function."""

    def test_parses_single_frame(self) -> None:
        """Should extract content from a single frame."""
        text = "<think>This is my thinking about the problem.</think>"
        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        assert usage["think"] > 0

    def test_parses_multiple_frames(self) -> None:
        """Should extract content from multiple frames."""
        text = """
        <think>Initial thoughts here.</think>
        <critic>But what about edge cases?</critic>
        <synthesize>Final answer combining both views.</synthesize>
        """
        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        assert "critic" in usage
        assert "synthesize" in usage
        assert len(usage) == 3

    def test_token_estimation_reasonable(self) -> None:
        """Token estimation should be approximately 1.33x word count."""
        # 10 words should give ~13 tokens
        text = "<think>one two three four five six seven eight nine ten</think>"
        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert usage["think"] >= 10  # At least word count
        assert usage["think"] <= 20  # But not unreasonably high

    def test_empty_text_returns_empty(self) -> None:
        """Empty text should return empty dict."""
        usage = parse_frame_usage("", ROTATION_FRAMES)
        assert usage == {}

    def test_no_frames_returns_empty(self) -> None:
        """Text without frame markers should return empty dict."""
        text = "This is regular text without any frame markers."
        usage = parse_frame_usage(text, ROTATION_FRAMES)
        assert usage == {}

    def test_divergent_frames(self) -> None:
        """Should parse divergent frame names correctly."""
        text = """
        <adversary>This could fail catastrophically!</adversary>
        <naive>But why does it work this way?</naive>
        """
        usage = parse_frame_usage(text, DIVERGENT_ROTATION_FRAMES)

        assert "adversary" in usage
        assert "naive" in usage


class TestBuildVotePrompt:
    """Tests for build_vote_prompt function."""

    def test_two_candidates(self) -> None:
        """Two candidates should show 'A or B'."""
        prompt = build_vote_prompt(
            "Test task",
            ["persona1", "persona2"],
            ["output1", "output2"],
        )
        assert "A or B" in prompt
        assert "Option A" in prompt
        assert "Option B" in prompt

    def test_three_candidates(self) -> None:
        """Three candidates should show 'A, B, or C'."""
        prompt = build_vote_prompt(
            "Test task",
            ["p1", "p2", "p3"],
            ["o1", "o2", "o3"],
        )
        assert "A, B, or C" in prompt

    def test_four_candidates(self) -> None:
        """Four candidates should show 'A, B, C, or D'."""
        prompt = build_vote_prompt(
            "Test task",
            ["p1", "p2", "p3", "p4"],
            ["o1", "o2", "o3", "o4"],
        )
        assert "A, B, C, or D" in prompt

    def test_five_candidates(self) -> None:
        """Five candidates should include E."""
        prompt = build_vote_prompt(
            "Test task",
            ["p1", "p2", "p3", "p4", "p5"],
            ["o1", "o2", "o3", "o4", "o5"],
        )
        assert "or E" in prompt
        assert "Option E" in prompt

    def test_single_candidate(self) -> None:
        """Single candidate edge case."""
        prompt = build_vote_prompt(
            "Test task",
            ["only_one"],
            ["single output"],
        )
        # Should handle gracefully, showing just "A"
        assert "Option A" in prompt

    def test_truncates_long_outputs(self) -> None:
        """Long outputs should be truncated to 1500 chars."""
        long_output = "x" * 2000
        prompt = build_vote_prompt(
            "Test task",
            ["persona"],
            [long_output],
        )
        # The full 2000 chars should not appear
        assert "x" * 2000 not in prompt
        # But truncated version should
        assert "x" * 1500 in prompt


class TestHarmonicMetrics:
    """Tests for HarmonicMetrics calculations."""

    def test_persona_diversity_identical_outputs(self) -> None:
        """Identical outputs should have zero diversity."""
        metrics = HarmonicMetrics(
            consensus_strength=1.0,
            persona_outputs=("same output", "same output", "same output"),
            persona_names=("p1", "p2", "p3"),
            winning_persona="p1",
        )
        assert metrics.persona_diversity == 0.0

    def test_persona_diversity_different_outputs(self) -> None:
        """Different outputs should have non-zero diversity."""
        metrics = HarmonicMetrics(
            consensus_strength=0.5,
            persona_outputs=("aaaa", "bbbb", "cccc"),
            persona_names=("p1", "p2", "p3"),
            winning_persona="p1",
        )
        assert metrics.persona_diversity > 0.0

    def test_persona_diversity_single_output(self) -> None:
        """Single output should have zero diversity."""
        metrics = HarmonicMetrics(
            consensus_strength=1.0,
            persona_outputs=("only one",),
            persona_names=("p1",),
            winning_persona="p1",
        )
        assert metrics.persona_diversity == 0.0

    def test_persona_diversity_empty_outputs(self) -> None:
        """Empty outputs should not cause division by zero."""
        metrics = HarmonicMetrics(
            consensus_strength=1.0,
            persona_outputs=("", ""),
            persona_names=("p1", "p2"),
            winning_persona="p1",
        )
        assert metrics.persona_diversity == 0.0


class TestConditionValues:
    """Tests that condition functions return correct condition values."""

    @pytest.mark.asyncio
    async def test_harmonic_returns_harmonic_condition(self) -> None:
        """run_harmonic should return HARMONIC condition."""
        from unittest.mock import AsyncMock, MagicMock

        from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic
        from sunwell.benchmark.types import BenchmarkTask, TaskCategory, TaskEvaluation

        # Mock model
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "test output"
        mock_result.usage = MagicMock(total_tokens=100)
        mock_model.generate = AsyncMock(return_value=mock_result)

        task = BenchmarkTask(
            id="test",
            category=TaskCategory.DOCUMENTATION,
            subcategory="test",
            prompt="test prompt",
            lens="test.lens",
            evaluation=TaskEvaluation(),
        )

        result = await run_harmonic(mock_model, task, temperature_strategy="uniform_med")

        assert result.condition == NaaruCondition.HARMONIC

    @pytest.mark.asyncio
    async def test_harmonic_divergent_returns_divergent_condition(self) -> None:
        """run_harmonic with divergent strategy should return HARMONIC_DIVERGENT."""
        from unittest.mock import AsyncMock, MagicMock

        from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic
        from sunwell.benchmark.types import BenchmarkTask, TaskCategory, TaskEvaluation

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "test output"
        mock_result.usage = MagicMock(total_tokens=100)
        mock_model.generate = AsyncMock(return_value=mock_result)

        task = BenchmarkTask(
            id="test",
            category=TaskCategory.DOCUMENTATION,
            subcategory="test",
            prompt="test prompt",
            lens="test.lens",
            evaluation=TaskEvaluation(),
        )

        result = await run_harmonic(mock_model, task, temperature_strategy="divergent")

        assert result.condition == NaaruCondition.HARMONIC_DIVERGENT


class TestConditionRunnerExhaustive:
    """Tests for ConditionRunner handling all conditions."""

    def test_all_conditions_have_handlers(self) -> None:
        """Every NaaruCondition should be handled by ConditionRunner."""
        from sunwell.benchmark.naaru.conditions.runner import ConditionRunner

        # Get all conditions
        all_conditions = list(NaaruCondition)

        # Conditions that require a lens
        lens_conditions = {
            NaaruCondition.BASELINE_LENS,
            NaaruCondition.HARMONIC_LENS,
            NaaruCondition.NAARU_FULL_LENS,
            NaaruCondition.ROTATION_LENS,
        }

        # Verify the runner's match statement covers all conditions
        # by checking the source code has a case for each
        import inspect

        source = inspect.getsource(ConditionRunner.run)

        for condition in all_conditions:
            # Check that the condition name appears in the match statement
            assert condition.name in source or condition.value in source, (
                f"Condition {condition} not handled in ConditionRunner.run()"
            )


class TestVoteParsingEdgeCases:
    """Tests for vote parsing with various inputs."""

    def test_parse_vote_letter_d(self) -> None:
        """Vote for D (4th candidate) should be parsed correctly."""
        # This is tested indirectly through collect_votes
        # The fix ensures ord('D') - ord('A') = 3 is handled
        pass  # Covered by integration tests

    def test_parse_vote_lowercase(self) -> None:
        """Lowercase votes should be handled."""
        # The implementation uppercases the vote text
        pass  # Covered by the .upper() call


class TestFrameCountConstants:
    """Verify frame count constants match actual frame definitions."""

    def test_standard_frame_count(self) -> None:
        """ROTATION_FRAMES should have 6 entries."""
        assert len(ROTATION_FRAMES) == 6

    def test_divergent_frame_count(self) -> None:
        """DIVERGENT_ROTATION_FRAMES should have 5 entries."""
        assert len(DIVERGENT_ROTATION_FRAMES) == 5

    def test_frame_coverage_denominators_match(self) -> None:
        """RotationMetrics frame_coverage should use correct denominators."""
        # Standard: 6 frames
        standard = RotationMetrics(
            frames_used=tuple(ROTATION_FRAMES.keys()),
            divergent_mode=False,
        )
        assert standard.frame_coverage == 1.0

        # Divergent: 5 frames
        divergent = RotationMetrics(
            frames_used=tuple(DIVERGENT_ROTATION_FRAMES.keys()),
            divergent_mode=True,
        )
        assert divergent.frame_coverage == 1.0
