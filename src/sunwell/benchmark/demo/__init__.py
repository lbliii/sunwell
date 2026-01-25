"""Demo module for showcasing the Prism Principle (RFC-095).

The `sunwell demo` command proves cognitive architecture matters
by running a side-by-side comparison of single-shot prompting vs
Sunwell's Resonance refinement on the same model.

Example:
    >>> from sunwell.demo import DemoRunner
    >>> runner = DemoRunner(model)
    >>> comparison = await runner.run("divide")
    >>> presenter.present(comparison)
"""

from sunwell.benchmark.demo.executor import ComponentBreakdown, DemoComparison, DemoExecutor, DemoResult
from sunwell.benchmark.demo.files import DemoFiles, cleanup_old_demos, load_demo_code, save_demo_code
from sunwell.benchmark.demo.history import (
    DemoHistoryEntry,
    get_history_summary,
    load_history,
    save_demo_result,
)
from sunwell.benchmark.demo.judge import DemoJudge, DemoJudgment
from sunwell.benchmark.demo.presenter import DemoPresenter, JsonPresenter, QuietPresenter
from sunwell.benchmark.demo.scorer import DemoScore, DemoScorer
from sunwell.benchmark.demo.tasks import BUILTIN_TASKS, DemoTask, get_task, list_tasks

__all__ = [
    # Tasks
    "DemoTask",
    "BUILTIN_TASKS",
    "get_task",
    "list_tasks",
    # Scoring
    "DemoScore",
    "DemoScorer",
    # Judge
    "DemoJudge",
    "DemoJudgment",
    # Execution
    "DemoExecutor",
    "DemoResult",
    "ComponentBreakdown",
    "DemoComparison",
    # Presentation
    "DemoPresenter",
    "QuietPresenter",
    "JsonPresenter",
    # History
    "DemoHistoryEntry",
    "save_demo_result",
    "load_history",
    "get_history_summary",
    # Files
    "DemoFiles",
    "save_demo_code",
    "load_demo_code",
    "cleanup_old_demos",
    # Runner
    "DemoRunner",
    "run_demo",
]


class DemoRunner:
    """High-level interface for running demos.

    Orchestrates the executor, scorer, and presenter to provide
    a complete demo experience.

    Example:
        >>> runner = DemoRunner(model, verbose=True)
        >>> comparison = await runner.run("divide")
        >>> runner.present(comparison)
    """

    def __init__(
        self,
        model,
        *,
        verbose: bool = False,
        quiet: bool = False,
        json_output: bool = False,
    ) -> None:
        """Initialize the demo runner.

        Args:
            model: A model implementing the ModelProtocol.
            verbose: Show detailed output including judge feedback.
            quiet: Show minimal output (just scores).
            json_output: Output as JSON for scripting.
        """
        self.model = model
        self.verbose = verbose
        self.quiet = quiet
        self.json_output = json_output

        self.executor = DemoExecutor(model, verbose=verbose)
        self.scorer = DemoScorer()

        # Select presenter based on output mode
        if json_output:
            self.presenter = JsonPresenter()
        elif quiet:
            self.presenter = QuietPresenter()
        else:
            self.presenter = DemoPresenter(verbose=verbose)

    async def run(
        self,
        task_name_or_prompt: str,
        *,
        on_progress=None,
    ) -> DemoComparison:
        """Run a complete demo comparison.

        Args:
            task_name_or_prompt: Either a built-in task name or custom prompt.
            on_progress: Optional callback for progress updates.

        Returns:
            DemoComparison with results from both methods.
        """
        # Get the task
        task = get_task(task_name_or_prompt)

        # Run single-shot
        single_shot_result = await self.executor.run_single_shot(
            task,
            on_progress=on_progress,
        )

        # Score single-shot
        single_shot_score = self.scorer.score(
            single_shot_result.code,
            task.expected_features,
        )

        # Run Sunwell
        sunwell_result = await self.executor.run_sunwell(
            task,
            on_progress=on_progress,
        )

        # Score Sunwell
        sunwell_score = self.scorer.score(
            sunwell_result.code,
            task.expected_features,
        )

        return DemoComparison(
            task=task,
            single_shot=single_shot_result,
            sunwell=sunwell_result,
            single_score=single_shot_score,
            sunwell_score=sunwell_score,
        )

    def present(self, comparison: DemoComparison, model_name: str = "unknown") -> None:
        """Present the demo comparison results.

        Args:
            comparison: The comparison result to present.
            model_name: Name of the model for display.
        """
        self.presenter.present(comparison, model_name)


async def run_demo(
    model,
    task: str = "divide",
    *,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
    model_name: str = "unknown",
    on_progress=None,
) -> DemoComparison:
    """Convenience function to run a complete demo.

    Args:
        model: A model implementing the ModelProtocol.
        task: Task name or custom prompt.
        verbose: Show detailed output.
        quiet: Show minimal output.
        json_output: Output as JSON.
        model_name: Name of the model for display.
        on_progress: Optional callback for progress updates.

    Returns:
        DemoComparison with results.
    """
    runner = DemoRunner(
        model,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
    )

    comparison = await runner.run(task, on_progress=on_progress)
    runner.present(comparison, model_name)

    return comparison
