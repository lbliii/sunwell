"""Benchmark Evaluator (RFC-018).

Three-tier evaluation system:
1. Deterministic checks (must_contain, must_not_contain, code tests)
2. LLM-as-Judge pairwise comparison with position randomization
3. Human evaluation protocol (not automated)
"""

import logging
from dataclasses import dataclass

from sunwell.benchmark.evaluation.deterministic import evaluate_deterministic
from sunwell.benchmark.evaluation.judge import evaluate_with_judge
from sunwell.benchmark.types import (
    AggregatedVerdict,
    BenchmarkTask,
    DeterministicResult,
    EvaluationResult,
    TaskResult,
    Verdict,
)
from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkEvaluator:
    """Evaluate benchmark outputs using three-tier methodology.

    Usage:
        evaluator = BenchmarkEvaluator(judge_model=judge)
        result = await evaluator.evaluate(task, task_result)
    """

    judge_model: ModelProtocol
    num_judge_runs: int = 3  # For majority vote
    run_code_tests: bool = True  # Enable code execution checks

    async def evaluate(
        self,
        task: BenchmarkTask,
        result: TaskResult,
    ) -> EvaluationResult:
        """Run all evaluation tiers for a single task.

        Args:
            task: The benchmark task definition
            result: The outputs from running the task

        Returns:
            EvaluationResult with deterministic and judge evaluations
        """
        # Tier 1: Deterministic checks for each condition
        deterministic: dict[str, DeterministicResult] = {}
        for condition_name, output in result.outputs.items():
            deterministic[condition_name] = evaluate_deterministic(
                task=task,
                output=output.content,
                run_code_tests=self.run_code_tests,
            )

        # Tier 2: LLM Judge pairwise comparisons
        judge_results: dict[str, AggregatedVerdict] = {}

        # Compare selective vs each baseline
        if "selective" in result.outputs:
            selective_output = result.outputs["selective"].content

            for baseline in ["bare", "flat"]:
                if baseline in result.outputs:
                    baseline_output = result.outputs[baseline].content

                    verdict = await evaluate_with_judge(
                        judge_model=self.judge_model,
                        task=task,
                        output_a=baseline_output,
                        output_b=selective_output,
                        num_runs=self.num_judge_runs,
                    )
                    judge_results[f"selective_vs_{baseline}"] = verdict

        # Determine overall winner
        overall_winner = self._determine_winner(judge_results)

        return EvaluationResult(
            task_id=task.id,
            deterministic=deterministic,
            judge_results=judge_results,
            overall_winner=overall_winner,
        )

    def _determine_winner(
        self,
        judge_results: dict[str, AggregatedVerdict],
    ) -> str:
        """Determine overall winner across all comparisons.

        Returns "selective" if it wins all comparisons, baseline name otherwise.
        """
        if not judge_results:
            return ""

        # Check if selective wins all comparisons
        selective_wins_all = all(
            v.winner == Verdict.B_WINS  # B is always selective in our comparisons
            for v in judge_results.values()
        )

        if selective_wins_all:
            return "selective"

        # Find the baseline that selective lost to
        for key, verdict in judge_results.items():
            if verdict.winner == Verdict.A_WINS:
                # Extract baseline name from key like "selective_vs_bare"
                return key.replace("selective_vs_", "")

        return "tie"

    async def evaluate_suite(
        self,
        tasks: list[BenchmarkTask],
        results: list[TaskResult],
    ) -> list[EvaluationResult]:
        """Evaluate all results from a benchmark suite."""
        # Create task lookup
        task_map = {t.id: t for t in tasks}

        evaluations: list[EvaluationResult] = []

        for result in results:
            task = task_map.get(result.task_id)
            if task is None:
                logger.warning("Task not found for result: %s", result.task_id)
                continue

            logger.info("Evaluating %s...", result.task_id)
            try:
                evaluation = await self.evaluate(task, result)
                evaluations.append(evaluation)
                if evaluation.selective_wins:
                    logger.info("  %s: ✓ selective wins", result.task_id)
                else:
                    logger.info("  %s: ✗ %s wins", result.task_id, evaluation.overall_winner)
            except Exception:
                logger.exception("Evaluation failed for %s", result.task_id)

        return evaluations
