"""Benchmark runner for Phase 4.

Runs benchmarks and tracks metrics over time for regression detection.

Part of Hindsight-inspired memory enhancements.
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.benchmarks.metrics import (
    BenchmarkResults,
    MetricsTracker,
    measure_retrieval,
)
from sunwell.memory.benchmarks.synthetic import get_all_scenarios, get_scenario

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Runs memory system benchmarks."""

    def __init__(
        self,
        store: SimulacrumStore,
        workspace: Path | None = None,
    ):
        """Initialize benchmark runner.

        Args:
            store: SimulacrumStore to benchmark
            workspace: Optional workspace path for history tracking
        """
        self.store = store
        self.workspace = workspace
        self.metrics_tracker = MetricsTracker()

    async def run_scenario(self, scenario_name: str) -> BenchmarkResults:
        """Run a single benchmark scenario.

        Args:
            scenario_name: Name of scenario to run

        Returns:
            BenchmarkResults
        """
        # Get scenario
        scenario = get_scenario(scenario_name)

        logger.info(f"Running benchmark: {scenario.name}")
        logger.info(f"Description: {scenario.description}")
        logger.info(f"Learnings: {len(scenario.learnings)}, Test cases: {len(scenario.test_cases)}")

        # Populate store with learnings
        for learning in scenario.learnings:
            self.store.add_learning(
                fact=learning.fact,
                category=learning.category,
                confidence=learning.confidence,
            )

        # Build BM25 index if available
        if hasattr(self.store, "_learning_cache"):
            cache = getattr(self.store, "_learning_cache", None)
            if cache and hasattr(cache, "build_bm25_index"):
                logger.info("Building BM25 index...")
                cache.build_bm25_index()

        # Run test cases
        results = BenchmarkResults(name=scenario.name)

        for query, expected_ids in scenario.test_cases:
            # Create retrieval function
            async def retrieve_fn(q: str):
                context = await self.store.retrieve_for_planning(q, limit_per_category=5)
                return list(context.all_learnings)

            # Measure retrieval
            metric = measure_retrieval(
                query=query,
                ground_truth_ids=expected_ids,
                retrieve_fn=lambda q: asyncio.run(retrieve_fn(q)),
            )
            results.add_metric(metric)

        logger.info(f"Benchmark complete: {results.summary()}")
        return results

    async def run_all_scenarios(self) -> dict[str, BenchmarkResults]:
        """Run all benchmark scenarios.

        Returns:
            Dict mapping scenario name to results
        """
        results = {}

        for scenario_creator in get_all_scenarios():
            scenario = scenario_creator if callable(scenario_creator) else scenario_creator
            if callable(scenario):
                scenario = scenario()

            result = await self.run_scenario(scenario.name)
            results[scenario.name] = result

        return results

    async def run_quick_benchmark(self) -> BenchmarkResults:
        """Run quick benchmark (authentication + database scenarios).

        Returns:
            Combined BenchmarkResults
        """
        logger.info("Running quick benchmark...")

        # Run authentication and database scenarios
        auth_results = await self.run_scenario("authentication")
        db_results = await self.run_scenario("database")

        # Combine results
        combined = BenchmarkResults(name="quick_benchmark")
        combined.metrics.extend(auth_results.metrics)
        combined.metrics.extend(db_results.metrics)

        return combined

    def detect_regression(
        self,
        current: BenchmarkResults,
        threshold_percent: float = 5.0,
    ) -> dict:
        """Detect regression compared to baseline.

        Args:
            current: Current benchmark results
            threshold_percent: Regression threshold

        Returns:
            Dict with regression info
        """
        return self.metrics_tracker.detect_regression(current, threshold_percent)

    def save_results(self, results: BenchmarkResults, path: Path) -> None:
        """Save results to file.

        Args:
            results: Results to save
            path: Output path
        """
        import json

        with open(path, "w") as f:
            json.dump(results.summary(), f, indent=2)

        logger.info(f"Saved results to {path}")

    def load_baseline(self, path: Path) -> BenchmarkResults | None:
        """Load baseline results from file.

        Args:
            path: Path to baseline file

        Returns:
            BenchmarkResults if found, None otherwise
        """
        import json

        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)

            # Reconstruct results (simplified - just summary stats)
            baseline = BenchmarkResults(name=data["name"])
            logger.info(f"Loaded baseline from {path}")
            return baseline
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")
            return None


async def run_ci_benchmark(store: SimulacrumStore) -> bool:
    """Run benchmark for CI integration.

    Args:
        store: SimulacrumStore to benchmark

    Returns:
        True if no regression detected, False otherwise
    """
    runner = BenchmarkRunner(store)

    # Run quick benchmark
    results = await runner.run_quick_benchmark()

    # Check for regression
    regression_info = runner.detect_regression(results)

    if regression_info["regression_detected"]:
        logger.error(f"Regression detected: {regression_info['regressions']}")
        return False

    logger.info("No regression detected")
    return True


async def benchmark_all(store: SimulacrumStore, output_dir: Path | None = None) -> dict:
    """Run all benchmarks and save results.

    Args:
        store: SimulacrumStore to benchmark
        output_dir: Optional directory for results

    Returns:
        Dict with all results
    """
    runner = BenchmarkRunner(store)

    # Run all scenarios
    all_results = await runner.run_all_scenarios()

    # Save results if output dir provided
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, results in all_results.items():
            output_path = output_dir / f"{name}_results.json"
            runner.save_results(results, output_path)

    # Print summary
    logger.info("\n=== Benchmark Summary ===")
    for name, results in all_results.items():
        summary = results.summary()
        logger.info(f"\n{name}:")
        logger.info(f"  Accuracy: {summary['accuracy']}%")
        logger.info(f"  Recall@5: {summary['recall_at_5']}%")
        logger.info(f"  Avg Latency: {summary['latency']['average_ms']}ms")

    return {name: results.summary() for name, results in all_results.items()}
