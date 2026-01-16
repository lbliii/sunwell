"""Quality Benchmark Framework (RFC-018).

This module provides rigorous quality benchmarking to validate that
selective heuristic retrieval produces measurably better outputs than
flat injection or no injection at all.

Components:
- BenchmarkRunner: Execute tasks across conditions (bare, flat, selective)
- BenchmarkEvaluator: Three-tier evaluation (deterministic, LLM judge, human)
- BenchmarkReporter: Statistical analysis and reporting

Usage:
    from sunwell.benchmark import BenchmarkRunner, BenchmarkEvaluator
    
    runner = BenchmarkRunner(model=model, lens_loader=loader)
    results = await runner.run_suite(category="docs")
    
    evaluator = BenchmarkEvaluator(judge_model=judge)
    evaluation = await evaluator.evaluate_suite(results)
"""

from sunwell.benchmark.types import (
    BenchmarkTask,
    TaskResult,
    EvaluationResult,
    JudgeVerdict,
    RubricDimension,
    DeterministicResult,
    RetrievalMetrics,
    BenchmarkResults,
    StatisticalSummary,
)
from sunwell.benchmark.runner import BenchmarkRunner
from sunwell.benchmark.evaluator import BenchmarkEvaluator
from sunwell.benchmark.report import BenchmarkReporter

__all__ = [
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
    # Classes
    "BenchmarkRunner",
    "BenchmarkEvaluator",
    "BenchmarkReporter",
]
