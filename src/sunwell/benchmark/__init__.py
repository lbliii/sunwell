"""Quality Benchmark Framework (RFC-018, RFC-027).

This module provides rigorous quality benchmarking to validate that
selective heuristic retrieval produces measurably better outputs than
flat injection or no injection at all.

Components:
- BenchmarkRunner: Execute tasks across conditions (bare, flat, selective)
- BenchmarkEvaluator: Three-tier evaluation (deterministic, LLM judge, human)
- BenchmarkReporter: Statistical analysis and reporting
- NaaruBenchmarkRunner: RFC-027 Naaru benchmark suite (harmonic, resonance, etc.)

Usage:
    from sunwell.benchmark import BenchmarkRunner, BenchmarkEvaluator

    runner = BenchmarkRunner(model=model, lens_loader=loader)
    results = await runner.run_suite(category="docs")

    evaluator = BenchmarkEvaluator(judge_model=judge)
    evaluation = await evaluator.evaluate_suite(results)

    # Naaru benchmark (RFC-027)
    from sunwell.benchmark.naaru import NaaruBenchmarkRunner
    naaru_runner = NaaruBenchmarkRunner(model=model, judge_model=judge, ...)
    naaru_results = await naaru_runner.run_suite()
"""

from sunwell.benchmark.core.runner import BenchmarkRunner, create_runner
from sunwell.benchmark.evaluation.evaluator import BenchmarkEvaluator
from sunwell.benchmark.naaru import (
    NaaruBenchmarkResults,
    NaaruBenchmarkRunner,
    NaaruCondition,
)
from sunwell.benchmark.reporting.reporter import BenchmarkReporter
from sunwell.benchmark.types import (
    BenchmarkResults,
    BenchmarkTask,
    DeterministicResult,
    EvaluationResult,
    JudgeVerdict,
    RetrievalMetrics,
    RubricDimension,
    StatisticalSummary,
    TaskResult,
)

__all__ = [
    # Core
    "BenchmarkRunner",
    "create_runner",
    # Evaluation
    "BenchmarkEvaluator",
    # Reporting
    "BenchmarkReporter",
    # Types
    "BenchmarkTask",
    "TaskResult",
    "EvaluationResult",
    "JudgeVerdict",
    "RubricDimension",
    "DeterministicResult",
    "RetrievalMetrics",
    "BenchmarkResults",
    "StatisticalSummary",
    # Naaru (RFC-027)
    "NaaruBenchmarkRunner",
    "NaaruCondition",
    "NaaruBenchmarkResults",
]
