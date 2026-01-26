"""Benchmark Runner (RFC-018).

Executes benchmark tasks across multiple conditions:
- Bare: No system prompt (raw model capability)
- Flat: Full lens context injected
- Selective: Sunwell's selective retrieval approach
- Competitor: Optional external baseline
"""


from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.benchmark.types import (
    BenchmarkResults,
    BenchmarkTask,
    Condition,
    ConditionOutput,
    NaaruMode,
    PromptStrategy,
    RetrievalMetrics,
    RoutingMetrics,
    RubricDimension,
    TaskCategory,
    TaskEvaluation,
    TaskResult,
)
from sunwell.foundation.utils import safe_yaml_load
from sunwell.models import ModelProtocol

if TYPE_CHECKING:
    from sunwell.foundation.schema.loader import LensLoader


from sunwell.benchmark.execution import ExecutionRunner


@dataclass
class BenchmarkRunner:
    """Execute benchmark tasks across conditions.

    Usage:
        runner = BenchmarkRunner(
            model=model,
            lens_loader=loader,
            tasks_dir=Path("benchmark/tasks"),
            output_dir=Path("benchmark/results"),
            lens_dir=Path("lenses"),
            prompt_strategy=PromptStrategy.CONSTRAINTS,  # Best for small models
        )
        results = await runner.run_suite(category="docs")

    Prompt strategies (from prompting research):
        - RAW: Just dump heuristics as-is
        - GUIDED: "Apply these principles" meta-instructions
        - COT: Chain-of-thought (THINK → PLAN → CODE → VERIFY)
        - CONSTRAINTS: Extract MUST/MUST NOT (best for small models)
        - FEW_SHOT: Include example of applying heuristics

    Naaru modes:
        - NONE: Single generation
        - HARMONIC: Multi-persona voting (Self-Consistency, 3x tokens)
        - RESONANCE: Feedback loop (1.5x tokens)
        - FULL: Both (4x tokens)
    """

    model: ModelProtocol
    lens_loader: LensLoader
    tasks_dir: Path
    output_dir: Path
    lens_dir: Path = Path("lenses")  # Directory containing lens files
    top_k: int = 3  # Number of heuristics to retrieve
    seed: int | None = 42  # For reproducibility where supported
    router_model: ModelProtocol | None = None  # RFC-020: Tiny LLM for routing
    prompt_strategy: PromptStrategy = PromptStrategy.CONSTRAINTS  # Best for small models
    naaru_mode: NaaruMode = NaaruMode.NONE  # Coordination layer

    _execution_runner: ExecutionRunner | None = field(default=None, init=False)
    """Execution runner for condition execution."""

    async def run_task(
        self,
        task: BenchmarkTask,
        skip_conditions: tuple[Condition, ...] = (),
    ) -> TaskResult:
        """Run a single task against all conditions.

        Args:
            task: The benchmark task to run
            skip_conditions: Conditions to skip (e.g., for ablation tests)

        Returns:
            TaskResult with outputs from all conditions
        """
        # Load lens for this task - resolve relative to lens_dir
        lens_path = self.lens_dir / task.lens
        lens = self.lens_loader.load(lens_path)

        outputs: dict[str, ConditionOutput] = {}
        retrieval_metrics: RetrievalMetrics | None = None

        # Initialize execution runner if needed
        if not self._execution_runner:
            self._execution_runner = ExecutionRunner(
                model=self.model,
                lens_loader=self.lens_loader,
                lens_dir=self.lens_dir,
                top_k=self.top_k,
                router_model=self.router_model,
                prompt_strategy=self.prompt_strategy,
                naaru_mode=self.naaru_mode,
            )

        # Condition A: No system prompt (bare model)
        if Condition.BARE not in skip_conditions:
            outputs[Condition.BARE.value] = await self._execution_runner.run_condition(
                task=task,
                system_prompt="",
                condition=Condition.BARE,
            )

        # Condition B: Flat injection (all heuristics)
        if Condition.FLAT not in skip_conditions:
            full_context = lens.to_context()
            outputs[Condition.FLAT.value] = await self._execution_runner.run_condition(
                task=task,
                system_prompt=full_context,
                condition=Condition.FLAT,
            )

        # Condition C: Selective retrieval (Sunwell's approach)
        if Condition.SELECTIVE not in skip_conditions:
            selective_context, retrieval_metrics = await self._execution_runner.selective_retrieve(
                lens=lens,
                query=task.prompt,
            )
            outputs[Condition.SELECTIVE.value] = await self._execution_runner.run_condition(
                task=task,
                system_prompt=selective_context,
                condition=Condition.SELECTIVE,
            )

        # Condition D: Routed retrieval (RFC-030 UnifiedRouter)
        routing_metrics: RoutingMetrics | None = None
        if Condition.ROUTED not in skip_conditions and self.router_model is not None:
            routed_context, routing_metrics, routed_retrieval = await self._execution_runner.routed_retrieve(
                task=task,
            )
            outputs[Condition.ROUTED.value] = await self._execution_runner.run_condition(
                task=task,
                system_prompt=routed_context,
                condition=Condition.ROUTED,
            )
            # Use routed retrieval metrics if selective wasn't run
            if retrieval_metrics is None:
                retrieval_metrics = routed_retrieval

        # Condition E: Self-directed expertise retrieval (RFC-027)
        self_directed_metrics = None
        if Condition.SELF_DIRECTED not in skip_conditions:
            try:
                self_directed_output, self_directed_metrics = await self._execution_runner.run_self_directed(
                    task=task,
                    lens=lens,
                )
                outputs[Condition.SELF_DIRECTED.value] = self_directed_output
            except ImportError:
                # RFC-027 tools not fully installed
                pass
            except Exception:
                # Log but don't fail the whole benchmark
                pass

        # Condition F: Prefetch expertise via Tool Orchestrator Shard (RFC-031)
        prefetch_metrics = None
        if Condition.PREFETCH not in skip_conditions:
            try:
                prefetch_output, prefetch_metrics = await self._execution_runner.run_prefetch(
                    task=task,
                    lens=lens,
                )
                outputs[Condition.PREFETCH.value] = prefetch_output
            except ImportError as e:
                # RFC-031 Tool Orchestrator not available
                import sys
                print(f"Prefetch ImportError: {e}", file=sys.stderr)
            except Exception as e:
                # Log but don't fail the whole benchmark
                import sys
                print(f"Prefetch Error: {e}", file=sys.stderr)

        return TaskResult(
            task_id=task.id,
            outputs=outputs,
            retrieval_metrics=retrieval_metrics,
            routing_metrics=routing_metrics,
            self_directed_metrics=self_directed_metrics,
            prefetch_metrics=prefetch_metrics,
        )

    # Execution methods are now in ExecutionRunner

    async def run_suite(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
        max_tasks: int | None = None,
    ) -> BenchmarkResults:
        """Run all tasks in a category or the full suite.

        Args:
            category: Filter to specific category (docs, review, code)
            task_ids: Filter to specific task IDs
            max_tasks: Limit number of tasks (for quick runs)

        Returns:
            BenchmarkResults with all task outcomes
        """
        tasks = self._load_tasks(category=category, task_ids=task_ids)

        if max_tasks:
            tasks = tasks[:max_tasks]

        results: list[TaskResult] = []

        for i, task in enumerate(tasks):
            print(f"  [{i+1}/{len(tasks)}] Running {task.id}...", end=" ", flush=True)
            try:
                result = await self.run_task(task)
                results.append(result)
                print("✓")
            except Exception as e:
                print(f"✗ {e}")

        return BenchmarkResults(
            timestamp=datetime.now().isoformat(),
            model=self.model.model_id,
            task_results=tuple(results),
        )

    async def run_ablation(
        self,
        task: BenchmarkTask,
        k_values: tuple[int, ...] = (1, 3, 5),
    ) -> dict[int, TaskResult]:
        """Run retrieval ablation test with different top_k values.

        Tests: What minimum retrieval depth is needed to maintain quality?
        """
        results: dict[int, TaskResult] = {}

        original_k = self.top_k

        for k in k_values:
            self.top_k = k
            result = await self.run_task(
                task,
                skip_conditions=(Condition.BARE, Condition.FLAT),
            )
            results[k] = result

        self.top_k = original_k
        return results

    def _load_tasks(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
    ) -> list[BenchmarkTask]:
        """Load benchmark tasks from YAML files.

        Searches benchmark/tasks/ for .yaml files.
        """
        tasks: list[BenchmarkTask] = []

        # Find all YAML files in tasks directory
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
                category = TaskCategory(category_str)
            except ValueError:
                category = TaskCategory.DOCUMENTATION

            return BenchmarkTask(
                id=task_data["id"],
                category=category,
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


async def create_runner(
    model: ModelProtocol | None = None,
    lens_loader: LensLoader | None = None,
    tasks_dir: Path | str = "benchmark/tasks",
    output_dir: Path | str = "benchmark/results",
    lens_dir: Path | str = "lenses",
    router_model: ModelProtocol | None = None,
) -> BenchmarkRunner:
    """Create a BenchmarkRunner with default configuration.

    If model is not provided, uses config defaults.
    If lens_loader is not provided, creates one with default paths.
    If router_model is provided, enables the ROUTED condition (RFC-020).
    """
    if model is None:
        from sunwell.foundation.config import get_config
        from sunwell.models import OllamaModel

        cfg = get_config()
        model_name = cfg.model.default_model if cfg else "gemma3:4b"
        model = OllamaModel(model=model_name)

    if lens_loader is None:
        from sunwell.foundation.schema.loader import LensLoader
        lens_loader = LensLoader()

    return BenchmarkRunner(
        model=model,
        lens_loader=lens_loader,
        tasks_dir=Path(tasks_dir),
        output_dir=Path(output_dir),
        lens_dir=Path(lens_dir),
        router_model=router_model,
    )
