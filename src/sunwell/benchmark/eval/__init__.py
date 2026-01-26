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

from sunwell.benchmark.eval.evaluator import FullStackEvaluator
from sunwell.benchmark.eval.executors import (
    EvaluationError,
    SingleShotExecutor,
    SunwellFullStackExecutor,
)
from sunwell.benchmark.eval.store import EvaluationStore, EvaluationSummary
from sunwell.benchmark.eval.tasks import FULL_STACK_TASKS, get_eval_task, list_eval_tasks
from sunwell.benchmark.eval.types import (
    EvaluationDetails,
    EvaluationRun,
    EvaluationStats,
    FullStackScore,
    FullStackTask,
    SingleShotResult,
    SunwellResult,
)

__all__ = [
    # Types (from types.py)
    "FullStackTask",
    "SingleShotResult",
    "SunwellResult",
    "FullStackScore",
    "EvaluationDetails",
    "EvaluationRun",
    "EvaluationStats",
    # Tasks (from tasks.py)
    "FULL_STACK_TASKS",
    "get_eval_task",
    "list_eval_tasks",
    # Executors (from executors.py)
    "SingleShotExecutor",
    "SunwellFullStackExecutor",
    "EvaluationError",
    # Evaluator (from evaluator.py)
    "FullStackEvaluator",
    # Store (from store.py)
    "EvaluationStore",
    "EvaluationSummary",
]
