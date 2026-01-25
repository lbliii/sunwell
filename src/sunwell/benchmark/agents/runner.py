"""Agent Benchmark Runner (RFC-032).

Extends the benchmark framework to test agent mode capabilities:
- Task decomposition quality
- Dependency graph correctness
- Tool selection accuracy
- Multi-step execution
- Error recovery
"""


import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.foundation.utils import safe_yaml_load
from sunwell.knowledge.project import create_project_from_workspace
from sunwell.planning.naaru import AgentResult, Naaru, Task
from sunwell.planning.naaru.planners import AgentPlanner
from sunwell.tools.execution import ToolExecutor
from sunwell.tools.core.types import ToolPolicy, ToolTrust

# =============================================================================
# Agent Benchmark Types
# =============================================================================


@dataclass(slots=True)
class AgentTaskDefinition:
    """Definition of an agent benchmark task."""

    id: str
    category: str
    subcategory: str
    goal: str
    context: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    complexity: str = "medium"
    timeout_seconds: int = 300

    @classmethod
    def from_yaml(cls, path: Path) -> AgentTaskDefinition:
        """Load task definition from YAML file."""
        data = safe_yaml_load(path)

        task = data.get("task", data)
        return cls(
            id=task["id"],
            category=task.get("category", "agent"),
            subcategory=task.get("subcategory", "planning"),
            goal=task["goal"],
            context=task.get("context", {}),
            evaluation=task.get("evaluation", {}),
            complexity=task.get("complexity", "medium"),
            timeout_seconds=task.get("timeout_seconds", 300),
        )


@dataclass(slots=True)
class PlanningScore:
    """Evaluation of task planning quality."""

    total_tasks: int
    task_count_valid: bool  # Within min/max range
    required_modes_present: bool
    required_tools_present: bool
    has_dependencies: bool
    dependency_chain_length: int

    @property
    def score(self) -> float:
        """Calculate planning score (0-1)."""
        points = 0
        max_points = 5

        if self.task_count_valid:
            points += 1
        if self.required_modes_present:
            points += 1
        if self.required_tools_present:
            points += 1
        if self.has_dependencies:
            points += 1
        if self.dependency_chain_length >= 2:
            points += 1

        return points / max_points


