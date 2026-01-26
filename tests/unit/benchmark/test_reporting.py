"""Tests for sunwell.benchmark.reporting edge cases.

Covers:
- Empty/small sample handling in statistical functions
- Edge cases that previously caused crashes or NaN results
"""

import numpy as np

from sunwell.benchmark.reporting.reporter import BenchmarkReporter
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

    def test_reproducibility_with_seed(self) -> None:
        """Seed 42 should produce identical results on repeated calls."""
        data_a = np.array([3.0, 4.0, 5.0, 6.0, 7.0])
        data_b = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        lower1, upper1 = bootstrap_ci(data_a, data_b)
        lower2, upper2 = bootstrap_ci(data_a, data_b)

        # With fixed seed=42 in implementation, results should be identical
        assert lower1 == lower2
        assert upper1 == upper2

    def test_ci_lower_always_lte_upper(self) -> None:
        """CI lower should always be <= CI upper for any valid input."""
        test_cases = [
            (np.array([1.0, 2.0]), np.array([1.0, 2.0])),  # Equal
            (np.array([5.0, 6.0]), np.array([1.0, 2.0])),  # A higher
            (np.array([1.0, 2.0]), np.array([5.0, 6.0])),  # B higher
            (np.array([1.0, 10.0, 2.0, 9.0]), np.array([3.0, 8.0, 4.0, 7.0])),  # Mixed
        ]
        for data_a, data_b in test_cases:
            lower, upper = bootstrap_ci(data_a, data_b)
            assert lower <= upper, f"CI ordering failed for {data_a} vs {data_b}"


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

    # Boundary tests - exact thresholds
    def test_boundary_negligible_to_small(self) -> None:
        """Test exact boundary at 0.2."""
        assert interpret_effect_size(0.19) == "negligible"
        assert interpret_effect_size(0.2) == "small"
        assert interpret_effect_size(-0.19) == "negligible"
        assert interpret_effect_size(-0.2) == "small"

    def test_boundary_small_to_medium(self) -> None:
        """Test exact boundary at 0.5."""
        assert interpret_effect_size(0.49) == "small"
        assert interpret_effect_size(0.5) == "medium"
        assert interpret_effect_size(-0.49) == "small"
        assert interpret_effect_size(-0.5) == "medium"

    def test_boundary_medium_to_large(self) -> None:
        """Test exact boundary at 0.8."""
        assert interpret_effect_size(0.79) == "medium"
        assert interpret_effect_size(0.8) == "large"
        assert interpret_effect_size(-0.79) == "medium"
        assert interpret_effect_size(-0.8) == "large"

    def test_zero_is_negligible(self) -> None:
        """Zero effect size is negligible."""
        assert interpret_effect_size(0.0) == "negligible"


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

    def test_category_extraction_with_hyphen(self) -> None:
        """Task ID with hyphens extracts first segment as category."""
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
            task_id="docs-api-ref-001",
            deterministic={},
            judge_results={"selective_vs_bare": verdict},
        )

        summary = reporter.compute_statistics([], [eval_result])
        assert "docs" in summary.n_per_category

    def test_category_extraction_without_hyphen(self) -> None:
        """Task ID without hyphens defaults to 'other' category."""
        reporter = BenchmarkReporter()

        verdict = AggregatedVerdict(
            winner=Verdict.TIE,
            individual_verdicts=(),
            agreement_rate=1.0,
            avg_score_a=3.0,
            avg_score_b=3.0,
            position_bias=0.0,
        )

        eval_result = EvaluationResult(
            task_id="singletask",
            deterministic={},
            judge_results={"selective_vs_bare": verdict},
        )

        summary = reporter.compute_statistics([], [eval_result])
        assert "other" in summary.n_per_category

    def test_win_loss_tie_aggregation(self) -> None:
        """Verify win/loss/tie counts match verdict types."""
        reporter = BenchmarkReporter()

        # Create 2 wins, 1 loss, 1 tie
        verdicts = [
            (Verdict.B_WINS, "task-win1"),
            (Verdict.B_WINS, "task-win2"),
            (Verdict.A_WINS, "task-loss1"),
            (Verdict.TIE, "task-tie1"),
        ]

        eval_results = []
        for verdict_type, task_id in verdicts:
            verdict = AggregatedVerdict(
                winner=verdict_type,
                individual_verdicts=(),
                agreement_rate=1.0,
                avg_score_a=3.0,
                avg_score_b=4.0 if verdict_type == Verdict.B_WINS else 3.0,
                position_bias=0.0,
            )
            eval_results.append(EvaluationResult(
                task_id=task_id,
                deterministic={},
                judge_results={"selective_vs_bare": verdict},
            ))

        summary = reporter.compute_statistics([], eval_results)
        assert summary.wins == 2
        assert summary.losses == 1
        assert summary.ties == 1


