"""Naaru Benchmark Suite (RFC-027).

Validates Naaru's quality claims with statistical rigor:
- Ablation tests for each technique
- Naaru × Lens interaction effects
- Cost-quality Pareto frontier

Example:
    >>> from sunwell.benchmark.naaru import NaaruBenchmarkRunner, NaaruCondition
    >>>
    >>> runner = NaaruBenchmarkRunner(
    ...     model=model,
    ...     judge_model=judge,
    ...     lens_loader=loader,
    ...     tasks_dir=Path("benchmark/tasks"),
    ... )
    >>> results = await runner.run_suite(max_tasks=30)
"""

from sunwell.benchmark.naaru.runner import NaaruBenchmarkRunner, create_naaru_runner
from sunwell.benchmark.naaru.types import (
    ConditionStats,
    HarmonicMetrics,
    NaaruBenchmarkResults,
    NaaruCondition,
    NaaruConditionOutput,
    NaaruTaskResult,
    ResonanceMetrics,
)

__all__ = [
    "NaaruCondition",
    "NaaruConditionOutput",
    "NaaruTaskResult",
    "NaaruBenchmarkResults",
    "NaaruBenchmarkRunner",
    "create_naaru_runner",
    "HarmonicMetrics",
    "ResonanceMetrics",
    "ConditionStats",
]
