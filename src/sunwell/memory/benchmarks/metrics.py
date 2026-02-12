"""Metrics for memory system benchmarking (Phase 4).

Tracks accuracy, recall, latency, and memory usage for retrieval performance.

Part of Hindsight-inspired memory enhancements.
"""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.turn import Learning


@dataclass(slots=True)
class RetrievalMetrics:
    """Metrics for a single retrieval operation."""

    query: str
    """The query string."""

    ground_truth_ids: list[str]
    """IDs of learnings that should be retrieved."""

    retrieved_ids: list[str]
    """IDs of learnings that were actually retrieved."""

    latency_ms: float
    """Retrieval latency in milliseconds."""

    memory_bytes: int = 0
    """Memory used in bytes."""

    @property
    def accuracy(self) -> float:
        """Accuracy: Is the top result correct?

        Returns:
            1.0 if top-1 is correct, 0.0 otherwise
        """
        if not self.retrieved_ids or not self.ground_truth_ids:
            return 0.0

        return 1.0 if self.retrieved_ids[0] in self.ground_truth_ids else 0.0

    @property
    def recall_at_k(self, k: int = 5) -> float:
        """Recall@k: Is the correct answer in top-k?

        Args:
            k: Number of top results to consider

        Returns:
            1.0 if any ground truth in top-k, 0.0 otherwise
        """
        if not self.retrieved_ids or not self.ground_truth_ids:
            return 0.0

        top_k = self.retrieved_ids[:k]
        for gt_id in self.ground_truth_ids:
            if gt_id in top_k:
                return 1.0

        return 0.0

    @property
    def recall_at_1(self) -> float:
        """Recall@1 (same as accuracy)."""
        return self.accuracy

    @property
    def recall_at_5(self) -> float:
        """Recall@5."""
        return self.recall_at_k(5)

    @property
    def recall_at_10(self) -> float:
        """Recall@10."""
        return self.recall_at_k(10)

    @property
    def precision_at_k(self, k: int = 5) -> float:
        """Precision@k: What fraction of top-k are relevant?

        Args:
            k: Number of top results to consider

        Returns:
            Precision score (0.0-1.0)
        """
        if not self.retrieved_ids or not self.ground_truth_ids:
            return 0.0

        top_k = self.retrieved_ids[:k]
        relevant_count = sum(1 for rid in top_k if rid in self.ground_truth_ids)

        return relevant_count / len(top_k) if top_k else 0.0