class TestStatisticalSummaryClaimLevel:
    """Test StatisticalSummary.claim_level() method."""

    def _make_summary(
        self, p_value: float, effect_size: float
    ) -> StatisticalSummary:
        """Helper to create summary with specific p-value and effect size."""
        return StatisticalSummary(
            n_tasks=10,
            n_per_category={},
            wins=5,
            losses=3,
            ties=2,
            effect_size_cohens_d=effect_size,
            effect_size_interpretation="large" if abs(effect_size) >= 0.8 else "medium",
            p_value=p_value,
            test_statistic=10.0,
            test_name="test",
            ci_lower=0.1,
            ci_upper=0.5,
        )

    def test_strong_evidence(self) -> None:
        """p < 0.01 and d > 0.8 = strong evidence."""
        summary = self._make_summary(p_value=0.005, effect_size=0.9)
        assert summary.claim_level() == "strong evidence"

    def test_shows_improvement(self) -> None:
        """p < 0.05 and d > 0.5 = shows improvement."""
        summary = self._make_summary(p_value=0.03, effect_size=0.6)
        assert summary.claim_level() == "shows improvement"

    def test_suggests_improvement(self) -> None:
        """p < 0.1 and d > 0.2 = suggests improvement."""
        summary = self._make_summary(p_value=0.08, effect_size=0.3)
        assert summary.claim_level() == "suggests improvement"

    def test_insufficient_evidence_high_p(self) -> None:
        """p >= 0.1 = insufficient evidence."""
        summary = self._make_summary(p_value=0.15, effect_size=0.9)
        assert summary.claim_level() == "insufficient evidence"

    def test_insufficient_evidence_low_effect(self) -> None:
        """d <= 0.2 with low p = insufficient evidence."""
        summary = self._make_summary(p_value=0.01, effect_size=0.15)
        assert summary.claim_level() == "insufficient evidence"

    def test_boundary_strong_evidence(self) -> None:
        """Test boundary: p=0.01 and d=0.8 should NOT be strong (needs p < 0.01)."""
        summary = self._make_summary(p_value=0.01, effect_size=0.85)
        # p=0.01 is not < 0.01, so should be shows improvement
        assert summary.claim_level() == "shows improvement"

    def test_win_rate_calculation(self) -> None:
        """Test win_rate property."""
        summary = self._make_summary(p_value=0.05, effect_size=0.5)
        # 5 wins / (5 + 3 + 2) = 0.5
        assert summary.win_rate == 0.5

    def test_significant_property(self) -> None:
        """Test significant property (p < 0.05)."""
        sig_summary = self._make_summary(p_value=0.04, effect_size=0.5)
        assert sig_summary.significant is True

        not_sig_summary = self._make_summary(p_value=0.06, effect_size=0.5)
        assert not_sig_summary.significant is False


