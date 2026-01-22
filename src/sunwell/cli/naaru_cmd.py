"""CLI commands for Naaru Unified Orchestration (RFC-032, RFC-083).

RFC-083 Unified Commands:
- sunwell naaru process "content": THE unified entry point
- sunwell naaru convergence: Read Convergence state

Legacy Commands (still supported):
- sunwell naaru run "goal": Execute arbitrary tasks (maps to process --mode agent)
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
    """Naaru unified orchestration commands (RFC-019, RFC-032, RFC-083)."""
    pass


# =============================================================================
# RFC-083: UNIFIED PROCESS COMMAND
# =============================================================================


@naaru.command("process")
@click.argument("content")
@click.option(
    "--mode", "-m",
    type=click.Choice(["auto", "chat", "agent", "interface"]),
    default="auto",
    help="Processing mode (default: auto - Naaru decides)",
)
@click.option(
    "--json", "json_output",
    is_flag=True,
    help="Output JSON (for programmatic use)",
)
@click.option(
    "--stream",
    is_flag=True,
    default=True,
    help="Stream events as they happen (default: True)",
)
@click.option(
    "--timeout", "-t",
    default=300.0,
    help="Max execution time in seconds (default: 300)",
)
@click.option(
    "--page-type",
    type=click.Choice(["home", "project", "research", "planning", "conversation"]),
    default="home",
    help="Current UI page context",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def process_cmd(
    content: str,
    mode: str,
    json_output: bool,
    stream: bool,
    timeout: float,
    page_type: str,
    verbose: bool,
):
    """Process any input through unified Naaru (RFC-083).

    THE single entry point for all Naaru interaction.

    Examples:

        sunwell naaru process "Hello, how are you?"

        sunwell naaru process "Build a REST API" --mode agent

        sunwell naaru process "plan my week" --mode chat

        sunwell naaru process "what files are in src/" --mode interface --json
    """
    asyncio.run(_process_unified(content, mode, json_output, stream, timeout, page_type, verbose))


async def _process_unified(
    content: str,
    mode: str,
    json_output: bool,
    stream: bool,
    timeout: float,
    page_type: str,
    verbose: bool,
):
    """Execute unified process."""
    import json as json_module

    from sunwell.config import get_config
    from sunwell.naaru import Naaru, NaaruEventType, ProcessInput, ProcessMode
    from sunwell.types.config import NaaruConfig

    config = get_config()

    # Create model
    synthesis_model = None
    try:
        from sunwell.models.ollama import OllamaModel

        model_name = None
        if config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "voice", "gemma3:1b")
        if not model_name:
            model_name = "gemma3:1b"

        synthesis_model = OllamaModel(model=model_name)
        if verbose and not json_output:
            console.print(f"[dim]Using model: {model_name}[/dim]")
    except Exception as e:
        if not json_output:
            console.print(f"[yellow]Warning: Could not load model: {e}[/yellow]")

    # Create Naaru
    naaru_config = NaaruConfig()
    if config and hasattr(config, "naaru"):
        naaru_config = config.naaru

    naaru_instance = Naaru(
        workspace=Path.cwd(),
        synthesis_model=synthesis_model,
        config=naaru_config,
    )

    # Create input
    process_input = ProcessInput(
        content=content,
        mode=ProcessMode(mode),
        page_type=page_type,
        workspace=Path.cwd(),
        stream=stream,
        timeout=timeout,
    )

    if json_output:
        # Collect all events and output as JSON
        events = []
        response = ""

        async for event in naaru_instance.process(process_input):
            event_dict = event.to_dict()
            events.append(event_dict)

            if stream:
                # Stream each event as JSON line
                print(json_module.dumps(event_dict))

            if event.type == NaaruEventType.MODEL_TOKENS:
                response += event.data.get("content", "")

        if not stream:
            # Output final summary
            print(json_module.dumps({
                "response": response,
                "events": events,
            }))
    else:
        # Human-readable output
        response = ""
        route_type = "unknown"

        async for event in naaru_instance.process(process_input):
            if event.type == NaaruEventType.PROCESS_START:
                if verbose:
                    console.print(f"[dim]Processing: {content[:50]}...[/dim]")

            elif event.type == NaaruEventType.ROUTE_DECISION:
                route_type = event.data.get("interaction_type", "unknown")
                confidence = event.data.get("confidence", 0)
                if verbose:
                    console.print(f"[dim]Route: {route_type} (confidence: {confidence:.0%})[/dim]")

            elif event.type == NaaruEventType.COMPOSITION_READY:
                if verbose:
                    panels = event.data.get("panels", [])
                    if panels:
                        panel_types = ", ".join(p.get("panel_type", "?") for p in panels)
                        console.print(f"[dim]Panels: {panel_types}[/dim]")

            elif event.type == NaaruEventType.MODEL_TOKENS:
                token_content = event.data.get("content", "")
                response += token_content
                if stream:
                    console.print(token_content, end="")

            elif event.type == NaaruEventType.TASK_COMPLETE:
                task_desc = event.data.get("description", "")[:50]
                console.print(f"  [green]✓[/green] {task_desc}")

            elif event.type == NaaruEventType.PROCESS_ERROR:
                error_msg = event.data.get("error", "Unknown error")
                console.print(f"[red]Error: {error_msg}[/red]")

            elif event.type == NaaruEventType.PROCESS_COMPLETE:
                duration = event.data.get("duration_s", 0)
                if verbose:
                    console.print(f"\n[dim]Completed in {duration:.1f}s[/dim]")

        if not stream and response:
            console.print(response)


@naaru.command("convergence")
@click.option(
    "--slot", "-s",
    help="Specific slot to read (e.g., 'routing:current')",
)
@click.option(
    "--json", "json_output",
    is_flag=True,
    help="Output as JSON",
)
def convergence_cmd(slot: str | None, json_output: bool):
    """Read Convergence state (RFC-083).

    Convergence is the shared working memory with 7±2 slots.

    Examples:

        sunwell naaru convergence

        sunwell naaru convergence --slot composition:current --json

        sunwell naaru convergence --slot routing:current
    """
    asyncio.run(_convergence(slot, json_output))


async def _convergence(slot: str | None, json_output: bool):
    """Read convergence state."""
    import json as json_module

    from sunwell.naaru import CONVERGENCE_SLOTS

    # For now, show slot definitions (actual convergence would need session)
    if json_output:
        if slot:
            desc = CONVERGENCE_SLOTS.get(slot, "Unknown slot")
            print(json_module.dumps({"slot": slot, "description": desc, "value": None}))
        else:
            print(json_module.dumps({"slots": CONVERGENCE_SLOTS}))
    else:
        if slot:
            desc = CONVERGENCE_SLOTS.get(slot, "Unknown slot")
            console.print(f"[bold]{slot}[/bold]: {desc}")
            console.print("[dim]Note: Actual value requires active session[/dim]")
        else:
            console.print("[bold]Standard Convergence Slots (RFC-083)[/bold]\n")
            for slot_id, desc in CONVERGENCE_SLOTS.items():
                console.print(f"  [cyan]{slot_id}[/cyan]: {desc}")


# =============================================================================
# LEGACY COMMANDS (still supported, map to unified process)
# =============================================================================


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
        workspace=Path.cwd(),
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
        workspace=Path(cp.working_directory),
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
        workspace=Path.cwd(),
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
