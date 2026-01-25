"""Lens experiment runner for systematic evaluation.

Runs all lens injection strategies across demo tasks and collects metrics.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sunwell.demo.lens_experiments import (
    STRATEGY_BUILDERS,
    ExperimentResult,
    ExperimentSummary,
    LensData,
    LensStrategy,
    PromptParts,
    create_prompt_builder,
    load_default_lens,
)
from sunwell.demo.scorer import DemoScorer
from sunwell.demo.tasks import BUILTIN_TASKS, DemoTask


@dataclass(slots=True)
class ExperimentConfig:
    """Configuration for experiment runs."""

    strategies: list[LensStrategy] = field(
        default_factory=lambda: list(LensStrategy)
    )
    tasks: list[str] = field(
        default_factory=lambda: list(BUILTIN_TASKS.keys())
    )
    runs_per_combination: int = 3  # Multiple runs for statistical validity
    temperature: float = 0.3
    max_tokens: int = 768


class ExperimentRunner:
    """Runs lens injection experiments and collects results."""

    def __init__(
        self,
        model,  # ModelProtocol
        lens: LensData | None = None,
        config: ExperimentConfig | None = None,
    ) -> None:
        self.model = model
        self.lens = lens or load_default_lens()
        self.config = config or ExperimentConfig()
        self.scorer = DemoScorer()
        self.results: list[ExperimentResult] = []

    async def run_all(
        self,
        *,
        on_progress: callable | None = None,
    ) -> dict[LensStrategy, ExperimentSummary]:
        """Run all experiments and return summaries by strategy.

        Args:
            on_progress: Optional callback(strategy, task, run_idx, total_runs)

        Returns:
            Dict mapping strategy to its summary statistics.
        """
        total_runs = (
            len(self.config.strategies)
            * len(self.config.tasks)
            * self.config.runs_per_combination
        )
        current_run = 0

        for strategy in self.config.strategies:
            builder = create_prompt_builder(strategy, self.lens)

            for task_name in self.config.tasks:
                task = BUILTIN_TASKS[task_name]

                for run_idx in range(self.config.runs_per_combination):
                    current_run += 1

                    if on_progress:
                        on_progress(
                            strategy=strategy,
                            task=task_name,
                            run_idx=run_idx + 1,
                            current=current_run,
                            total=total_runs,
                        )

                    result = await self._run_single(builder, task, strategy)
                    self.results.append(result)

        return self._compute_summaries()

    async def run_strategy(
        self,
        strategy: LensStrategy,
        *,
        on_progress: callable | None = None,
    ) -> ExperimentSummary:
        """Run experiments for a single strategy.

        Args:
            strategy: The strategy to test.
            on_progress: Optional callback(task, run_idx)

        Returns:
            Summary for this strategy.
        """
        builder = create_prompt_builder(strategy, self.lens)
        strategy_results: list[ExperimentResult] = []

        for task_name in self.config.tasks:
            task = BUILTIN_TASKS[task_name]

            for run_idx in range(self.config.runs_per_combination):
                if on_progress:
                    on_progress(task=task_name, run_idx=run_idx + 1)

                result = await self._run_single(builder, task, strategy)
                strategy_results.append(result)
                self.results.append(result)

        return self._compute_strategy_summary(strategy, strategy_results)

    async def run_single_task(
        self,
        strategy: LensStrategy,
        task_name: str,
    ) -> ExperimentResult:
        """Run a single experiment.

        Args:
            strategy: The strategy to use.
            task_name: The task name.

        Returns:
            Single experiment result.
        """
        builder = create_prompt_builder(strategy, self.lens)
        task = BUILTIN_TASKS.get(task_name)
        if not task:
            raise ValueError(f"Unknown task: {task_name}")

        return await self._run_single(builder, task, strategy)

    async def _run_single(
        self,
        builder,
        task: DemoTask,
        strategy: LensStrategy,
    ) -> ExperimentResult:
        """Run a single experiment iteration."""
        from sunwell.models.protocol import GenerateOptions

        start = time.perf_counter()

        # Check if builder uses proper system prompt separation
        if builder.uses_system_prompt:
            # Use proper system/user split!
            parts = builder.build_prompt_parts(task.prompt)
            result = await self.model.generate(
                parts.user,  # User message only
                options=GenerateOptions(
                    system_prompt=parts.system,  # Lens in system prompt!
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ),
            )
        else:
            # Legacy: everything in one prompt
            prompt = builder.build_prompt(task.prompt)
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ),
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        code = result.content or ""
        usage = result.usage

        # Score the output
        score_result = self.scorer.score(code, task.expected_features)
        achieved = tuple(f for f, present in score_result.features.items() if present)
        missing = tuple(score_result.issues)

        return ExperimentResult(
            strategy=strategy,
            task_name=task.name,
            score=score_result.score,
            features_achieved=achieved,
            features_missing=missing,
            code=code,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            time_ms=elapsed_ms,
        )

    def _compute_summaries(self) -> dict[LensStrategy, ExperimentSummary]:
        """Compute summary statistics for all strategies."""
        by_strategy: dict[LensStrategy, list[ExperimentResult]] = defaultdict(list)

        for r in self.results:
            by_strategy[r.strategy].append(r)

        return {
            strategy: self._compute_strategy_summary(strategy, results)
            for strategy, results in by_strategy.items()
        }

    def _compute_strategy_summary(
        self,
        strategy: LensStrategy,
        results: list[ExperimentResult],
    ) -> ExperimentSummary:
        """Compute summary for a single strategy."""
        if not results:
            return ExperimentSummary(
                strategy=strategy,
                avg_score=0.0,
                success_rate=0.0,
                total_runs=0,
                results=[],
            )

        scores = [r.score for r in results]
        successes = sum(1 for s in scores if s >= 8.0)

        return ExperimentSummary(
            strategy=strategy,
            avg_score=sum(scores) / len(scores),
            success_rate=successes / len(scores),
            total_runs=len(results),
            results=results,
        )


def print_experiment_report(summaries: dict[LensStrategy, ExperimentSummary]) -> str:
    """Generate a formatted report of experiment results.

    Args:
        summaries: Dict of strategy to summary.

    Returns:
        Formatted report string.
    """
    lines = [
        "=" * 70,
        "LENS INJECTION EXPERIMENT RESULTS",
        "=" * 70,
        "",
        f"{'Strategy':<25} {'Avg Score':>10} {'Success %':>10} {'Runs':>6}",
        "-" * 55,
    ]

    # Sort by success rate
    sorted_summaries = sorted(
        summaries.items(),
        key=lambda x: (x[1].success_rate, x[1].avg_score),
        reverse=True,
    )

    for strategy, summary in sorted_summaries:
        lines.append(
            f"{strategy.value:<25} {summary.avg_score:>10.2f} "
            f"{summary.success_rate * 100:>9.1f}% {summary.total_runs:>6}"
        )

    lines.extend([
        "",
        "=" * 70,
        "TOP PERFORMER:",
        f"  {sorted_summaries[0][0].value} with {sorted_summaries[0][1].success_rate * 100:.1f}% success rate",
        "=" * 70,
    ])

    return "\n".join(lines)


def print_detailed_report(
    summaries: dict[LensStrategy, ExperimentSummary],
    *,
    show_code: bool = False,
) -> str:
    """Generate detailed report with per-task breakdown.

    Args:
        summaries: Dict of strategy to summary.
        show_code: Whether to include generated code.

    Returns:
        Detailed report string.
    """
    lines = [
        "=" * 80,
        "DETAILED EXPERIMENT RESULTS",
        "=" * 80,
    ]

    for strategy, summary in sorted(
        summaries.items(),
        key=lambda x: x[1].success_rate,
        reverse=True,
    ):
        lines.extend([
            "",
            f"## {strategy.value}",
            f"   Avg Score: {summary.avg_score:.2f}",
            f"   Success Rate: {summary.success_rate * 100:.1f}%",
            f"   Total Runs: {summary.total_runs}",
            "",
        ])

        # Group by task
        by_task: dict[str, list[ExperimentResult]] = defaultdict(list)
        for r in summary.results:
            by_task[r.task_name].append(r)

        for task_name, results in by_task.items():
            task_scores = [r.score for r in results]
            task_avg = sum(task_scores) / len(task_scores)
            task_success = sum(1 for s in task_scores if s >= 8.0) / len(task_scores)

            lines.append(f"   [{task_name}] avg={task_avg:.1f}, success={task_success * 100:.0f}%")

            if show_code and results:
                lines.append(f"      Code sample:\n{results[0].code[:200]}...")

    return "\n".join(lines)


async def run_quick_comparison(model) -> dict[LensStrategy, ExperimentSummary]:
    """Quick comparison of all strategies with 1 run per task.

    Useful for rapid iteration during development.
    """
    config = ExperimentConfig(
        runs_per_combination=1,
        tasks=["divide", "sort"],  # Quick subset
    )

    runner = ExperimentRunner(model, config=config)

    def on_progress(**kwargs):
        print(f"  Running {kwargs['strategy'].value} on {kwargs['task']}...")

    summaries = await runner.run_all(on_progress=on_progress)

    print(print_experiment_report(summaries))
    return summaries


async def run_full_evaluation(model) -> dict[LensStrategy, ExperimentSummary]:
    """Full evaluation with multiple runs for statistical validity.

    Use for final comparison to determine best strategy.
    """
    config = ExperimentConfig(
        runs_per_combination=3,
        tasks=list(BUILTIN_TASKS.keys()),
    )

    runner = ExperimentRunner(model, config=config)

    def on_progress(**kwargs):
        pct = kwargs["current"] / kwargs["total"] * 100
        print(f"  [{pct:5.1f}%] {kwargs['strategy'].value} / {kwargs['task']} (run {kwargs['run_idx']})")

    summaries = await runner.run_all(on_progress=on_progress)

    print(print_experiment_report(summaries))
    print()
    print(print_detailed_report(summaries))
    return summaries