class TestMarkdownReportGeneration:
    """Test BenchmarkReporter.generate_markdown_report()."""

    def _make_minimal_results(self) -> tuple:
        """Create minimal results for testing markdown generation."""
        from sunwell.benchmark.types import BenchmarkResults

        verdict = AggregatedVerdict(
            winner=Verdict.B_WINS,
            individual_verdicts=(),
            agreement_rate=0.8,
            avg_score_a=3.5,
            avg_score_b=4.5,
            position_bias=0.1,
        )

        eval_result = EvaluationResult(
            task_id="docs-test-001",
            deterministic={
                "selective": DeterministicResult(
                    must_contain_results={"API": True},
                    must_not_contain_results={},
                ),
            },
            judge_results={"selective_vs_bare": verdict},
        )

        task_result = TaskResult(
            task_id="docs-test-001",
            outputs={
                "selective": ConditionOutput(
                    condition=Condition.SELECTIVE,
                    content="Test output",
                    tokens_input=100,
                    tokens_output=50,
                    latency_ms=500,
                ),
            },
        )

        results = BenchmarkResults(
            timestamp="2025-01-01T00:00:00",
            model="test-model",
            task_results=(task_result,),
        )

        summary = StatisticalSummary(
            n_tasks=1,
            n_per_category={"docs": 1},
            wins=1,
            losses=0,
            ties=0,
            effect_size_cohens_d=0.9,
            effect_size_interpretation="large",
            p_value=0.02,
            test_statistic=5.0,
            test_name="Wilcoxon signed-rank",
            ci_lower=0.1,
            ci_upper=0.5,
        )

        return results, [eval_result], summary

    def test_report_contains_header(self) -> None:
        """Report should contain header section."""
        reporter = BenchmarkReporter()
        results, evals, summary = self._make_minimal_results()
        report = reporter.generate_markdown_report(results, evals, summary)

        assert "# Quality Benchmark Report" in report
        assert "**Model**: test-model" in report

    def test_report_contains_summary_table(self) -> None:
        """Report should contain summary statistics table."""
        reporter = BenchmarkReporter()
        results, evals, summary = self._make_minimal_results()
        report = reporter.generate_markdown_report(results, evals, summary)

        assert "## Summary" in report
        assert "| Metric | Value |" in report
        assert "Win Rate" in report
        assert "Effect Size" in report
        assert "p-value" in report

    def test_report_contains_interpretation(self) -> None:
        """Report should contain interpretation section."""
        reporter = BenchmarkReporter()
        results, evals, summary = self._make_minimal_results()
        report = reporter.generate_markdown_report(results, evals, summary)

        assert "### Interpretation" in report
        # With p=0.02 and d=0.9, should show "shows improvement"
        assert "show improvement" in report.lower() or "strong evidence" in report.lower()

    def test_report_contains_category_breakdown(self) -> None:
        """Report should contain category breakdown when category_stats exist."""
        from sunwell.benchmark.types import CategoryStats

        reporter = BenchmarkReporter()
        results, evals, _ = self._make_minimal_results()

        # Create summary WITH category_stats populated
        summary_with_cats = StatisticalSummary(
            n_tasks=1,
            n_per_category={"docs": 1},
            wins=1,
            losses=0,
            ties=0,
            effect_size_cohens_d=0.9,
            effect_size_interpretation="large",
            p_value=0.02,
            test_statistic=5.0,
            test_name="Wilcoxon signed-rank",
            ci_lower=0.1,
            ci_upper=0.5,
            category_stats=(
                CategoryStats(
                    category="docs",
                    total_tasks=1,
                    wins=1,
                    losses=0,
                    ties=0,
                    avg_selective_score=4.5,
                    avg_baseline_score=3.5,
                ),
            ),
        )

        report = reporter.generate_markdown_report(results, evals, summary_with_cats)
        assert "## Category Breakdown" in report
        assert "docs" in report

    def test_report_contains_detailed_results(self) -> None:
        """Report should contain detailed per-task results."""
        reporter = BenchmarkReporter()
        results, evals, summary = self._make_minimal_results()
        report = reporter.generate_markdown_report(results, evals, summary)

        assert "## Detailed Results" in report
        assert "docs-test-001" in report
