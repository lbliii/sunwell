"""Regression tests for benchmark module edge case handling.

Ensures defensive guards remain in place across modules:
- naaru/analysis.py: Statistical functions
- evaluation/judge.py: Verdict aggregation
- naaru/runner.py: Summary computation

These tests verify that empty/small inputs are handled gracefully,
not that they produce specific results.
"""

import pytest

from sunwell.benchmark.evaluation.judge import aggregate_verdicts, parse_judge_response
from sunwell.benchmark.naaru.analysis import (
    compute_cohens_d,
    interpret_cohens_d,
    wilcoxon_test,
)
from sunwell.benchmark.types import JudgeVerdict, Verdict


class TestNaaruAnalysisEdgeCases:
    """Test naaru/analysis.py statistical functions handle edge cases."""

    def test_cohens_d_empty_lists(self) -> None:
        """Empty lists should return 0.0, not crash."""
        d = compute_cohens_d([], [])
        assert d == 0.0

    def test_cohens_d_single_element(self) -> None:
        """Single element lists should return 0.0 (need n>=2 for variance)."""
        d = compute_cohens_d([5.0], [3.0])
        assert d == 0.0

    def test_cohens_d_mismatched_lengths(self) -> None:
        """Mismatched lengths should return 0.0."""
        d = compute_cohens_d([1.0, 2.0, 3.0], [4.0, 5.0])
        assert d == 0.0

    def test_cohens_d_two_elements(self) -> None:
        """Two elements should compute valid effect size."""
        d = compute_cohens_d([5.0, 6.0], [3.0, 4.0])
        assert d != 0.0  # Should have computed something
        assert not (d != d)  # Not NaN

    def test_wilcoxon_test_empty_lists(self) -> None:
        """Empty lists should return (0.0, 1.0), not crash."""
        stat, p = wilcoxon_test([], [])
        assert stat == 0.0
        assert p == 1.0

    def test_wilcoxon_test_too_few_pairs(self) -> None:
        """Fewer than 3 non-tied pairs should return defaults."""
        # All ties - no valid pairs
        stat, p = wilcoxon_test([5.0, 5.0], [5.0, 5.0])
        assert p == 1.0

    def test_wilcoxon_test_valid_input(self) -> None:
        """Valid input with enough pairs should compute test."""
        stat, p = wilcoxon_test(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [0.5, 1.5, 2.5, 3.5, 4.5],
        )
        # Should return actual values
        assert 0 <= p <= 1

    def test_interpret_cohens_d_boundaries(self) -> None:
        """Effect size interpretation should handle all magnitudes."""
        assert interpret_cohens_d(0.0) == "negligible"
        assert interpret_cohens_d(0.19) == "negligible"
        assert interpret_cohens_d(0.2) == "small"
        assert interpret_cohens_d(0.49) == "small"
        assert interpret_cohens_d(0.5) == "medium"
        assert interpret_cohens_d(0.79) == "medium"
        assert interpret_cohens_d(0.8) == "large"
        assert interpret_cohens_d(2.0) == "large"

    def test_interpret_cohens_d_negative(self) -> None:
        """Negative effect sizes should use absolute value."""
        assert interpret_cohens_d(-0.9) == "large"
        assert interpret_cohens_d(-0.3) == "small"


