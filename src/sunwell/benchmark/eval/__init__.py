"""Evaluation Framework — Real Metrics, Real Transparency (RFC-098).

Provides rigorous evaluation comparing single-shot prompting vs Sunwell's
cognitive architecture on complex multi-file tasks.

Key Components:
- FullStackTask: Definition of evaluation tasks
- SingleShotExecutor: Baseline single-turn generation with tools
- SunwellFullStackExecutor: Full cognitive stack via Naaru
- FullStackEvaluator: Scoring and comparison
- EvaluationStore: SQLite-backed historical tracking
"""

from sunwell.benchmark.eval.evaluator import FullStackEvaluator, FullStackScore
from sunwell.benchmark.eval.executors import (
    EvaluationError,
    SingleShotExecutor,
    SingleShotResult,
    SunwellFullStackExecutor,
    SunwellResult,
)
from sunwell.benchmark.eval.store import EvaluationRun, EvaluationStats, EvaluationStore
from sunwell.benchmark.eval.tasks import FULL_STACK_TASKS, FullStackTask, get_eval_task

__all__ = [
    # Tasks
    "FullStackTask",
    "FULL_STACK_TASKS",
    "get_eval_task",
    # Executors
    "SingleShotExecutor",
    "SingleShotResult",
    "SunwellFullStackExecutor",
    "SunwellResult",
    "EvaluationError",
    # Evaluator
    "FullStackEvaluator",
    "FullStackScore",
    # Store
    "EvaluationStore",
    "EvaluationRun",
    "EvaluationStats",
]
