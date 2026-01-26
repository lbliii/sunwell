"""Tests for sunwell.benchmark.reporting edge cases.

Covers:
- Empty/small sample handling in statistical functions
- Edge cases that previously caused crashes or NaN results
"""

import numpy as np
import pytest

from sunwell.benchmark.reporting.statistics import (
    bootstrap_ci,
    cohens_d,
    empty_summary,
    interpret_effect_size,
    significance_test,
)
from sunwell.benchmark.types import (
    AggregatedVerdict,
    Condition,
    ConditionOutput,
    DeterministicResult,
    EvaluationResult,
    StatisticalSummary,
    TaskResult,
    Verdict,
)
from sunwell.benchmark.reporting.reporter import BenchmarkReporter


class TestSignificanceTest:
    """Test significance_test edge cases."""

    def test_empty_arrays_return_insufficient_data(self) -> None:
        """Empty arrays should return insufficient_data, not crash."""
        p, stat, name = significance_test(np.array([]), np.array([]))
        assert p == 1.0
        assert stat == 0.0
        assert name == "insufficient_data"

    def test_single_element_arrays_return_insufficient_data(self) -> None:
        """Single element arrays need at least 2 samples for meaningful test."""
        p, stat, name = significance_test(np.array([1.0]), np.array([2.0]))
        assert p == 1.0
        assert stat == 0.0
        assert name == "insufficient_data"

    def test_two_elements_works(self) -> None:
        """Two elements per group is minimum for statistical test."""
        # With scipy available, should run actual test
        p, stat, name = significance_test(
            np.array([3.0, 4.0]),
            np.array([1.0, 2.0]),
        )
        # Should return actual results, not insufficient_data
        assert name in ("Wilcoxon signed-rank", "Mann-Whitney U", "scipy_not_available")

    def test_mismatched_lengths_uses_mann_whitney(self) -> None:
        """Different length arrays use Mann-Whitney U (independent samples)."""
        p, stat, name = significance_test(
            np.array([3.0, 4.0, 5.0]),
            np.array([1.0, 2.0]),
        )
        # Should use Mann-Whitney for independent samples
        if name != "scipy_not_available":
            assert name == "Mann-Whitney U"


class TestCohensD:
    """Test cohens_d edge cases."""

    def test_empty_arrays_return_zero(self) -> None:
        """Empty arrays should return 0.0, not crash."""
        d = cohens_d(np.array([]), np.array([]))
        assert d == 0.0

    def test_single_element_returns_zero(self) -> None:
        """Single element arrays can't compute variance with ddof=1."""
        d = cohens_d(np.array([1.0]), np.array([2.0]))
        assert d == 0.0
        assert not np.isnan(d)  # Key fix: was returning NaN before

    def test_two_elements_computes_effect_size(self) -> None:
        """Two elements per group is minimum for Cohen's d."""
        d = cohens_d(np.array([3.0, 4.0]), np.array([1.0, 2.0]))
        assert d > 0  # Selective higher than baseline
        assert not np.isnan(d)

    def test_identical_values_zero_variance(self) -> None:
        """Zero variance case should return inf for non-zero mean diff."""
        d = cohens_d(np.array([5.0, 5.0]), np.array([1.0, 1.0]))
        assert d == float("inf")

    def test_identical_values_both_groups(self) -> None:
        """Zero variance and zero mean diff should return 0."""
        d = cohens_d(np.array([3.0, 3.0]), np.array([3.0, 3.0]))
        assert d == 0.0


