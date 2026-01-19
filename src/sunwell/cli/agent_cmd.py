"""CLI commands for Agent Mode (RFC-032, RFC-037).

This module provides the 'sunwell agent' command group.
Renamed from 'naaru' for clarity (RFC-037).

Provides:
- sunwell agent run "goal": Execute arbitrary tasks (same as bare 'sunwell "goal"')
- sunwell agent resume: Resume from checkpoint
- sunwell agent illuminate: Self-improvement mode (RFC-019)
- sunwell agent status: Show agent state
- sunwell agent benchmark: Agent benchmarks
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
def agent() -> None:
    """Agent commands for task execution and management.
    
    For most use cases, you can skip this command group entirely:
    
    \b
        sunwell "Build a REST API"          # Same as: sunwell agent run "..."
        sunwell "Build an app" --plan       # Same as: sunwell agent run "..." --dry-run
    
    The agent command group is for advanced operations like resuming
    interrupted runs or running self-improvement mode.
    """
    pass


@agent.command()
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
    type=click.Choice(["sequential", "contract_first", "resource_aware", "artifact_first", "harmonic"]),
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
# RFC-038: Harmonic Planning options
@click.option(
    "--harmonic",
    is_flag=True,
    help="Enable harmonic planning (multi-candidate optimization, RFC-038)",
)
@click.option(
    "--candidates", "-c",
    default=5,
    help="Number of plan candidates for harmonic planning (default: 5)",
)
@click.option(
    "--refine", "-r",
    default=1,
    help="Refinement rounds for harmonic planning (default: 1, 0 to disable)",
)
# RFC-040: Plan Persistence options
@click.option(
    "--incremental", "-i",
    is_flag=True,
    help="Only rebuild changed artifacts (RFC-040)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force full rebuild (ignore saved state)",
)
@click.option(
    "--show-plan",
    is_flag=True,
    help="Show plan with cost estimate (alias for --dry-run with estimates)",
)
@click.option(
    "--diff-plan",
    is_flag=True,
    help="Show changes vs previous plan",
)
@click.option(
    "--plan-id",
    default=None,
    help="Explicit plan identifier (default: hash of goal)",
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
    harmonic: bool,
    candidates: int,
    refine: int,
    incremental: bool,
    force: bool,
    show_plan: bool,
    diff_plan: bool,
    plan_id: str | None,
) -> None:
    """Execute a task using agent mode.

    \b
    For most cases, you can use the simpler form:
        sunwell "Build a REST API"
    
    \b
    This command provides additional control:
        sunwell agent run "Build API" --strategy contract_first
        sunwell agent run "Build API" --dry-run --show-graph

    \b
    For harmonic planning (RFC-038):
        sunwell agent run "Build API" --harmonic
        sunwell agent run "Build API" --harmonic --candidates 7 --refine 2

    \b
    For incremental builds (RFC-040):
        sunwell agent run "Build API" --incremental
        sunwell agent run "Build API" --show-plan
        sunwell agent run "Build API" --diff-plan
        sunwell agent run "Build API" --force

    Examples:

    \b
        sunwell agent run "Build a React forum app"
        sunwell agent run "Write getting started docs"
        sunwell agent run "Refactor auth.py to async" --trust shell
        sunwell agent run "Create a CLI tool" --dry-run
        sunwell agent run "Build app" --dry-run --show-graph
        sunwell agent run "Build app" --harmonic --verbose
        sunwell agent run "Build app" --incremental --verbose
    """
    # Override strategy if --harmonic flag is set
    if harmonic:
        strategy = "harmonic"

    # --show-plan implies --dry-run
    if show_plan or diff_plan:
        dry_run = True

    asyncio.run(_run_agent(
        goal, time, trust, strategy, dry_run, verbose, model, show_graph,
        candidates, refine, incremental, force, show_plan, diff_plan, plan_id,
    ))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    strategy: str,
    dry_run: bool,
    verbose: bool,
    model_override: str | None,
    show_graph: bool,
    candidates: int = 5,
    refine: int = 1,
    incremental: bool = False,
    force: bool = False,
    show_plan: bool = False,
    diff_plan: bool = False,
    plan_id: str | None = None,
) -> None:
    """Execute agent mode."""
    from sunwell.naaru import Naaru
    from sunwell.naaru.planners import (
        AgentPlanner,
        ArtifactPlanner,
        HarmonicPlanner,
        PlanningStrategy,
        VarianceStrategy,
    )
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
        if incremental:
            console.print("[dim]Incremental mode: enabled (RFC-040)[/dim]")

    # Create planner based on strategy
    planning_strategy = PlanningStrategy(strategy)

    if planning_strategy == PlanningStrategy.HARMONIC:
        # RFC-038: Harmonic planning (multi-candidate optimization)
        planner = HarmonicPlanner(
            model=synthesis_model,
            candidates=candidates,
            refinement_rounds=refine,
            variance=VarianceStrategy.PROMPTING,
        )

        if verbose:
            console.print(f"[dim]Harmonic: {candidates} candidates, {refine} refinement rounds[/dim]")

        if dry_run and not show_plan:
            await _harmonic_dry_run(goal, planner, show_graph, verbose)
            return

    elif planning_strategy == PlanningStrategy.ARTIFACT_FIRST:
        # RFC-036: Artifact-first planning
        planner = ArtifactPlanner(model=synthesis_model)

        if dry_run and not show_plan and not diff_plan:
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

    # RFC-040: Show plan with cost estimates
    if show_plan or diff_plan:
        await _show_plan_preview(goal, planner, plan_id, diff_plan, show_graph, verbose)
        return

    # RFC-040: Incremental execution
    if incremental and planning_strategy == PlanningStrategy.ARTIFACT_FIRST:
        await _incremental_run(
            goal, planner, plan_id, force, verbose, time, tool_executor
        )
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


async def _task_dry_run(goal: str, planner, show_graph: bool, verbose: bool) -> None:
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


async def _artifact_dry_run(goal: str, planner, show_graph: bool, verbose: bool) -> None:
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


async def _show_plan_preview(
    goal: str,
    planner,
    plan_id: str | None,
    diff_plan: bool,
    show_graph: bool,
    verbose: bool,
) -> None:
    """Show plan preview with cost estimates (RFC-040)."""
    from sunwell.naaru import get_model_distribution
    from sunwell.naaru.incremental import PlanPreview
    from sunwell.naaru.persistence import PlanStore, hash_goal

    console.print("[yellow]Plan preview - RFC-040[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

    # Create preview with cost estimates
    store = PlanStore()
    goal_hash = plan_id or hash_goal(goal)
    preview = PlanPreview.create(graph, goal, store)

    console.print(f"[bold]📋 Execution Plan:[/bold] {goal}\n")

    # Show waves
    for i, wave in enumerate(preview.waves, 1):
        parallel = "⚡" if len(wave) > 1 else "→"
        console.print(f"Wave {i} {parallel}")
        for artifact_id in wave:
            artifact = graph[artifact_id]
            from sunwell.naaru.artifacts import select_model_tier
            tier = select_model_tier(artifact, graph)
            desc = artifact.description[:40] + "..." if len(artifact.description) > 40 else artifact.description
            console.print(f"  [{tier}] {artifact_id}: {desc}")
        console.print()

    # Show estimates
    console.print("[bold]📊 Estimates[/bold]")
    console.print(f"  Artifacts: {len(graph)}")
    console.print(f"  Waves: {len(preview.waves)}")
    console.print(f"  Parallelization: {preview.parallelization_factor:.1f}x")
    console.print(f"  Model mix: {preview.model_distribution}")
    console.print(f"  Est. tokens: ~{preview.estimated_tokens:,}")
    console.print(f"  Est. cost: ~${preview.estimated_cost_usd:.3f}")
    console.print(f"  Est. time: ~{preview.estimated_duration_seconds:.0f}s")

    # Show changes vs previous (if requested and exists)
    if diff_plan and preview.previous:
        console.print("\n[bold]🔄 Changes vs Previous[/bold]")
        changes = preview.changes
        if changes:
            console.print(f"  Added: {len(changes.added)}")
            console.print(f"  Contract changed: {len(changes.contract_changed)}")
            console.print(f"  Deps changed: {len(changes.deps_changed)}")
            console.print(f"  Output modified: {len(changes.output_modified)}")
            console.print(f"  Removed: {len(changes.removed)}")
            console.print(f"\n  [green]To rebuild: {len(preview.to_rebuild)}[/green]")
            console.print(f"  [dim]Unchanged: {preview.skip_count}[/dim]")
            console.print(f"  [bold]Savings: {preview.savings_percent:.0f}%[/bold]")
        else:
            console.print("  [dim]No changes detected[/dim]")
    elif diff_plan:
        console.print("\n[dim]No previous plan to compare[/dim]")

    # Show graph if requested
    if show_graph:
        console.print("\n[bold]Dependency Graph (Mermaid):[/bold]")
        console.print("```mermaid")
        console.print(graph.to_mermaid())
        console.print("```")


async def _incremental_run(
    goal: str,
    planner,
    plan_id: str | None,
    force: bool,
    verbose: bool,
    max_time: int,
    tool_executor,
) -> None:
    """Run with incremental rebuild support (RFC-040)."""
    from sunwell.naaru.incremental import (
        ChangeDetector,
        IncrementalExecutor,
        PlanPreview,
        compute_rebuild_set,
    )
    from sunwell.naaru.persistence import PlanStore, hash_goal

    console.print("[bold]🔄 Incremental execution (RFC-040)[/bold]\n")

    # Discover graph
    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

    store = PlanStore()
    goal_hash = plan_id or hash_goal(goal)

    # Check for previous execution
    previous = store.load(goal_hash) if not force else None
    if previous:
        detector = ChangeDetector()
        changes = detector.detect(graph, previous)
        to_rebuild = compute_rebuild_set(graph, changes, previous)

        skip_count = len(graph) - len(to_rebuild)
        console.print(f"📊 Found previous execution")
        console.print(f"   Unchanged: {skip_count} artifacts")
        console.print(f"   To rebuild: {len(to_rebuild)} artifacts")

        if changes.all_changed:
            console.print("\n[bold]Changes detected:[/bold]")
            if changes.added:
                console.print(f"   ✨ Added: {', '.join(sorted(changes.added)[:5])}")
            if changes.contract_changed:
                console.print(f"   📝 Contract: {', '.join(sorted(changes.contract_changed)[:5])}")
            if changes.output_modified:
                console.print(f"   📄 Modified: {', '.join(sorted(changes.output_modified)[:5])}")

        if not to_rebuild:
            console.print("\n[green]✓ All artifacts up to date![/green]")
            return
    else:
        console.print("[dim]No previous execution found - full build[/dim]")

    # Create artifact creation function
    async def create_artifact(spec):
        """Create an artifact using the planner."""
        # This is a simplified implementation
        # In practice, this would use the planner's create method
        result = await planner.create_artifact(spec, {})
        return result

    # Execute with incremental support
    executor = IncrementalExecutor(
        store=store,
        trace_enabled=verbose,
    )

    try:
        result = await executor.execute(
            graph=graph,
            create_fn=create_artifact,
            goal=goal,
            force_rebuild=force,
            on_progress=console.print if verbose else None,
        )

        # Summary
        console.print(f"\n[bold]═══ Summary ═══[/bold]")
        console.print(f"  Completed: {len(result.completed)}")
        console.print(f"  Failed: {len(result.failed)}")
        console.print(f"  Model distribution: {result.model_distribution}")

        if result.failed:
            console.print("\n[red]Failed artifacts:[/red]")
            for aid, error in result.failed.items():
                console.print(f"  ✗ {aid}: {error[:50]}")

        if len(result.failed) == 0:
            console.print("\n[green]✓ Incremental build complete[/green]")
        else:
            console.print("\n[yellow]⚠ Build completed with errors[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted - progress saved[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


async def _harmonic_dry_run(goal: str, planner, show_graph: bool, verbose: bool) -> None:
    """Dry run for harmonic planning (RFC-038)."""
    from sunwell.naaru import get_model_distribution

    console.print("[yellow]Dry run - harmonic planning (RFC-038)[/yellow]")
    console.print(f"[dim]Generating {planner.candidates} candidates...[/dim]\n")

    try:
        graph, metrics = await planner.plan_with_metrics(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Harmonic planning failed: {e}[/red]")
        return

    console.print(f"[bold]🎵 Harmonic Plan for:[/bold] {goal}\n")

    # Show metrics summary
    console.print("[bold]📊 Plan Metrics:[/bold]")
    console.print(f"  Score: [bold]{metrics.score:.1f}[/bold]")
    console.print(f"  Critical path depth: {metrics.depth}")
    console.print(f"  Parallel leaves: {metrics.leaf_count}/{metrics.artifact_count} ({metrics.parallelism_factor:.0%})")
    console.print(f"  Balance factor: {metrics.balance_factor:.2f}")
    console.print(f"  Estimated waves: {metrics.estimated_waves}")
    if metrics.file_conflicts > 0:
        console.print(f"  [yellow]File conflicts: {metrics.file_conflicts}[/yellow]")
    console.print()

    # Show artifact table
    table = Table(title="Selected Plan Artifacts")
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


def _display_task_graph(tasks: list) -> None:
    """Display a simple text-based task graph."""
    # Find roots (no dependencies)
    roots = [t.id for t in tasks if not t.depends_on]

    def print_tree(task_id: str, indent: int = 0, visited: set | None = None) -> None:
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


@agent.command()
@click.option(
    "--checkpoint", "-c",
    type=click.Path(exists=True),
    help="Resume from specific checkpoint file (task-based)",
)
@click.option(
    "--plan-id",
    default=None,
    help="Resume specific plan by ID (artifact-based, RFC-040)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def resume(checkpoint: str | None, plan_id: str | None, verbose: bool) -> None:
    """Resume an interrupted agent run from checkpoint.

    Supports two modes:
    - Task-based (RFC-032): --checkpoint option
    - Artifact-based (RFC-040): --plan-id option

    Examples:

    \b
        sunwell agent resume                                    # Latest plan
        sunwell agent resume --plan-id my-api                   # Specific plan
        sunwell agent resume --checkpoint .sunwell/checkpoints/agent-*.json
    """
    asyncio.run(_resume_agent(checkpoint, plan_id, verbose))


async def _resume_agent(checkpoint_path: str | None, plan_id: str | None, verbose: bool) -> None:
    """Resume agent from checkpoint."""
    # RFC-040: Artifact-based resume
    if plan_id or (not checkpoint_path):
        # Try artifact-based resume first
        from sunwell.naaru.persistence import PlanStore, get_latest_execution

        store = PlanStore()

        if plan_id:
            execution = store.load(plan_id)
        else:
            execution = get_latest_execution()

        if execution:
            await _resume_artifact_execution(execution, verbose)
            return
        elif plan_id:
            console.print(f"[red]No plan found with ID: {plan_id}[/red]")
            return
        # Fall through to task-based resume

    # RFC-032: Task-based resume
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
            console.print("[red]No checkpoint found. Run 'sunwell \"goal\"' first.[/red]")
            return

    # Show checkpoint info
    summary = cp.get_progress_summary()

    console.print(f"[bold]Resuming (task-based):[/bold] {cp.goal}")
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


async def _resume_artifact_execution(execution, verbose: bool) -> None:
    """Resume artifact-based execution (RFC-040)."""
    from sunwell.naaru.persistence import (
        ExecutionStatus,
        PlanStore,
        resume_execution,
    )

    console.print(f"[bold]Resuming (artifact-based):[/bold] {execution.goal}")
    console.print(f"   Status: {execution.status.value}")
    console.print(f"   Progress: {len(execution.completed)}/{len(execution.graph)} artifacts")
    console.print(f"   Progress: {execution.progress_percent:.0f}%\n")

    remaining = execution.get_remaining_artifacts()

    if not remaining:
        console.print("[green]All artifacts already completed![/green]")
        return

    # Show execution waves
    resume_wave = execution.get_resume_wave()
    waves = execution.graph.execution_waves()
    console.print(f"[bold]Resume from wave {resume_wave + 1}/{len(waves)}[/bold]")

    console.print("\n[bold]Remaining artifacts:[/bold]")
    for aid in remaining[:10]:
        artifact = execution.graph[aid]
        console.print(f"  • {aid}: {artifact.description[:40]}...")

    if len(remaining) > 10:
        console.print(f"  ... and {len(remaining) - 10} more")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[dim]Aborted[/dim]")
        return

    # Create artifact creation function
    # This is a simplified implementation - would need proper planner integration
    from sunwell.models.ollama import OllamaModel
    from sunwell.naaru.planners import ArtifactPlanner

    try:
        model = OllamaModel(model="gemma3:1b")
        planner = ArtifactPlanner(model=model)
    except Exception as e:
        console.print(f"[red]Failed to load model: {e}[/red]")
        return

    async def create_artifact(spec):
        """Create an artifact using the planner."""
        result = await planner.create_artifact(spec, {})
        return result

    # Resume execution
    try:
        result = await resume_execution(
            execution=execution,
            create_fn=create_artifact,
            on_progress=console.print if verbose else None,
        )

        # Save updated execution
        store = PlanStore()
        execution.update_from_result(result)
        store.save(execution)

        # Summary
        console.print(f"\n[bold]═══ Summary ═══[/bold]")
        console.print(f"  Completed: {len(result.completed)}")
        console.print(f"  Failed: {len(result.failed)}")

        if len(result.failed) == 0:
            console.print("\n[green]✓ Execution complete[/green]")
        else:
            console.print("\n[yellow]⚠ Execution completed with errors[/yellow]")
            for aid, error in result.failed.items():
                console.print(f"  ✗ {aid}: {error[:50]}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted - progress saved[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


@agent.command()
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
def illuminate(goals: tuple[str, ...], time: int, verbose: bool) -> None:
    """Self-improvement mode (RFC-019 behavior).

    The original Naaru mode - finds and addresses opportunities to
    improve Sunwell's own codebase.

    Examples:

    \b
        sunwell agent illuminate -g "improve error handling"
        sunwell agent illuminate -g "add tests" -g "improve docs" --time 300
    """
    asyncio.run(_illuminate(list(goals), time, verbose))


async def _illuminate(goals: list[str], time: int, verbose: bool) -> None:
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


@agent.command()
def status() -> None:
    """Show agent status and available checkpoints."""
    from sunwell.naaru.checkpoint import find_latest_checkpoint
    from sunwell.naaru.persistence import PlanStore

    checkpoint_dir = Path.cwd() / ".sunwell" / "checkpoints"
    store = PlanStore()

    console.print("[bold]Agent Status[/bold]\n")

    # Check for saved plans (RFC-040)
    plans = store.list_recent(limit=5)
    if plans:
        console.print(f"[green]✓[/green] Found {len(plans)} saved plan(s)")
        console.print("\n[bold]Recent plans:[/bold]")
        for plan in plans[:3]:
            status_icon = "✓" if plan.is_complete else "◐"
            console.print(f"  [{status_icon}] {plan.goal[:50]}...")
            console.print(f"      ID: {plan.goal_hash} | Progress: {plan.progress_percent:.0f}%")
    else:
        console.print("[dim]No saved plans found[/dim]")

    # Check for checkpoints
    if checkpoint_dir.exists():
        checkpoint_files = list(checkpoint_dir.glob("agent-*.json"))

        if checkpoint_files:
            console.print(f"\n[green]✓[/green] Found {len(checkpoint_files)} checkpoint(s)")

            # Show latest
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                summary = latest.get_progress_summary()
                console.print("\n[bold]Latest checkpoint:[/bold]")
                console.print(f"  Goal: {summary['goal'][:60]}...")
                console.print(f"  Progress: {summary['completed']}/{summary['total_tasks']} tasks")
                console.print(f"  Created: {summary['checkpoint_at']}")
        else:
            console.print("\n[dim]No task checkpoints found[/dim]")
    else:
        console.print("\n[dim]No checkpoint directory found[/dim]")

    # Check for models
    console.print("\n[bold]Model Status:[/bold]")
    try:
        from sunwell.models.ollama import OllamaModel
        _ = OllamaModel(model="gemma3:1b")  # noqa: F841
        console.print("  [green]✓[/green] Ollama available")
    except Exception:
        console.print("  [red]✗[/red] Ollama not available")


@agent.command(name="plans")
@click.option("--list", "-l", "list_plans", is_flag=True, help="List saved plans")
@click.option("--clean", is_flag=True, help="Clean old plans (>7 days)")
@click.option("--delete", "-d", "delete_id", help="Delete a specific plan by ID")
@click.option("--show", "-s", "show_id", help="Show details of a specific plan")
def plans_cmd(list_plans: bool, clean: bool, delete_id: str | None, show_id: str | None) -> None:
    """Manage saved execution plans (RFC-040).

    Examples:

    \b
        sunwell agent plans --list
        sunwell agent plans --show abc123
        sunwell agent plans --delete abc123
        sunwell agent plans --clean
    """
    from sunwell.naaru.persistence import PlanStore

    store = PlanStore()

    if show_id:
        execution = store.load(show_id)
        if not execution:
            console.print(f"[red]Plan not found: {show_id}[/red]")
            return

        console.print(f"[bold]Plan: {execution.goal_hash}[/bold]\n")
        console.print(f"  Goal: {execution.goal}")
        console.print(f"  Status: {execution.status.value}")
        console.print(f"  Created: {execution.created_at}")
        console.print(f"  Updated: {execution.updated_at}")
        console.print(f"\n[bold]Progress:[/bold]")
        console.print(f"  Artifacts: {len(execution.graph)}")
        console.print(f"  Completed: {len(execution.completed)}")
        console.print(f"  Failed: {len(execution.failed)}")
        console.print(f"  Progress: {execution.progress_percent:.0f}%")

        if execution.failed:
            console.print("\n[bold]Failed artifacts:[/bold]")
            for aid, error in list(execution.failed.items())[:5]:
                console.print(f"  ✗ {aid}: {error[:40]}...")

        console.print(f"\n[bold]Model distribution:[/bold]")
        for tier, count in execution.model_distribution.items():
            console.print(f"  {tier}: {count}")
        return

    if delete_id:
        if store.delete(delete_id):
            console.print(f"[green]✓[/green] Deleted plan: {delete_id}")
        else:
            console.print(f"[yellow]Plan not found: {delete_id}[/yellow]")
        return

    if clean:
        count = store.clean_old(max_age_hours=168.0)  # 7 days
        console.print(f"[green]✓[/green] Cleaned {count} old plan(s)")
        return

    # Default: list plans
    plans = store.list_recent(limit=20)
    if not plans:
        console.print("[dim]No saved plans found[/dim]")
        return

    table = Table(title="Saved Plans")
    table.add_column("ID", style="cyan")
    table.add_column("Goal")
    table.add_column("Status", style="magenta")
    table.add_column("Progress")
    table.add_column("Updated")

    for plan in plans:
        status_style = "green" if plan.is_complete else "yellow"
        progress = f"{plan.progress_percent:.0f}%"
        updated = plan.updated_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(
            plan.goal_hash[:8],
            plan.goal[:40] + ("..." if len(plan.goal) > 40 else ""),
            f"[{status_style}]{plan.status.value}[/{status_style}]",
            progress,
            updated,
        )

    console.print(table)


@agent.command(name="benchmark")
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
def agent_benchmark(tasks_dir: str, dry_run: bool, output: str | None, verbose: bool) -> None:
    """Run agent mode benchmarks (RFC-032).

    Tests planning quality, task decomposition, and execution accuracy.

    Examples:

    \b
        sunwell agent benchmark
        sunwell agent benchmark --dry-run
        sunwell agent benchmark -o benchmark/results/agent/
    """
    asyncio.run(_benchmark_async(tasks_dir, dry_run, output, verbose))


async def _benchmark_async(
    tasks_dir: str,
    dry_run: bool,
    output: str | None,
    verbose: bool,
) -> None:
    """Async implementation of benchmark command."""

    tasks_path = Path(tasks_dir)
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
            output_path = Path(output)
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