@dataclass(slots=True)
class ExecutionScore:
    """Evaluation of task execution quality."""

    tasks_completed: int
    tasks_failed: int
    tasks_total: int
    files_created: list[str]
    expected_files_created: bool
    content_checks_passed: int
    content_checks_total: int
    execution_time_seconds: float

    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate."""
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_completed / self.tasks_total

    @property
    def content_accuracy(self) -> float:
        """Calculate content check accuracy."""
        if self.content_checks_total == 0:
            return 1.0
        return self.content_checks_passed / self.content_checks_total


@dataclass(slots=True)
class AgentBenchmarkResult:
    """Result from running an agent benchmark task."""

    task_id: str
    goal: str
    planning_score: PlanningScore
    execution_score: ExecutionScore | None
    agent_result: AgentResult | None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def overall_score(self) -> float:
        """Calculate overall benchmark score (0-1)."""
        if self.error:
            return 0.0

        planning_weight = 0.4
        execution_weight = 0.6

        score = self.planning_score.score * planning_weight

        if self.execution_score:
            exec_score = (
                self.execution_score.completion_rate * 0.5
                + self.execution_score.content_accuracy * 0.5
            )
            score += exec_score * execution_weight
        else:
            # Dry-run mode - only planning evaluated
            score = self.planning_score.score

        return score

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "planning_score": {
                "total_tasks": self.planning_score.total_tasks,
                "task_count_valid": self.planning_score.task_count_valid,
                "required_modes_present": self.planning_score.required_modes_present,
                "required_tools_present": self.planning_score.required_tools_present,
                "has_dependencies": self.planning_score.has_dependencies,
                "dependency_chain_length": self.planning_score.dependency_chain_length,
                "score": self.planning_score.score,
            },
            "execution_score": {
                "tasks_completed": self.execution_score.tasks_completed,
                "tasks_failed": self.execution_score.tasks_failed,
                "completion_rate": self.execution_score.completion_rate,
                "content_accuracy": self.execution_score.content_accuracy,
            }
            if self.execution_score
            else None,
            "overall_score": self.overall_score,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Agent Benchmark Runner
# =============================================================================


class AgentBenchmarkRunner:
    """Runner for agent mode benchmarks.

    Evaluates:
    - Planning: How well does the agent decompose goals?
    - Execution: Does the agent complete tasks correctly?
    - Recovery: How does the agent handle failures?

    Example:
        >>> runner = AgentBenchmarkRunner(model=my_model)
        >>> result = await runner.run_task("benchmark/tasks/agent/planning-001.yaml")
        >>> print(f"Score: {result.overall_score:.2f}")
    """

    def __init__(
        self,
        model,
        trust_level: ToolTrust = ToolTrust.WORKSPACE,
        dry_run: bool = False,
    ):
        self.model = model
        self.trust_level = trust_level
        self.dry_run = dry_run

    async def run_task(
        self,
        task_path: Path | str,
        on_progress: callable = None,
    ) -> AgentBenchmarkResult:
        """Run a single agent benchmark task.

        Args:
            task_path: Path to the task YAML file
            on_progress: Optional callback for progress updates

        Returns:
            AgentBenchmarkResult with scores and details
        """
        task_path = Path(task_path)
        task_def = AgentTaskDefinition.from_yaml(task_path)

        output = on_progress or print
        output(f"🎯 Running: {task_def.id}")
        output(f"   Goal: {task_def.goal[:60]}...")

        # Create temporary workspace
        workspace = Path(tempfile.mkdtemp(prefix=f"bench-{task_def.id}-"))

        try:
            # Setup tool executor
            trust = ToolTrust.from_string(task_def.context.get("trust_level", "workspace"))
            project = create_project_from_workspace(workspace)
            tool_executor = ToolExecutor(
                project=project,
                policy=ToolPolicy(trust_level=trust),
            )

            # Create planner
            planner = AgentPlanner(
                model=self.model,
                available_tools=frozenset(tool_executor.get_available_tools()),
            )

            # Phase 1: Plan
            output("   📋 Planning...")
            try:
                tasks = await planner.plan(
                    [task_def.goal],
                    {"cwd": str(workspace)},
                )
            except Exception as e:
                return AgentBenchmarkResult(
                    task_id=task_def.id,
                    goal=task_def.goal,
                    planning_score=PlanningScore(
                        total_tasks=0,
                        task_count_valid=False,
                        required_modes_present=False,
                        required_tools_present=False,
                        has_dependencies=False,
                        dependency_chain_length=0,
                    ),
                    execution_score=None,
                    agent_result=None,
                    error=f"Planning failed: {e}",
                )

            # Evaluate planning
            planning_score = self._evaluate_planning(tasks, task_def)
            output(f"   📊 Planning score: {planning_score.score:.2f}")

            # Phase 2: Execute (unless dry-run)
            execution_score = None
            agent_result = None

            if not self.dry_run:
                output("   ⚡ Executing...")

                naaru = Naaru(
                    workspace=workspace,
                    synthesis_model=self.model,
                    planner=planner,
                    tool_executor=tool_executor,
                )

                agent_result = await naaru.run(
                    goal=task_def.goal,
                    context={"cwd": str(workspace)},
                    max_time_seconds=task_def.timeout_seconds,
                )

                # Evaluate execution
                execution_score = self._evaluate_execution(
                    agent_result,
                    workspace,
                    task_def,
                )
                output(f"   📊 Execution score: {execution_score.completion_rate:.2f}")

            result = AgentBenchmarkResult(
                task_id=task_def.id,
                goal=task_def.goal,
                planning_score=planning_score,
                execution_score=execution_score,
                agent_result=agent_result,
            )

            output(f"   ✅ Overall: {result.overall_score:.2f}")
            return result

        finally:
            # Cleanup workspace
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    def _evaluate_planning(
        self,
        tasks: list[Task],
        task_def: AgentTaskDefinition,
    ) -> PlanningScore:
        """Evaluate task planning quality."""
        eval_config = task_def.evaluation.get("planning", {})

        # Count tasks
        total_tasks = len(tasks)
        min_tasks = eval_config.get("min_tasks", 1)
        max_tasks = eval_config.get("max_tasks", 50)
        task_count_valid = min_tasks <= total_tasks <= max_tasks

        # Check required modes (flexible: research mode OR read_file tool counts as research)
        required_modes = set(eval_config.get("required_modes", []))
        present_modes = {t.mode.value for t in tasks}
        present_tools = set()
        for t in tasks:
            present_tools.update(t.tools)

        # Flexibility: if "research" is required, accept read_file or list_files as equivalent
        research_tools = {"read_file", "list_files", "search_files"}
        if "research" in required_modes and present_tools & research_tools:
            present_modes.add("research")  # Grant credit for using research tools

        required_modes_present = required_modes.issubset(present_modes)

        # Check required tools
        required_tools = set(eval_config.get("required_tools", []))
        required_tools_present = required_tools.issubset(present_tools)

        # Check dependencies (flexible: requires_dependencies means at least one)
        requires_deps = eval_config.get("required_dependencies", False)
        has_dependencies = any(t.depends_on for t in tasks)

        # Calculate dependency chain length
        dependency_chain_length = self._calculate_chain_length(tasks)

        return PlanningScore(
            total_tasks=total_tasks,
            task_count_valid=task_count_valid,
            required_modes_present=required_modes_present,
            required_tools_present=required_tools_present,
            has_dependencies=has_dependencies if requires_deps else True,
            dependency_chain_length=dependency_chain_length,
        )

    def _calculate_chain_length(self, tasks: list[Task]) -> int:
        """Calculate the longest dependency chain."""
        task_map = {t.id: t for t in tasks}

        def chain_length(task_id: str, visited: set) -> int:
            if task_id in visited or task_id not in task_map:
                return 0
            visited.add(task_id)
            task = task_map[task_id]
            if not task.depends_on:
                return 1
            return 1 + max(chain_length(dep, visited.copy()) for dep in task.depends_on)

        if not tasks:
            return 0

        return max(chain_length(t.id, set()) for t in tasks)

    def _evaluate_execution(
        self,
        result: AgentResult,
        workspace: Path,
        task_def: AgentTaskDefinition,
    ) -> ExecutionScore:
        """Evaluate task execution quality."""
        eval_config = task_def.evaluation.get("execution", {})

        # Count task completion
        tasks_completed = result.completed_count
        tasks_failed = result.failed_count
        tasks_total = len(result.tasks)

        # Check created files
        must_create = eval_config.get("must_create_files", [])
        files_created = []
        for f in workspace.rglob("*"):
            if f.is_file():
                files_created.append(str(f.relative_to(workspace)))

        expected_files_created = all(
            any(f.endswith(expected) or expected in f for f in files_created)
            for expected in must_create
        )

        # Check file contents
        content_checks = eval_config.get("must_contain_in_files", {})
        checks_passed = 0
        checks_total = 0

        for filename, required_strings in content_checks.items():
            for created in files_created:
                if filename in created:
                    try:
                        content = (workspace / created).read_text()
                        for required in required_strings:
                            checks_total += 1
                            if required in content:
                                checks_passed += 1
                    except Exception:
                        pass

        return ExecutionScore(
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            tasks_total=tasks_total,
            files_created=files_created,
            expected_files_created=expected_files_created,
            content_checks_passed=checks_passed,
            content_checks_total=checks_total,
            execution_time_seconds=result.execution_time_seconds,
        )

    async def run_all(
        self,
        tasks_dir: Path | str = "benchmark/tasks/agent",
        on_progress: callable = None,
    ) -> list[AgentBenchmarkResult]:
        """Run all agent benchmark tasks.

        Args:
            tasks_dir: Directory containing task YAML files
            on_progress: Optional callback for progress updates

        Returns:
            List of AgentBenchmarkResult for each task
        """
        tasks_dir = Path(tasks_dir)
        task_files = sorted(tasks_dir.glob("*.yaml"))

        results = []
        for task_file in task_files:
            result = await self.run_task(task_file, on_progress)
            results.append(result)

        return results

    def summarize(self, results: list[AgentBenchmarkResult]) -> dict[str, Any]:
        """Generate summary statistics from benchmark results."""
        if not results:
            return {"error": "No results to summarize"}

        scores = [r.overall_score for r in results if not r.error]
        planning_scores = [r.planning_score.score for r in results if not r.error]

        errors = [r for r in results if r.error]

        return {
            "total_tasks": len(results),
            "successful_tasks": len(scores),
            "failed_tasks": len(errors),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "average_planning_score": sum(planning_scores) / len(planning_scores)
            if planning_scores
            else 0,
            "by_category": self._group_by_category(results),
        }

    def _group_by_category(self, results: list[AgentBenchmarkResult]) -> dict[str, float]:
        """Group scores by task category."""
        from collections import defaultdict

        by_cat = defaultdict(list)
        for r in results:
            if not r.error:
                # Extract category from task_id (e.g., "agent-planning-001" -> "planning")
                parts = r.task_id.split("-")
                if len(parts) >= 2:
                    category = parts[1]
                    by_cat[category].append(r.overall_score)

        return {cat: sum(scores) / len(scores) for cat, scores in by_cat.items()}


# =============================================================================
# CLI Integration
# =============================================================================


async def run_agent_benchmark(
    model,
    tasks_dir: str = "benchmark/tasks/agent",
    dry_run: bool = False,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run agent benchmarks and save results.

    Args:
        model: The LLM model to use
        tasks_dir: Directory with task YAML files
        dry_run: If True, only evaluate planning (no execution)
        output_dir: Directory to save results (optional)

    Returns:
        Summary statistics dict
    """
    from rich.console import Console

    console = Console()

    runner = AgentBenchmarkRunner(
        model=model,
        dry_run=dry_run,
    )

    console.print("\n[bold]Agent Benchmark Suite[/bold]")
    console.print(f"Mode: {'Planning Only' if dry_run else 'Full Execution'}\n")

    results = await runner.run_all(
        tasks_dir=tasks_dir,
        on_progress=console.print,
    )

    summary = runner.summarize(results)

    # Print summary
    console.print("\n[bold]Summary[/bold]")
    console.print(f"  Total: {summary['total_tasks']} tasks")
    console.print(f"  Passed: {summary['successful_tasks']}")
    console.print(f"  Failed: {summary['failed_tasks']}")
    console.print(f"  Average Score: {summary['average_score']:.2f}")

    if summary.get("by_category"):
        console.print("\n[bold]By Category[/bold]")
        for cat, score in summary["by_category"].items():
            console.print(f"  {cat}: {score:.2f}")

    # Save results
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results_file = (
            output_path / f"agent-benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        with open(results_file, "w") as f:
            json.dump(
                {
                    "summary": summary,
                    "results": [r.to_dict() for r in results],
                },
                f,
                indent=2,
            )

        console.print(f"\n[dim]Results saved to: {results_file}[/dim]")

    return summary
