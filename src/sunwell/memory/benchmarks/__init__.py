"""Benchmarking harness for Phase 4: Optimization.

Provides metrics tracking, synthetic scenarios, and regression detection
for memory system performance.

Part of Hindsight-inspired memory enhancements.
"""

from sunwell.memory.benchmarks.longmemeval import (
    LongMemEvalAdapter,
    create_longmemeval_stub,
)
from sunwell.memory.benchmarks.metrics import (
    BenchmarkResults,
    MetricsTracker,
    RetrievalMetrics,
    measure_retrieval,
)
from sunwell.memory.benchmarks.runner import (
    BenchmarkRunner,
    benchmark_all,
    run_ci_benchmark,
)
from sunwell.memory.benchmarks.synthetic import (
    ALL_SCENARIOS,
    BenchmarkScenario,
    get_all_scenarios,
    get_scenario,
)

__all__ = [
    # Metrics
    "RetrievalMetrics",
    "BenchmarkResults",
    "MetricsTracker",
    "measure_retrieval",
    # Scenarios
    "BenchmarkScenario",
    "get_scenario",
    "get_all_scenarios",
    "ALL_SCENARIOS",
    # LongMemEval
    "LongMemEvalAdapter",
    "create_longmemeval_stub",
    # Runner
    "BenchmarkRunner",
    "run_ci_benchmark",
    "benchmark_all",
]
