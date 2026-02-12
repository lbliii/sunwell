"""Tests for Phase 4.3: Benchmarking Harness.

Tests metrics tracking, synthetic scenarios, and regression detection.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.benchmarks.metrics import (
    BenchmarkResults,
    MetricsTracker,
    RetrievalMetrics,
    measure_retrieval,
)
from sunwell.memory.benchmarks.synthetic import (
    BenchmarkScenario,
    create_authentication_scenario,
    create_database_scenario,
    get_all_scenarios,
    get_scenario,
)


class TestRetrievalMetrics:
    """Test retrieval metrics calculation."""

    def test_perfect_retrieval(self):
        """Test metrics for perfect retrieval."""
        retrieved = ["l1", "l2", "l3"]
        ground_truth = ["l1", "l2", "l3"]

        metrics = RetrievalMetrics(
            query="test",
            retrieved_ids=retrieved,
            ground_truth_ids=ground_truth,
            latency_ms=50.0,
        )

        # Perfect match
        assert metrics.accuracy == 1.0  # Top-1 is correct
        assert metrics.recall_at_5 == 1.0  # All in top-5
        assert metrics.precision_at_k(3) == 1.0

    def test_partial_retrieval(self):
        """Test metrics for partial retrieval."""
        retrieved = ["l1", "l2", "l4", "l5"]
        ground_truth = ["l1", "l3", "l4"]

        metrics = RetrievalMetrics(
            query="test",
            retrieved_ids=retrieved,
            ground_truth_ids=ground_truth,
            latency_ms=100.0,
        )

        # Top-1 is correct
        assert metrics.accuracy == 1.0

        # Recall@5: 2 out of 3 ground truth found
        assert metrics.recall_at_5 == pytest.approx(2.0 / 3.0)

        # Precision@4: 2 out of 4 retrieved are relevant
        assert metrics.precision_at_k(4) == 0.5

    def test_zero_retrieval(self):
        """Test metrics when nothing retrieved."""
        retrieved = []
        ground_truth = ["l1", "l2"]

        metrics = RetrievalMetrics(
            query="test",
            retrieved_ids=retrieved,
            ground_truth_ids=ground_truth,
            latency_ms=10.0,
        )

        assert metrics.accuracy == 0.0
        assert metrics.recall_at_5 == 0.0
        assert metrics.precision_at_k(5) == 0.0

    def test_incorrect_top_result(self):
        """Test accuracy when top result is wrong."""
        retrieved = ["l4", "l1", "l2"]
        ground_truth = ["l1", "l2", "l3"]

        metrics = RetrievalMetrics(
            query="test",
            retrieved_ids=retrieved,
            ground_truth_ids=ground_truth,
            latency_ms=50.0,
        )

        # Top-1 is wrong
        assert metrics.accuracy == 0.0

        # But recall@5 should be good (found 2/3)
        assert metrics.recall_at_5 == pytest.approx(2.0 / 3.0)


class TestMeasureRetrieval:
    """Test retrieval measurement wrapper."""

    def test_measure_retrieval_function(self):
        """Test measuring a retrieval function."""
        # Mock retrieval function
        def retrieve_fn(query):
            return [
                Learning(id="l1", fact="fact1", category="pattern"),
                Learning(id="l2", fact="fact2", category="pattern"),
            ]

        ground_truth = ["l1", "l3"]

        metrics = measure_retrieval(
            query="test query",
            ground_truth_ids=ground_truth,
            retrieve_fn=retrieve_fn,
        )

        assert metrics.query == "test query"
        assert len(metrics.retrieved_ids) == 2
        assert metrics.latency_ms > 0

    def test_measure_empty_retrieval(self):
        """Test measuring function that returns nothing."""
        def retrieve_fn(query):
            return []

        metrics = measure_retrieval(
            query="test",
            ground_truth_ids=["l1"],
            retrieve_fn=retrieve_fn,
        )

        assert len(metrics.retrieved_ids) == 0
        assert metrics.accuracy == 0.0


class TestBenchmarkResults:
    """Test benchmark results aggregation."""

    def test_aggregate_metrics(self):
        """Test aggregating multiple metrics."""
        results = BenchmarkResults(name="test_benchmark")

        # Add metrics
        results.add_metric(
            RetrievalMetrics(
                query="q1",
                retrieved_ids=["l1", "l2"],
                ground_truth_ids=["l1", "l2"],
                latency_ms=50.0,
            )
        )

        results.add_metric(
            RetrievalMetrics(
                query="q2",
                retrieved_ids=["l3"],
                ground_truth_ids=["l3", "l4"],
                latency_ms=30.0,
            )
        )

        summary = results.summary()

        # Check aggregated stats
        assert summary["num_queries"] == 2
        assert summary["accuracy"] > 0
        assert summary["recall_at_5"] > 0
        assert summary["latency"]["average_ms"] == pytest.approx((50.0 + 30.0) / 2)

    def test_empty_results(self):
        """Test summary with no metrics."""
        results = BenchmarkResults(name="empty")

        summary = results.summary()

        assert summary["num_queries"] == 0
        assert summary["accuracy"] == 0.0

    def test_latency_percentiles(self):
        """Test latency percentile calculation."""
        results = BenchmarkResults(name="latency_test")

        # Add metrics with varying latencies
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for i, latency in enumerate(latencies):
            results.add_metric(
                RetrievalMetrics(
                    query=f"q{i}",
                    retrieved_ids=["l1"],
                    ground_truth_ids=["l1"],
                    latency_ms=latency,
                )
            )

        summary = results.summary()
        latency_stats = summary["latency"]

        assert latency_stats["p50_ms"] == 50.0  # Median
        assert latency_stats["p95_ms"] == 95.0
        assert latency_stats["p99_ms"] == 99.0


class TestBenchmarkScenarios:
    """Test synthetic benchmark scenarios."""

    def test_authentication_scenario(self):
        """Test authentication scenario creation."""
        scenario = create_authentication_scenario()

        assert scenario.name == "authentication"
        assert len(scenario.learnings) >= 10
        assert len(scenario.test_cases) >= 5

        # Verify test cases have ground truth
        for query, expected_ids in scenario.test_cases:
            assert isinstance(query, str)
            assert isinstance(expected_ids, list)
            assert len(expected_ids) > 0

    def test_database_scenario(self):
        """Test database scenario creation."""
        scenario = create_database_scenario()

        assert scenario.name == "database"
        assert len(scenario.learnings) >= 10
        assert len(scenario.test_cases) >= 5

        # Check that learnings are about databases
        learning_facts = [l.fact.lower() for l in scenario.learnings]
        assert any("database" in fact or "sql" in fact for fact in learning_facts)

    def test_get_scenario_by_name(self):
        """Test retrieving scenario by name."""
        auth_scenario = get_scenario("authentication")
        assert auth_scenario.name == "authentication"

        db_scenario = get_scenario("database")
        assert db_scenario.name == "database"

    def test_get_all_scenarios(self):
        """Test retrieving all scenarios."""
        scenarios = get_all_scenarios()

        assert len(scenarios) >= 4  # auth, db, react, performance

        # Verify they're callable scenario creators
        for scenario_creator in scenarios:
            scenario = scenario_creator() if callable(scenario_creator) else scenario_creator
            assert isinstance(scenario, BenchmarkScenario)


class TestMetricsTracker:
    """Test metrics tracking and regression detection."""

    def test_track_metrics_history(self):
        """Test tracking metrics over time."""
        tracker = MetricsTracker()

        # Baseline results
        baseline = BenchmarkResults(name="test")
        baseline.add_metric(
            RetrievalMetrics("q1", ["l1"], ["l1"], 50.0)
        )

        tracker.add_results(baseline)

        # Check history
        assert len(tracker.history) == 1

    def test_detect_no_regression(self):
        """Test regression detection with improved metrics."""
        tracker = MetricsTracker()

        # Baseline: 50% accuracy
        baseline = BenchmarkResults(name="test")
        baseline.add_metric(
            RetrievalMetrics("q1", ["l2", "l1"], ["l1"], 50.0)  # Wrong top-1
        )
        baseline.add_metric(
            RetrievalMetrics("q2", ["l3"], ["l3"], 50.0)  # Correct
        )

        # Current: 100% accuracy
        current = BenchmarkResults(name="test")
        current.add_metric(
            RetrievalMetrics("q1", ["l1"], ["l1"], 45.0)  # Correct
        )
        current.add_metric(
            RetrievalMetrics("q2", ["l3"], ["l3"], 45.0)  # Correct
        )

        tracker.add_results(baseline)
        regression_info = tracker.detect_regression(current, threshold_percent=5.0)

        # No regression (improved)
        assert regression_info["regression_detected"] is False

    def test_detect_regression(self):
        """Test regression detection with degraded metrics."""
        tracker = MetricsTracker()

        # Baseline: 100% accuracy
        baseline = BenchmarkResults(name="test")
        baseline.add_metric(
            RetrievalMetrics("q1", ["l1"], ["l1"], 50.0)
        )
        baseline.add_metric(
            RetrievalMetrics("q2", ["l2"], ["l2"], 50.0)
        )

        # Current: 0% accuracy (regression)
        current = BenchmarkResults(name="test")
        current.add_metric(
            RetrievalMetrics("q1", ["l3"], ["l1"], 100.0)  # Wrong
        )
        current.add_metric(
            RetrievalMetrics("q2", ["l4"], ["l2"], 100.0)  # Wrong
        )

        tracker.add_results(baseline)
        regression_info = tracker.detect_regression(current, threshold_percent=5.0)

        # Regression detected
        assert regression_info["regression_detected"] is True
        assert len(regression_info["regressions"]) > 0


@pytest.mark.asyncio
class TestBenchmarkRunner:
    """Test benchmark runner."""

    async def test_run_scenario(self):
        """Test running a single scenario."""
        from sunwell.memory.benchmarks.runner import BenchmarkRunner

        # Mock SimulacrumStore
        mock_store = MagicMock()
        mock_store.add_learning = MagicMock()

        # Mock retrieve_for_planning
        async def mock_retrieve(query, limit_per_category):
            mock_context = MagicMock()
            mock_context.all_learnings = [
                Learning(id="l1", fact="test", category="pattern"),
            ]
            return mock_context

        mock_store.retrieve_for_planning = mock_retrieve

        runner = BenchmarkRunner(mock_store)

        # Run authentication scenario
        with patch.object(runner.store, "add_learning"):
            # This test verifies the runner structure
            # Full integration would require real store
            pass

    async def test_run_quick_benchmark(self):
        """Test quick benchmark (auth + db scenarios)."""
        from sunwell.memory.benchmarks.runner import BenchmarkRunner

        mock_store = MagicMock()

        # Mock retrieve_for_planning
        async def mock_retrieve(query, limit_per_category):
            mock_context = MagicMock()
            mock_context.all_learnings = [
                Learning(id="l1", fact="test", category="pattern"),
            ]
            return mock_context

        mock_store.retrieve_for_planning = mock_retrieve
        mock_store.add_learning = MagicMock()

        runner = BenchmarkRunner(mock_store)

        # Would run quick benchmark
        # Actual test requires full integration


class TestLongMemEvalAdapter:
    """Test LongMemEval adapter."""

    def test_adapter_creation(self):
        """Test creating LongMemEval adapter."""
        from sunwell.memory.benchmarks.longmemeval import create_longmemeval_stub

        adapter = create_longmemeval_stub()
        assert adapter is not None

    def test_expected_accuracy_benchmarks(self):
        """Test expected accuracy metrics."""
        from sunwell.memory.benchmarks.longmemeval import LongMemEvalAdapter

        adapter = LongMemEvalAdapter()
        expected = adapter.expected_accuracy()

        # Verify Hindsight SOTA
        assert expected["hindsight_sota"]["accuracy"] == 0.90

        # Verify our target
        assert expected["target"]["accuracy"] >= 0.85

    def test_sample_queries(self):
        """Test LongMemEval-style sample queries."""
        from sunwell.memory.benchmarks.longmemeval import LongMemEvalAdapter

        adapter = LongMemEvalAdapter()
        samples = adapter.sample_queries()

        assert len(samples) > 0

        # Verify format: (query, expected_ids)
        for query, expected_ids in samples:
            assert isinstance(query, str)
            assert isinstance(expected_ids, list)


class TestBenchmarkIntegration:
    """Integration tests for benchmarking system."""

    def test_end_to_end_benchmark_flow(self):
        """Test complete benchmark flow."""
        # 1. Create scenario
        scenario = create_authentication_scenario()

        # 2. Populate store (mocked)
        # 3. Run queries
        # 4. Measure metrics
        # 5. Detect regression

        assert len(scenario.learnings) > 0
        assert len(scenario.test_cases) > 0

        # Verify test cases are reasonable
        for query, expected_ids in scenario.test_cases:
            assert len(query) > 0
            assert len(expected_ids) > 0

    def test_ci_integration_pass(self):
        """Test CI integration when no regression."""
        # Would test run_ci_benchmark()
        # Returns True if no regression, False otherwise
        pass

    def test_save_and_load_baseline(self):
        """Test saving and loading baseline results."""
        temp_dir = tempfile.mkdtemp()

        try:
            from sunwell.memory.benchmarks.runner import BenchmarkRunner

            mock_store = MagicMock()
            runner = BenchmarkRunner(mock_store)

            # Create results
            results = BenchmarkResults(name="test")
            results.add_metric(
                RetrievalMetrics("q1", ["l1"], ["l1"], 50.0)
            )

            # Save
            output_path = Path(temp_dir) / "baseline.json"
            runner.save_results(results, output_path)

            assert output_path.exists()

            # Load
            loaded = runner.load_baseline(output_path)
            assert loaded is not None

        finally:
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
