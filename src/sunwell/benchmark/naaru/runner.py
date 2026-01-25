"""Naaru Benchmark Runner (RFC-027).

The main orchestrator for the Naaru benchmark suite. Runs tasks across
all 7 conditions and collects Naaru-specific metrics.

Example:
    >>> runner = NaaruBenchmarkRunner(
    ...     model=model,
    ...     judge_model=judge,
    ...     lens_loader=loader,
    ...     tasks_dir=Path("benchmark/tasks"),
    ... )
    >>> results = await runner.run_suite(max_tasks=30)
"""


from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.foundation.utils import safe_json_dumps, safe_yaml_load
from sunwell.benchmark.naaru.conditions import ConditionRunner
from sunwell.benchmark.naaru.types import (
    NaaruBenchmarkResults,
    NaaruCondition,
    NaaruConditionOutput,
    NaaruTaskResult,
)
from sunwell.benchmark.types import (
    BenchmarkTask,
    RubricDimension,
    TaskCategory,
    TaskEvaluation,
)

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol
    from sunwell.foundation.schema.loader import LensLoader


@dataclass
class NaaruBenchmarkRunner:
    """Execute benchmark tasks across Naaru conditions.

    This is the main entry point for RFC-027. It runs tasks across
    7 conditions (A-G) to validate Naaru's quality claims.

    Attributes:
        model: The synthesis model (e.g., gemma3:1b)
        judge_model: The judge model for evaluation (e.g., gemma3:4b)
        lens_loader: Loader for lens files
        tasks_dir: Directory containing task YAML files
        output_dir: Directory for saving results
        lens_dir: Directory containing lens files
        max_resonance_attempts: Max refinement attempts for resonance

    Example:
        >>> runner = NaaruBenchmarkRunner(
        ...     model=OllamaModel("gemma3:1b"),
        ...     judge_model=OllamaModel("gemma3:4b"),
        ...     lens_loader=LensLoader(),
        ...     tasks_dir=Path("benchmark/tasks"),
        ... )
        >>>
        >>> # Quick smoke test
        >>> results = await runner.run_suite(max_tasks=5)
        >>>
        >>> # Full ablation
        >>> results = await runner.run_suite(
        ...     conditions=[
        ...         NaaruCondition.BASELINE,
        ...         NaaruCondition.HARMONIC,
        ...         NaaruCondition.NAARU_FULL,
        ...     ],
        ... )
    """

    model: ModelProtocol
    judge_model: ModelProtocol
    lens_loader: LensLoader
    tasks_dir: Path
    output_dir: Path = Path("benchmark/results/naaru")
    lens_dir: Path = Path("lenses")
    max_resonance_attempts: int = 2

    # Internal
    _condition_runner: ConditionRunner | None = None

    def _get_condition_runner(self) -> ConditionRunner:
        """Lazily create the condition runner."""
        if self._condition_runner is None:
            self._condition_runner = ConditionRunner(
                model=self.model,
                judge_model=self.judge_model,
                max_resonance_attempts=self.max_resonance_attempts,
            )
        return self._condition_runner

    async def run_task(
        self,
        task: BenchmarkTask,
        conditions: list[NaaruCondition] | None = None,
    ) -> NaaruTaskResult:
        """Run a single task against specified conditions.

        Args:
            task: The benchmark task to run
            conditions: Conditions to run (default: all 7)

        Returns:
            NaaruTaskResult with outputs from all conditions
        """
        if conditions is None:
            conditions = list(NaaruCondition)

        # Load lens for this task
        lens_path = self.lens_dir / task.lens
        lens: Lens | None = None
        if lens_path.exists():
            lens = self.lens_loader.load(lens_path)

        runner = self._get_condition_runner()
        outputs: dict[NaaruCondition, NaaruConditionOutput] = {}

        for condition in conditions:
            # Skip lens conditions if no lens available
            if lens is None and condition in (
                NaaruCondition.BASELINE_LENS,
                NaaruCondition.HARMONIC_LENS,
                NaaruCondition.NAARU_FULL_LENS,
            ):
                continue

            try:
                output = await runner.run(condition, task, lens)
                outputs[condition] = output
            except Exception as e:
                # Log error but continue with other conditions
                print(f"  Error in {condition.value}: {e}")

        return NaaruTaskResult(
            task_id=task.id,
            outputs=outputs,
        )

    async def run_suite(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
        conditions: list[NaaruCondition] | None = None,
        max_tasks: int | None = None,
    ) -> NaaruBenchmarkResults:
        """Run the full benchmark suite.

        Args:
            category: Filter to specific category (docs, code, review)
            task_ids: Filter to specific task IDs
            conditions: Conditions to run (default: all 7)
            max_tasks: Limit number of tasks (for quick runs)

        Returns:
            NaaruBenchmarkResults with all task outcomes
        """
        tasks = self._load_tasks(category=category, task_ids=task_ids)

        if max_tasks:
            tasks = tasks[:max_tasks]

        if conditions is None:
            conditions = list(NaaruCondition)

        results: list[NaaruTaskResult] = []

        for i, task in enumerate(tasks):
            print(f"  [{i+1}/{len(tasks)}] Running {task.id}...", end=" ", flush=True)
            try:
                result = await self.run_task(task, conditions)
                results.append(result)

                # Show condition summary
                conds_run = len(result.outputs)
                print(f"✓ ({conds_run} conditions)")
            except Exception as e:
                print(f"✗ {e}")

        return NaaruBenchmarkResults(
            timestamp=datetime.now().isoformat(),
            model=self.model.model_id,
            judge_model=self.judge_model.model_id,
            conditions=conditions,
            results=results,
            config={
                "max_resonance_attempts": self.max_resonance_attempts,
                "tasks_dir": str(self.tasks_dir),
                "lens_dir": str(self.lens_dir),
            },
        )

    async def run_ablation(
        self,
        max_tasks: int = 10,
    ) -> NaaruBenchmarkResults:
        """Run ablation study (incremental technique enablement).

        Tests conditions in order to isolate each technique's contribution:
        A → C → E → F (without lens)
        B → D → G (with lens)

        Args:
            max_tasks: Number of tasks for ablation

        Returns:
            NaaruBenchmarkResults with ablation conditions
        """
        # Core ablation: techniques without lens
        core_conditions = [
            NaaruCondition.BASELINE,
            NaaruCondition.HARMONIC,
            NaaruCondition.RESONANCE,
            NaaruCondition.NAARU_FULL,
        ]

        # Lens ablation: same techniques with lens
        lens_conditions = [
            NaaruCondition.BASELINE_LENS,
            NaaruCondition.HARMONIC_LENS,
            NaaruCondition.NAARU_FULL_LENS,
        ]

        all_conditions = core_conditions + lens_conditions

        return await self.run_suite(
            conditions=all_conditions,
            max_tasks=max_tasks,
        )

    async def run_quick(
        self,
        n_tasks: int = 5,
    ) -> NaaruBenchmarkResults:
        """Quick smoke test (small sample, all conditions).

        Validates that all conditions work before full run.

        Args:
            n_tasks: Number of tasks to run

        Returns:
            NaaruBenchmarkResults with quick results
        """
        return await self.run_suite(max_tasks=n_tasks)

    def _load_tasks(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
    ) -> list[BenchmarkTask]:
        """Load benchmark tasks from YAML files.

        Reuses RFC-018 task registry format.
        """
        tasks: list[BenchmarkTask] = []

        for yaml_path in self.tasks_dir.rglob("*.yaml"):
            task = self._load_task_file(yaml_path)
            if task is None:
                continue

            # Filter by category
            if category and task.category.value != category:
                continue

            # Filter by task ID
            if task_ids and task.id not in task_ids:
                continue

            tasks.append(task)

        return sorted(tasks, key=lambda t: t.id)

    def _load_task_file(self, path: Path) -> BenchmarkTask | None:
        """Load a single task from a YAML file."""
        try:
            data = safe_yaml_load(path)

            if not data or "task" not in data:
                return None

            task_data = data["task"]

            # Parse evaluation
            eval_data = task_data.get("evaluation", {})
            rubric = tuple(
                RubricDimension(
                    dimension=r["dimension"],
                    weight=r.get("weight", 0.25),
                    criteria=r.get("criteria", ""),
                )
                for r in eval_data.get("rubric", [])
            )

            evaluation = TaskEvaluation(
                rubric=rubric,
                must_contain=tuple(eval_data.get("must_contain", [])),
                must_not_contain=tuple(eval_data.get("must_not_contain", [])),
                ground_truth_issues=tuple(eval_data.get("ground_truth_issues", [])),
            )

            # Parse category
            category_str = task_data.get("category", "documentation")
            try:
                task_category = TaskCategory(category_str)
            except ValueError:
                task_category = TaskCategory.DOCUMENTATION

            return BenchmarkTask(
                id=task_data["id"],
                category=task_category,
                subcategory=task_data.get("subcategory", "general"),
                prompt=task_data["prompt"],
                lens=task_data.get("lens", "tech-writer.lens"),
                evaluation=evaluation,
                context_files=tuple(task_data.get("context_files", [])),
                test_suite=task_data.get("test_suite"),
                target_persona=task_data.get("target_persona"),
                source_path=path,
            )
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
            return None

    def save_results(
        self,
        results: NaaruBenchmarkResults,
        output_dir: Path | None = None,
    ) -> Path:
        """Save benchmark results to disk.

        Creates a timestamped directory with:
        - raw_outputs.jsonl: Per-task outputs
        - condition_scores.json: Per-condition aggregates
        - config.json: Run configuration

        Args:
            results: Results to save
            output_dir: Override default output directory

        Returns:
            Path to the results directory
        """
        out_dir = output_dir or self.output_dir
        timestamp = datetime.now().strftime("%Y-%m-%d")
        results_dir = out_dir / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)

        # Save raw outputs as JSONL
        outputs_path = results_dir / "raw_outputs.jsonl"
        with open(outputs_path, "w") as f:
            for task_result in results.results:
                f.write(safe_json_dumps(task_result.to_dict()) + "\n")

        # Save condition summary
        summary = self._compute_condition_summary(results)
        summary_path = results_dir / "condition_scores.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Save config
        config_path = results_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump({
                "timestamp": results.timestamp,
                "model": results.model,
                "judge_model": results.judge_model,
                "n_tasks": results.n_tasks,
                "conditions": [c.value for c in results.conditions],
                "config": results.config,
            }, f, indent=2)

        print(f"Results saved to {results_dir}")
        return results_dir

    def _compute_condition_summary(
        self,
        results: NaaruBenchmarkResults,
    ) -> dict:
        """Compute per-condition summary statistics."""
        summary: dict = {}

        for condition in results.conditions:
            tokens_list: list[int] = []
            times_list: list[float] = []
            consensus_list: list[float] = []
            refinement_list: list[int] = []

            for task_result in results.results:
                output = task_result.outputs.get(condition)
                if output is None:
                    continue

                tokens_list.append(output.tokens_used)
                times_list.append(output.time_seconds)

                if output.harmonic_metrics:
                    consensus_list.append(output.harmonic_metrics.consensus_strength)

                if output.resonance_metrics:
                    refinement_list.append(output.resonance_metrics.refinement_attempts)

            if not tokens_list:
                continue

            summary[condition.value] = {
                "n_tasks": len(tokens_list),
                "mean_tokens": sum(tokens_list) / len(tokens_list),
                "total_tokens": sum(tokens_list),
                "mean_time_seconds": sum(times_list) / len(times_list),
                "total_time_seconds": sum(times_list),
            }

            if consensus_list:
                summary[condition.value]["mean_consensus_strength"] = (
                    sum(consensus_list) / len(consensus_list)
                )

            if refinement_list:
                summary[condition.value]["mean_refinement_attempts"] = (
                    sum(refinement_list) / len(refinement_list)
                )
                summary[condition.value]["refinement_rate"] = (
                    sum(1 for r in refinement_list if r > 0) / len(refinement_list)
                )

        return summary