class TestBootstrapCI:
    """Test bootstrap_ci edge cases."""

    def test_empty_arrays_return_zero_ci(self) -> None:
        """Empty arrays should return (0.0, 0.0)."""
        lower, upper = bootstrap_ci(np.array([]), np.array([]))
        assert lower == 0.0
        assert upper == 0.0

    def test_single_element_returns_zero_ci(self) -> None:
        """Single element arrays can't produce meaningful CI."""
        lower, upper = bootstrap_ci(np.array([1.0]), np.array([2.0]))
        assert lower == 0.0
        assert upper == 0.0

    def test_two_elements_produces_ci(self) -> None:
        """Two elements per group produces actual CI."""
        lower, upper = bootstrap_ci(
            np.array([3.0, 4.0]),
            np.array([1.0, 2.0]),
        )
        # With clear separation, CI should be positive
        assert lower <= upper

    def test_custom_ci_level(self) -> None:
        """Custom CI level should affect bounds."""
        data_a = np.array([3.0, 4.0, 5.0, 6.0])
        data_b = np.array([1.0, 2.0, 3.0, 4.0])

        lower_95, upper_95 = bootstrap_ci(data_a, data_b, ci_level=0.95)
        lower_90, upper_90 = bootstrap_ci(data_a, data_b, ci_level=0.90)

        # 90% CI should be narrower than 95% CI
        assert (upper_95 - lower_95) >= (upper_90 - lower_90)


class TestInterpretEffectSize:
    """Test effect size interpretation."""

    def test_negligible(self) -> None:
        assert interpret_effect_size(0.1) == "negligible"
        assert interpret_effect_size(-0.1) == "negligible"

    def test_small(self) -> None:
        assert interpret_effect_size(0.3) == "small"
        assert interpret_effect_size(-0.3) == "small"

    def test_medium(self) -> None:
        assert interpret_effect_size(0.6) == "medium"
        assert interpret_effect_size(-0.6) == "medium"

    def test_large(self) -> None:
        assert interpret_effect_size(1.0) == "large"
        assert interpret_effect_size(-1.0) == "large"


class TestEmptySummary:
    """Test empty_summary factory."""

    def test_returns_valid_summary(self) -> None:
        """empty_summary should return a valid StatisticalSummary."""
        summary = empty_summary()
        assert isinstance(summary, StatisticalSummary)
        assert summary.n_tasks == 0
        assert summary.wins == 0
        assert summary.losses == 0
        assert summary.ties == 0
        assert summary.p_value == 1.0
        assert summary.effect_size_interpretation == "negligible"


class TestBenchmarkReporter:
    """Test BenchmarkReporter edge cases."""

    def test_compute_statistics_empty_evaluations(self) -> None:
        """Empty evaluations should return empty summary."""
        reporter = BenchmarkReporter()
        summary = reporter.compute_statistics([], [])
        assert summary.n_tasks == 0

    def test_compute_statistics_no_judge_results(self) -> None:
        """Evaluations without judge results should not crash."""
        reporter = BenchmarkReporter()

        # Create evaluation with empty judge_results
        eval_result = EvaluationResult(
            task_id="test-001",
            deterministic={},
            judge_results={},
        )

        results = [
            TaskResult(
                task_id="test-001",
                outputs={},
            )
        ]

        summary = reporter.compute_statistics(results, [eval_result])
        # Should handle gracefully - may have insufficient data
        assert summary.n_tasks == 1
        # With no judge results, wins/losses/ties should be 0
        assert summary.wins == 0
        assert summary.losses == 0
        assert summary.ties == 0

    def test_compute_statistics_single_evaluation(self) -> None:
        """Single evaluation should work but may show insufficient_data."""
        reporter = BenchmarkReporter()

        verdict = AggregatedVerdict(
            winner=Verdict.B_WINS,
            individual_verdicts=(),
            agreement_rate=1.0,
            avg_score_a=3.0,
            avg_score_b=4.0,
            position_bias=0.0,
        )

        eval_result = EvaluationResult(
            task_id="test-001",
            deterministic={},
            judge_results={"selective_vs_bare": verdict},
        )

        results = [
            TaskResult(
                task_id="test-001",
                outputs={},
            )
        ]

        summary = reporter.compute_statistics(results, [eval_result])
        assert summary.wins == 1
        # Single data point means insufficient data for stats
        assert summary.test_name == "insufficient_data"
