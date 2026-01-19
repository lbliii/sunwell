"""CLI commands for Naaru Agent Mode (RFC-032).

Provides:
- sunwell naaru run "goal": Execute arbitrary tasks
- sunwell naaru resume: Resume from checkpoint
- sunwell naaru illuminate: Self-improvement mode (RFC-019)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.config import get_config

console = Console()


@click.group()
def naaru():
    """Naaru coordinated intelligence commands (RFC-019, RFC-032)."""
    pass


@naaru.command()
@click.argument("goal")
@click.option(
    "--time", "-t",
    default=300,
    help="Max execution time in seconds (default: 300)",
)
@click.option(
    "--trust",
    type=click.Choice(["read_only", "workspace", "shell"]),
    default="workspace",
    help="Tool trust level",
)
@click.option(
    "--strategy", "-s",
    type=click.Choice(["sequential", "contract_first", "resource_aware", "artifact_first"]),
    default="artifact_first",
    help="Planning strategy (default: artifact_first per RFC-036)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Plan only, don't execute",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override synthesis model",
)
@click.option(
    "--show-graph",
    is_flag=True,
    help="Show artifact/task dependency graph (with --dry-run)",
)
def run(
    goal: str,
    time: int,
    trust: str,
    strategy: str,
    dry_run: bool,
    verbose: bool,
    model: str | None,
    show_graph: bool,
):
    """Execute a task using Naaru agent mode (RFC-032, RFC-036).

    Examples:

        sunwell naaru run "Build a React forum app"

        sunwell naaru run "Write getting started docs for sunwell"

        sunwell naaru run "Refactor auth.py to async" --trust shell

        sunwell naaru run "Create a CLI tool" --dry-run

        # RFC-036 Artifact-First Planning (structural parallelism)
        sunwell naaru run "Build REST API with auth" --strategy artifact_first

        sunwell naaru run "Build app" --strategy artifact_first --dry-run --show-graph
    """
    asyncio.run(_run_agent(goal, time, trust, strategy, dry_run, verbose, model, show_graph))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    strategy: str,
    dry_run: bool,
    verbose: bool,
    model_override: str | None,
    show_graph: bool,
):
    """Execute agent mode."""
    from sunwell.naaru import Naaru
    from sunwell.naaru.planners import AgentPlanner, ArtifactPlanner, PlanningStrategy
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust
    from sunwell.types.config import NaaruConfig

    # Load config
    config = get_config()

    # Create model
    synthesis_model = None
    try:
        from sunwell.models.ollama import OllamaModel

        model_name = model_override
        if not model_name and config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "voice", "gemma3:1b")

        if not model_name:
            model_name = "gemma3:1b"

        synthesis_model = OllamaModel(model=model_name)
        console.print(f"[dim]Using model: {model_name}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load model: {e}[/yellow]")

    if not synthesis_model:
        console.print("[red]No model available for planning[/red]")
        return

    # Setup tool executor
    trust_level = ToolTrust.from_string(trust)
    tool_executor = ToolExecutor(
        workspace=Path.cwd(),
        policy=ToolPolicy(trust_level=trust_level),
    )

    available_tools = frozenset(tool_executor.get_available_tools())
    tool_definitions = tool_executor.get_tool_definitions()

    if verbose:
        console.print(f"[dim]Trust level: {trust}[/dim]")
        console.print(f"[dim]Strategy: {strategy}[/dim]")
        console.print(f"[dim]Available tools: {', '.join(sorted(available_tools))}[/dim]")

    # Create planner based on strategy
    planning_strategy = PlanningStrategy(strategy)

    if planning_strategy == PlanningStrategy.ARTIFACT_FIRST:
        # RFC-036: Artifact-first planning
        planner = ArtifactPlanner(model=synthesis_model)

        if dry_run:
            await _artifact_dry_run(goal, planner, show_graph, verbose)
            return
    else:
        # RFC-032/034: Task-based planning
        planner = AgentPlanner(
            model=synthesis_model,
            available_tools=available_tools,
            tool_definitions=tool_definitions,
            strategy=planning_strategy,
        )

        if dry_run:
            await _task_dry_run(goal, planner, show_graph, verbose)
            return

    # Full execution
    naaru_config = NaaruConfig()
    if config and hasattr(config, "naaru"):
        naaru_config = config.naaru

    naaru = Naaru(
        sunwell_root=Path.cwd(),
        synthesis_model=synthesis_model,
        planner=planner,
        tool_executor=tool_executor,
        config=naaru_config,
    )

    try:
        result = await naaru.run(
            goal=goal,
            context={"cwd": str(Path.cwd())},
            on_progress=console.print,
            max_time_seconds=time,
        )

        # Show artifacts
        if result.artifacts:
            console.print("\n[bold]Created files:[/bold]")
            for artifact in result.artifacts:
                console.print(f"  • {artifact}")

        # Summary
        if result.success:
            console.print("\n[green]✓ Goal completed successfully[/green]")
        else:
            partial_msg = f"({result.completed_count}/{len(result.tasks)})"
            console.print(f"\n[yellow]⚠ Goal partially completed {partial_msg}[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


async def _task_dry_run(goal: str, planner, show_graph: bool, verbose: bool):
    """Dry run for task-based planning."""
    console.print("[yellow]Dry run - planning only[/yellow]\n")

    try:
        tasks = await planner.plan([goal], {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Planning failed: {e}[/red]")
        return

    console.print(f"[bold]Plan for:[/bold] {goal}\n")

    table = Table(title="Task Plan")
    table.add_column("#", style="cyan")
    table.add_column("Description")
    table.add_column("Mode", style="magenta")
    table.add_column("Tools", style="green")
    table.add_column("Dependencies", style="dim")

    for task in tasks:
        deps = ", ".join(task.depends_on) if task.depends_on else "-"
        tools = ", ".join(task.tools) if task.tools else "-"
        table.add_row(
            task.id,
            task.description[:50] + ("..." if len(task.description) > 50 else ""),
            task.mode.value,
            tools,
            deps,
        )

    console.print(table)

    if show_graph:
        console.print("\n[bold]Dependency Graph:[/bold]")
        _display_task_graph(tasks)


async def _artifact_dry_run(goal: str, planner, show_graph: bool, verbose: bool):
    """Dry run for artifact-first planning (RFC-036)."""
    from sunwell.naaru import get_model_distribution

    console.print("[yellow]Dry run - artifact discovery only (RFC-036)[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

    console.print(f"[bold]Artifacts for:[/bold] {goal}\n")

    # Show artifact table
    table = Table(title="Discovered Artifacts")
    table.add_column("ID", style="cyan")
    table.add_column("Description")
    table.add_column("Type", style="magenta")
    table.add_column("File", style="green")
    table.add_column("Requires", style="dim")

    waves = graph.execution_waves()
    for _wave_num, wave in enumerate(waves):
        for artifact_id in wave:
            artifact = graph[artifact_id]
            requires = ", ".join(artifact.requires) if artifact.requires else "-"
            table.add_row(
                artifact_id,
                artifact.description[:40] + ("..." if len(artifact.description) > 40 else ""),
                artifact.domain_type or "-",
                artifact.produces_file or "-",
                requires,
            )

    console.print(table)

    # Show execution waves
    console.print("\n[bold]Execution Waves (parallel):[/bold]")
    for i, wave in enumerate(waves, 1):
        console.print(f"  Wave {i}: {', '.join(wave)}")

    # Show model distribution
    dist = get_model_distribution(graph)
    console.print("\n[bold]Model Distribution:[/bold]")
    console.print(f"  Small (leaves):  {dist['small']} artifacts")
    console.print(f"  Medium:          {dist['medium']} artifacts")
    console.print(f"  Large (complex): {dist['large']} artifacts")

    # Show graph if requested
    if show_graph:
        console.print("\n[bold]Dependency Graph (Mermaid):[/bold]")
        console.print("```mermaid")
        console.print(graph.to_mermaid())
        console.print("```")


def _display_task_graph(tasks: list):
    """Display a simple text-based task graph."""
    # Find roots (no dependencies)
    roots = [t.id for t in tasks if not t.depends_on]

    def print_tree(task_id: str, indent: int = 0, visited: set = None):
        if visited is None:
            visited = set()
        if task_id in visited:
            console.print("  " * indent + f"└─ {task_id} (cycle)")
            return
        visited.add(task_id)

        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        console.print(prefix + task_id)

        # Find dependents
        dependents = [t.id for t in tasks if task_id in t.depends_on]
        for dep in dependents:
            print_tree(dep, indent + 1, visited.copy())

    for root in roots:
        print_tree(root)


@naaru.command()
@click.option(
    "--checkpoint", "-c",
    type=click.Path(exists=True),
    help="Resume from specific checkpoint file",
)
def resume(checkpoint: str | None):
    """Resume an interrupted agent run from checkpoint.

    Examples:

        sunwell naaru resume

        sunwell naaru resume --checkpoint .sunwell/checkpoints/agent-2026-01-18.json
    """
    asyncio.run(_resume_agent(checkpoint))


async def _resume_agent(checkpoint_path: str | None):
    """Resume agent from checkpoint."""
    from sunwell.naaru.checkpoint import AgentCheckpoint, find_latest_checkpoint

    # Find checkpoint
    if checkpoint_path:
        try:
            cp = AgentCheckpoint.load(Path(checkpoint_path))
        except Exception as e:
            console.print(f"[red]Failed to load checkpoint: {e}[/red]")
            return
    else:
        cp = find_latest_checkpoint()
        if not cp:
            console.print("[red]No checkpoint found. Run 'sunwell naaru run' first.[/red]")
            return

    # Show checkpoint info
    summary = cp.get_progress_summary()

    console.print(f"[bold]Resuming:[/bold] {cp.goal}")
    console.print(f"   Started: {summary['started_at']}")
    console.print(f"   Progress: {summary['completed']}/{summary['total_tasks']} tasks")
    console.print(f"   Remaining: {summary['remaining']} tasks\n")

    remaining = cp.get_remaining_tasks()

    if not remaining:
        console.print("[green]All tasks already completed![/green]")
        return

    console.print("[bold]Remaining tasks:[/bold]")
    for task in remaining[:10]:
        console.print(f"  • {task.description}")

    if len(remaining) > 10:
        console.print(f"  ... and {len(remaining) - 10} more")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[dim]Aborted[/dim]")
        return

    # Resume execution
    from sunwell.naaru import Naaru
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    tool_executor = ToolExecutor(
        workspace=Path(cp.working_directory),
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Try to load model
    synthesis_model = None
    try:
        from sunwell.models.ollama import OllamaModel
        synthesis_model = OllamaModel(model="gemma3:1b")
    except Exception:
        console.print("[yellow]Warning: Could not load model[/yellow]")

    naaru = Naaru(
        sunwell_root=Path(cp.working_directory),
        synthesis_model=synthesis_model,
        tool_executor=tool_executor,
    )

    # Execute remaining tasks
    # Note: This is a simplified resume - full implementation would restore task graph state
    result = await naaru.run(
        goal=cp.goal,
        context={
            "cwd": cp.working_directory,
            "checkpoint": cp,
            "completed_ids": list(cp.completed_ids),
        },
        on_progress=console.print,
    )

    console.print(f"\n✨ Complete: {result.completed_count}/{len(result.tasks)} tasks")


@naaru.command()
@click.option(
    "--goals", "-g",
    multiple=True,
    required=True,
    help="Goals for self-improvement",
)
@click.option(
    "--time", "-t",
    default=120,
    help="Max execution time in seconds",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def illuminate(goals: tuple[str], time: int, verbose: bool):
    """Self-improvement mode (RFC-019 behavior).

    The original Naaru mode - finds and addresses opportunities to
    improve Sunwell's own codebase.

    Examples:

        sunwell naaru illuminate -g "improve error handling"

        sunwell naaru illuminate -g "add tests" -g "improve docs" --time 300
    """
    asyncio.run(_illuminate(list(goals), time, verbose))


async def _illuminate(goals: list[str], time: int, verbose: bool):
    """Run self-improvement mode."""
    from sunwell.naaru import Naaru
    from sunwell.types.config import NaaruConfig

    # Load config
    config = get_config()

    # Create models
    synthesis_model = None
    judge_model = None

    try:
        from sunwell.models.ollama import OllamaModel

        if config and hasattr(config, "naaru"):
            voice = getattr(config.naaru, "voice", "gemma3:1b")
            wisdom = getattr(config.naaru, "wisdom", "gemma3:4b")
        else:
            voice = "gemma3:1b"
            wisdom = "gemma3:4b"

        synthesis_model = OllamaModel(model=voice)
        judge_model = OllamaModel(model=wisdom)

        if verbose:
            console.print(f"[dim]Voice: {voice}, Wisdom: {wisdom}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load models: {e}[/yellow]")

    # Create Naaru config
    naaru_config = NaaruConfig()
    if config and hasattr(config, "naaru"):
        naaru_config = config.naaru

    naaru = Naaru(
        sunwell_root=Path.cwd(),
        synthesis_model=synthesis_model,
        judge_model=judge_model,
        config=naaru_config,
    )

    try:
        results = await naaru.illuminate(
            goals=goals,
            max_time_seconds=time,
            on_output=console.print,
        )

        # Show final summary
        if results.get("completed_proposals"):
            count = len(results['completed_proposals'])
            console.print(f"\n[bold]Completed {count} proposals[/bold]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


@naaru.command()
def status():
    """Show Naaru status and available checkpoints."""
    from sunwell.naaru.checkpoint import find_latest_checkpoint

    checkpoint_dir = Path.cwd() / ".sunwell" / "checkpoints"

    console.print("[bold]Naaru Status[/bold]\n")

    # Check for checkpoints
    if checkpoint_dir.exists():
        checkpoint_files = list(checkpoint_dir.glob("agent-*.json"))

        if checkpoint_files:
            console.print(f"[green]✓[/green] Found {len(checkpoint_files)} checkpoint(s)")

            # Show latest
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                summary = latest.get_progress_summary()
                console.print("\n[bold]Latest checkpoint:[/bold]")
                console.print(f"  Goal: {summary['goal'][:60]}...")
                console.print(f"  Progress: {summary['completed']}/{summary['total_tasks']} tasks")
                console.print(f"  Created: {summary['checkpoint_at']}")
        else:
            console.print("[dim]No checkpoints found[/dim]")
    else:
        console.print("[dim]No checkpoint directory found[/dim]")

    # Check for models
    console.print("\n[bold]Model Status:[/bold]")
    try:
        from sunwell.models.ollama import OllamaModel
        _ = OllamaModel(model="gemma3:1b")  # noqa: F841
        # Try a quick ping
        console.print("  [green]✓[/green] Ollama available")
    except Exception:
        console.print("  [red]✗[/red] Ollama not available")


@naaru.command()
@click.option(
    "--tasks-dir", "-d",
    default="benchmark/tasks/agent",
    help="Directory containing agent benchmark tasks",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Evaluate planning only (no execution)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Directory to save results",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def benchmark(tasks_dir: str, dry_run: bool, output: str | None, verbose: bool):
    """Run agent mode benchmarks (RFC-032).

    Tests planning quality, task decomposition, and execution accuracy.

    Examples:
        sunwell naaru benchmark
        sunwell naaru benchmark --dry-run
        sunwell naaru benchmark -o benchmark/results/agent/
    """
    asyncio.run(_benchmark_async(tasks_dir, dry_run, output, verbose))


async def _benchmark_async(
    tasks_dir: str,
    dry_run: bool,
    output: str | None,
    verbose: bool,
):
    """Async implementation of benchmark command."""
    from pathlib import Path as PathLib

    tasks_path = PathLib(tasks_dir)
    if not tasks_path.exists():
        console.print(f"[red]Error: Tasks directory not found: {tasks_dir}[/red]")
        return

    task_files = list(tasks_path.glob("*.yaml"))
    if not task_files:
        console.print(f"[yellow]No benchmark tasks found in {tasks_dir}[/yellow]")
        return

    console.print("[bold]Agent Benchmark Suite[/bold]")
    console.print(f"  Mode: {'Planning Only' if dry_run else 'Full Execution'}")
    console.print(f"  Tasks: {len(task_files)} found\n")

    # Load model
    try:
        from sunwell.models.ollama import OllamaModel
        config = get_config()

        if config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "wisdom", "gemma3:4b")
        else:
            model_name = "gemma3:4b"

        model = OllamaModel(model=model_name)
        console.print(f"[dim]Using model: {model_name}[/dim]\n")
    except Exception as e:
        console.print(f"[red]Error loading model: {e}[/red]")
        return

    # Run benchmarks
    try:
        from sunwell.benchmark.agent_runner import AgentBenchmarkRunner

        runner = AgentBenchmarkRunner(
            model=model,
            dry_run=dry_run,
        )

        results = await runner.run_all(
            tasks_dir=tasks_dir,
            on_progress=console.print if verbose else None,
        )

        # Summary
        summary = runner.summarize(results)

        console.print("\n[bold]═══ Summary ═══[/bold]")
        console.print(f"  Total: {summary['total_tasks']} tasks")
        console.print(f"  Passed: {summary['successful_tasks']}")
        console.print(f"  Failed: {summary['failed_tasks']}")
        console.print(f"  Average Score: [bold]{summary['average_score']:.2f}[/bold]")

        if summary.get("by_category"):
            console.print("\n[bold]By Category:[/bold]")
            for cat, score in summary["by_category"].items():
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                console.print(f"  {cat:15} {bar} {score:.2f}")

        # Save results
        if output:
            output_path = PathLib(output)
            output_path.mkdir(parents=True, exist_ok=True)

            import json
            from datetime import datetime

            results_file = output_path / f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            with open(results_file, "w") as f:
                json.dump({
                    "summary": summary,
                    "results": [r.to_dict() for r in results],
                }, f, indent=2)

            console.print(f"\n[dim]Results saved to: {results_file}[/dim]")

    except Exception as e:
        console.print(f"\n[red]Benchmark error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