@dataclass(slots=True)
class BenchmarkResults:
    """Aggregated benchmark results."""

    name: str
    """Benchmark name."""

    metrics: list[RetrievalMetrics] = field(default_factory=list)
    """Individual retrieval metrics."""

    def add_metric(self, metric: RetrievalMetrics) -> None:
        """Add a metric to results.

        Args:
            metric: Retrieval metric to add
        """
        self.metrics.append(metric)

    @property
    def total_queries(self) -> int:
        """Total number of queries."""
        return len(self.metrics)

    @property
    def average_accuracy(self) -> float:
        """Average accuracy across all queries."""
        if not self.metrics:
            return 0.0
        return sum(m.accuracy for m in self.metrics) / len(self.metrics)

    @property
    def average_recall_at_5(self) -> float:
        """Average recall@5."""
        if not self.metrics:
            return 0.0
        return sum(m.recall_at_5 for m in self.metrics) / len(self.metrics)

    @property
    def average_recall_at_10(self) -> float:
        """Average recall@10."""
        if not self.metrics:
            return 0.0
        return sum(m.recall_at_10 for m in self.metrics) / len(self.metrics)

    @property
    def average_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if not self.metrics:
            return 0.0
        return sum(m.latency_ms for m in self.metrics) / len(self.metrics)

    @property
    def p50_latency_ms(self) -> float:
        """P50 (median) latency."""
        if not self.metrics:
            return 0.0
        sorted_latencies = sorted(m.latency_ms for m in self.metrics)
        mid = len(sorted_latencies) // 2
        return sorted_latencies[mid]

    @property
    def p95_latency_ms(self) -> float:
        """P95 latency."""
        if not self.metrics:
            return 0.0
        sorted_latencies = sorted(m.latency_ms for m in self.metrics)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99_latency_ms(self) -> float:
        """P99 latency."""
        if not self.metrics:
            return 0.0
        sorted_latencies = sorted(m.latency_ms for m in self.metrics)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def total_memory_mb(self) -> float:
        """Total memory used in MB."""
        if not self.metrics:
            return 0.0
        return sum(m.memory_bytes for m in self.metrics) / (1024 * 1024)

    def summary(self) -> dict:
        """Get summary statistics.

        Returns:
            Dict with summary stats
        """
        return {
            "name": self.name,
            "total_queries": self.total_queries,
            "accuracy": round(self.average_accuracy * 100, 2),
            "recall_at_5": round(self.average_recall_at_5 * 100, 2),
            "recall_at_10": round(self.average_recall_at_10 * 100, 2),
            "latency": {
                "average_ms": round(self.average_latency_ms, 2),
                "p50_ms": round(self.p50_latency_ms, 2),
                "p95_ms": round(self.p95_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
            },
            "memory_mb": round(self.total_memory_mb, 2),
        }

    def compare_with(self, baseline: BenchmarkResults) -> dict:
        """Compare with baseline results.

        Args:
            baseline: Baseline results to compare against

        Returns:
            Dict with comparison metrics
        """
        return {
            "accuracy_delta": round(
                (self.average_accuracy - baseline.average_accuracy) * 100, 2
            ),
            "recall_at_5_delta": round(
                (self.average_recall_at_5 - baseline.average_recall_at_5) * 100, 2
            ),
            "latency_speedup": round(
                baseline.average_latency_ms / self.average_latency_ms, 2
            ) if self.average_latency_ms > 0 else 0,
        }


class MetricsTracker:
    """Tracks metrics over time for regression detection."""

    def __init__(self):
        """Initialize metrics tracker."""
        self._history: list[BenchmarkResults] = []

    def add_results(self, results: BenchmarkResults) -> None:
        """Add benchmark results to history.

        Args:
            results: Results to add
        """
        self._history.append(results)

    def detect_regression(
        self,
        current: BenchmarkResults,
        threshold_percent: float = 5.0,
    ) -> dict:
        """Detect performance regression.

        Args:
            current: Current benchmark results
            threshold_percent: Regression threshold (e.g., 5.0 = 5%)

        Returns:
            Dict with regression status
        """
        if not self._history:
            return {"regression_detected": False, "reason": "no_baseline"}

        # Compare with most recent baseline
        baseline = self._history[-1]

        accuracy_drop = (baseline.average_accuracy - current.average_accuracy) * 100
        recall_drop = (baseline.average_recall_at_5 - current.average_recall_at_5) * 100
        latency_increase = (
            (current.average_latency_ms - baseline.average_latency_ms)
            / baseline.average_latency_ms
            * 100
        ) if baseline.average_latency_ms > 0 else 0

        regressions = []
        if accuracy_drop > threshold_percent:
            regressions.append(f"accuracy dropped {accuracy_drop:.1f}%")
        if recall_drop > threshold_percent:
            regressions.append(f"recall@5 dropped {recall_drop:.1f}%")
        if latency_increase > threshold_percent * 2:  # More lenient for latency
            regressions.append(f"latency increased {latency_increase:.1f}%")

        return {
            "regression_detected": len(regressions) > 0,
            "regressions": regressions,
            "baseline": baseline.summary(),
            "current": current.summary(),
        }

    def get_history(self) -> list[BenchmarkResults]:
        """Get benchmark history.

        Returns:
            List of benchmark results
        """
        return self._history.copy()


def measure_retrieval(
    query: str,
    ground_truth_ids: list[str],
    retrieve_fn,
) -> RetrievalMetrics:
    """Measure a single retrieval operation.

    Args:
        query: Query string
        ground_truth_ids: Expected learning IDs
        retrieve_fn: Function that performs retrieval (takes query, returns Learning list)

    Returns:
        RetrievalMetrics
    """
    # Measure latency
    start_time = time.perf_counter()
    retrieved_learnings = retrieve_fn(query)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    # Extract IDs
    retrieved_ids = [l.id for l in retrieved_learnings]

    return RetrievalMetrics(
        query=query,
        ground_truth_ids=ground_truth_ids,
        retrieved_ids=retrieved_ids,
        latency_ms=latency_ms,
    )