class TestJudgeEdgeCases:
    """Test evaluation/judge.py handles edge cases."""

    def test_aggregate_verdicts_empty(self) -> None:
        """Empty verdicts list should return safe defaults."""
        result = aggregate_verdicts([])
        assert result.winner == Verdict.TIE
        assert result.agreement_rate == 0.0
        assert result.avg_score_a == 0.0
        assert result.avg_score_b == 0.0
        assert result.position_bias == 0.0

    def test_aggregate_verdicts_single(self) -> None:
        """Single verdict should still work."""
        verdict = JudgeVerdict(
            winner=Verdict.A_WINS,
            dimension_scores=(),
            confidence=0.9,
            order="ab",
            raw_response="test",
        )
        result = aggregate_verdicts([verdict])
        assert result.winner == Verdict.A_WINS
        assert result.agreement_rate == 1.0

    def test_aggregate_verdicts_no_dimension_scores(self) -> None:
        """Verdicts without dimension scores should use defaults."""
        verdicts = [
            JudgeVerdict(
                winner=Verdict.B_WINS,
                dimension_scores=(),  # Empty
                confidence=0.8,
                order="ab",
                raw_response="test",
            )
            for _ in range(3)
        ]
        result = aggregate_verdicts(verdicts)
        # Should use default 5.0 when no scores
        assert result.avg_score_a == 5.0
        assert result.avg_score_b == 5.0

    def test_parse_judge_response_invalid_json(self) -> None:
        """Invalid JSON should return TIE verdict, not crash."""
        result = parse_judge_response("not valid json at all", "ab")
        assert result.winner == Verdict.TIE
        assert result.confidence == 0.0

    def test_parse_judge_response_empty_string(self) -> None:
        """Empty response should return TIE verdict."""
        result = parse_judge_response("", "ab")
        assert result.winner == Verdict.TIE

    def test_parse_judge_response_markdown_wrapped(self) -> None:
        """JSON in markdown code blocks should be extracted."""
        response = '''```json
{"overall_winner": "A", "dimensions": [], "confidence": 0.9}
```'''
        result = parse_judge_response(response, "ab")
        assert result.winner == Verdict.A_WINS
        assert result.confidence == 0.9


class TestConditionStatsEdgeCases:
    """Test ConditionStats property edge cases."""

    def test_quality_per_token_zero_tokens(self) -> None:
        """Zero tokens should return 0.0, not divide by zero."""
        from sunwell.benchmark.naaru.types import ConditionStats, NaaruCondition

        stats = ConditionStats(
            condition=NaaruCondition.BASELINE,
            n_tasks=5,
            mean_score=8.0,
            std_score=1.0,
            min_score=6.0,
            max_score=10.0,
            mean_tokens=0,  # Zero tokens!
            total_tokens=0,
            mean_time_seconds=1.0,
            total_time_seconds=5.0,
        )
        assert stats.quality_per_token == 0.0

    def test_quality_per_token_normal(self) -> None:
        """Normal case should compute quality per 1000 tokens."""
        from sunwell.benchmark.naaru.types import ConditionStats, NaaruCondition

        stats = ConditionStats(
            condition=NaaruCondition.BASELINE,
            n_tasks=5,
            mean_score=8.0,
            std_score=1.0,
            min_score=6.0,
            max_score=10.0,
            mean_tokens=1000,
            total_tokens=5000,
            mean_time_seconds=1.0,
            total_time_seconds=5.0,
        )
        # 8.0 / 1000 * 1000 = 8.0
        assert stats.quality_per_token == 8.0


class TestCategoryStatsEdgeCases:
    """Test CategoryStats property edge cases."""

    def test_win_rate_zero_total(self) -> None:
        """Zero wins+losses should return 0.0, not divide by zero."""
        from sunwell.benchmark.types import CategoryStats

        stats = CategoryStats(
            category="test",
            total_tasks=0,
            wins=0,
            losses=0,
            ties=0,
            avg_selective_score=0.0,
            avg_baseline_score=0.0,
        )
        assert stats.win_rate == 0.0

    def test_win_rate_only_ties(self) -> None:
        """Only ties (no wins/losses) should return 0.0."""
        from sunwell.benchmark.types import CategoryStats

        stats = CategoryStats(
            category="test",
            total_tasks=5,
            wins=0,
            losses=0,
            ties=5,
            avg_selective_score=5.0,
            avg_baseline_score=5.0,
        )
        assert stats.win_rate == 0.0


class TestStatisticalSummaryEdgeCases:
    """Test StatisticalSummary property edge cases."""

    def test_win_rate_zero_total(self) -> None:
        """Zero total should return 0.0."""
        from sunwell.benchmark.types import StatisticalSummary

        summary = StatisticalSummary(
            n_tasks=0,
            n_per_category={},
            wins=0,
            losses=0,
            ties=0,
            effect_size_cohens_d=0.0,
            effect_size_interpretation="negligible",
            p_value=1.0,
            test_statistic=0.0,
            test_name="none",
            ci_lower=0.0,
            ci_upper=0.0,
        )
        assert summary.win_rate == 0.0
        assert summary.significant is False
        assert summary.claim_level() == "insufficient evidence"
