"""Tests for AwarenessPattern dataclass."""

import pytest

from sunwell.awareness.patterns import (
    AwarenessPattern,
    PatternType,
    format_patterns_for_prompt,
)


class TestAwarenessPattern:
    """Tests for the AwarenessPattern dataclass."""

    def test_create_confidence_pattern(self) -> None:
        """Test creating a confidence calibration pattern."""
        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I tend to overstate confidence on refactoring tasks",
            metric=0.20,
            sample_size=10,
            context="refactoring",
        )

        assert pattern.pattern_type == PatternType.CONFIDENCE
        assert pattern.metric == 0.20
        assert pattern.sample_size == 10
        assert pattern.context == "refactoring"
        assert "overstate" in pattern.observation

    def test_pattern_id_is_deterministic(self) -> None:
        """Same type + context should produce same ID."""
        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I overstate confidence",
            metric=0.20,
            sample_size=10,
            context="refactoring",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="Different observation",
            metric=0.50,
            sample_size=5,
            context="refactoring",  # Same context
        )

        # Same type + context = same ID (for deduplication)
        assert p1.id == p2.id

    def test_different_context_different_id(self) -> None:
        """Different context should produce different ID."""
        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I overstate confidence",
            metric=0.20,
            sample_size=10,
            context="refactoring",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I overstate confidence",
            metric=0.20,
            sample_size=10,
            context="testing",  # Different context
        )

        assert p1.id != p2.id

    def test_confidence_scales_with_samples(self) -> None:
        """Confidence should increase with sample size."""
        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=3,
            context="test",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=10,
            context="test",
        )

        assert p2.confidence > p1.confidence
        assert p1.confidence >= 0.5  # Minimum with samples

    def test_confidence_caps_at_95(self) -> None:
        """Confidence should cap at 0.95."""
        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=100,  # Many samples
            context="test",
        )

        assert pattern.confidence == 0.95

    def test_is_significant_requires_min_samples(self) -> None:
        """Pattern needs at least 3 samples to be significant."""
        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,  # Above threshold
            sample_size=2,  # Below minimum
            context="test",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=3,  # At minimum
            context="test",
        )

        assert not p1.is_significant
        assert p2.is_significant

    def test_is_significant_requires_min_metric(self) -> None:
        """Pattern needs metric above threshold to be significant."""
        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.05,  # Below 10% threshold
            sample_size=10,
            context="test",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.15,  # Above threshold
            sample_size=10,
            context="test",
        )

        assert not p1.is_significant
        assert p2.is_significant

    def test_to_prompt_line_includes_metric(self) -> None:
        """Prompt line should include metric context."""
        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I overstate confidence on refactoring",
            metric=0.20,
            sample_size=10,
            context="refactoring",
        )

        line = pattern.to_prompt_line()
        assert "I overstate confidence on refactoring" in line
        assert "20%" in line

    def test_with_reinforcement_merges_stats(self) -> None:
        """Reinforcement should combine samples and average metrics."""
        original = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=10,
            context="test",
        )

        reinforced = original.with_reinforcement(new_metric=0.30, new_samples=10)

        # Should combine samples
        assert reinforced.sample_size == 20
        # Should average metrics (weighted)
        assert reinforced.metric == pytest.approx(0.25)
        # Should increment reinforcement count
        assert reinforced.reinforcement_count == 1

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """Pattern should survive serialization roundtrip."""
        original = AwarenessPattern(
            pattern_type=PatternType.TOOL_AVOIDANCE,
            observation="I under-utilize grep_search",
            metric=0.85,
            sample_size=15,
            context="grep_search",
            activity_day_created=5,
            activity_day_accessed=10,
            reinforcement_count=3,
        )

        data = original.to_dict()
        restored = AwarenessPattern.from_dict(data)

        assert restored.pattern_type == original.pattern_type
        assert restored.observation == original.observation
        assert restored.metric == original.metric
        assert restored.sample_size == original.sample_size
        assert restored.context == original.context
        assert restored.activity_day_created == original.activity_day_created
        assert restored.activity_day_accessed == original.activity_day_accessed
        assert restored.reinforcement_count == original.reinforcement_count


class TestFormatPatternsForPrompt:
    """Tests for the format_patterns_for_prompt function."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty list should return empty string."""
        assert format_patterns_for_prompt([]) == ""

    def test_only_significant_patterns_included(self) -> None:
        """Non-significant patterns should be filtered out."""
        insignificant = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.05,  # Below threshold
            sample_size=10,
            context="test",
        )

        assert format_patterns_for_prompt([insignificant]) == ""

    def test_format_includes_header(self) -> None:
        """Formatted output should include header."""
        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="I overstate confidence",
            metric=0.20,
            sample_size=10,
            context="test",
        )

        result = format_patterns_for_prompt([pattern])
        assert "Based on recent sessions:" in result

    def test_format_limits_to_five_patterns(self) -> None:
        """Should limit to 5 patterns maximum."""
        patterns = [
            AwarenessPattern(
                pattern_type=PatternType.CONFIDENCE,
                observation=f"Pattern {i}",
                metric=0.20,
                sample_size=10,
                context=f"context_{i}",
            )
            for i in range(10)
        ]

        result = format_patterns_for_prompt(patterns)
        # Count lines starting with "- "
        lines = [l for l in result.split("\n") if l.strip().startswith("-")]
        assert len(lines) == 5