async def create_naaru_runner(
    model: ModelProtocol | None = None,
    judge_model: ModelProtocol | None = None,
    lens_loader: LensLoader | None = None,
    tasks_dir: Path | str = "benchmark/tasks",
    output_dir: Path | str = "benchmark/results/naaru",
    lens_dir: Path | str = "lenses",
) -> NaaruBenchmarkRunner:
    """Create a NaaruBenchmarkRunner with default configuration.

    If models are not provided, uses Ollama with default models:
    - model: gemma3:1b (synthesis)
    - judge_model: gemma3:4b (evaluation)

    Args:
        model: Synthesis model (default: gemma3:1b via Ollama)
        judge_model: Judge model (default: gemma3:4b via Ollama)
        lens_loader: Lens loader (default: creates new LensLoader)
        tasks_dir: Directory containing task files
        output_dir: Directory for results
        lens_dir: Directory containing lens files

    Returns:
        Configured NaaruBenchmarkRunner
    """
    if model is None:
        from sunwell.foundation.config import get_config
        from sunwell.models.ollama import OllamaModel

        cfg = get_config()
        model_name = cfg.naaru.voice if cfg else "gemma3:1b"
        model = OllamaModel(model=model_name)

    if judge_model is None:
        from sunwell.foundation.config import get_config
        from sunwell.models.ollama import OllamaModel

        cfg = get_config()
        judge_name = cfg.naaru.wisdom if cfg else "gemma3:4b"
        judge_model = OllamaModel(model=judge_name)

    if lens_loader is None:
        from sunwell.foundation.schema.loader import LensLoader
        lens_loader = LensLoader()

    return NaaruBenchmarkRunner(
        model=model,
        judge_model=judge_model,
        lens_loader=lens_loader,
        tasks_dir=Path(tasks_dir),
        output_dir=Path(output_dir),
        lens_dir=Path(lens_dir),
    )
