
import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.config import get_config

console = Console()


@click.command()
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
# RFC-064: Lens Management options
@click.option(
    "--lens", "-l",
    default=None,
    help="Lens to apply (name or path, e.g. 'coder' or './custom.lens')",
)
@click.option(
    "--auto-lens/--no-auto-lens",
    default=True,
    help="Auto-select lens based on goal (default: enabled)",
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
    "--provider", "-p",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default=None,
    help="Model provider (default: from config)",
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
# RFC-116: Harmonic Scoring v2
@click.option(
    "--scoring",
    type=click.Choice(["v1", "v2", "auto"]),
    default="v2",
    help="Harmonic scoring version: v1=original, v2=domain-aware (default), auto=adaptive",
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
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output NDJSON events for programmatic consumption (RFC-043)",
)
# RFC-117: Project workspace isolation
@click.option(
    "--project", "-P",
    "project_id",
    default=None,
    help="Project ID from registry (RFC-117)",
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Explicit project root path (RFC-117)",
)
# RFC-119: Server bridge for unified visibility
@click.option(
    "--no-server",
    is_flag=True,
    help="Force direct execution, skip server routing (RFC-119)",
)
def run(
    goal: str,
    time: int,
    trust: str,
    strategy: str,
    lens: str | None,
    auto_lens: bool,
    dry_run: bool,
    verbose: bool,
    provider: str | None,
    model: str | None,
    show_graph: bool,
    harmonic: bool,
    candidates: int,
    refine: int,
    scoring: str,
    incremental: bool,
    force: bool,
    show_plan: bool,
    diff_plan: bool,
    plan_id: str | None,
    json_output: bool,
    project_id: str | None,
    project_root: str | None,
    no_server: bool,
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
        goal, time, trust, strategy, lens, auto_lens, dry_run, verbose, provider, model,
        show_graph, candidates, refine, scoring, incremental, force, show_plan, diff_plan,
        plan_id, json_output, project_id, project_root, no_server,
    ))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    strategy: str,
    lens_name: str | None,
    auto_lens: bool,
    dry_run: bool,
    verbose: bool,
    provider_override: str | None,
    model_override: str | None,
    show_graph: bool,
    candidates: int = 5,
    refine: int = 1,
    scoring: str = "v2",
    incremental: bool = False,
    force: bool = False,
    show_plan: bool = False,
    diff_plan: bool = False,
    plan_id: str | None = None,
    json_output: bool = False,
    project_id: str | None = None,
    project_root: str | None = None,
    no_server: bool = False,
) -> None:
    """Execute agent mode."""
    # RFC-119: Route through server for unified visibility (if available)
    if not no_server and not dry_run:
        from sunwell.cli.server_bridge import detect_server, run_via_server

        server_url = await detect_server()
        if server_url:
            if not json_output:
                console.print(f"[dim]Routing through server at {server_url} (RFC-119)[/dim]")

            # Event callback for terminal output
            def print_event(event: dict) -> None:
                if json_output:
                    import json
                    import sys
                    print(json.dumps(event), file=sys.stdout, flush=True)
                else:
                    event_type = event.get("type", "")
                    data = event.get("data", {})
                    if event_type == "task_start":
                        console.print(f"[cyan]▶[/cyan] {data.get('description', '')}")
                    elif event_type == "task_complete":
                        console.print(f"[green]✓[/green] {data.get('task_id', '')}")
                    elif event_type == "error":
                        console.print(f"[red]✗[/red] {data.get('message', '')}")
                    elif event_type == "complete":
                        console.print("[green]✓ Goal completed successfully[/green]")

            result = await run_via_server(
                server_url,
                goal,
                workspace=project_root or str(Path.cwd()),
                project_id=project_id,
                lens=lens_name,
                provider=provider_override,
                model=model_override,
                trust=trust,
                timeout=time,
                event_callback=print_event,
            )

            if result.get("status") == "error":
                console.print(f"[red]Error: {result.get('error', 'Unknown')}[/red]")
            return

    from sunwell.cli.helpers import resolve_model
    from sunwell.naaru import Naaru
    from sunwell.naaru.planners import (
        AgentPlanner,
        ArtifactPlanner,
        HarmonicPlanner,
        PlanningStrategy,
        ScoringVersion,
        VarianceStrategy,
    )
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust
    from sunwell.types.config import NaaruConfig

    # Load config
    config = get_config()

    # Create model using resolve_model() helper
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
        # RFC-053: Suppress console output in JSON mode to keep NDJSON clean
        if not json_output:
            provider = provider_override or (config.model.default_provider if config else "ollama")
            model_name = model_override or (config.model.default_model if config else "gemma3:4b")
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")
    except Exception as e:
        if not json_output:
            console.print(f"[yellow]Warning: Could not load model: {e}[/yellow]")

    if not synthesis_model:
        if not json_output:
            console.print("[red]No model available for planning[/red]")
        else:
            # RFC-053: Emit error event in JSON mode
            import json
            import sys

            from sunwell.agent.events import AgentEvent, EventType

            msg = "No model available for planning"
            error_event = AgentEvent(EventType.ERROR, {"message": msg})
            print(json.dumps(error_event.to_dict()), file=sys.stdout, flush=True)
        return

    # RFC-117: Resolve project context
    from sunwell.project import (
        ProjectResolutionError,
        ProjectValidationError,
        resolve_project,
    )

    try:
        project = resolve_project(
            project_root=project_root,
            project_id=project_id,
            cwd=Path.cwd(),
        )
        if verbose and not json_output:
            console.print(f"[dim]Project: {project.id} ({project.root})[/dim]")
    except (ProjectResolutionError, ProjectValidationError) as e:
        if json_output:
            import json
            import sys

            from sunwell.agent.events import AgentEvent, EventType

            error_event = AgentEvent(EventType.ERROR, {"message": str(e)})
            print(json.dumps(error_event.to_dict()), file=sys.stdout, flush=True)
        else:
            console.print(f"[red]Error:[/red] {e}")
        return

    # Setup tool executor with project context
    trust_level = ToolTrust.from_string(trust)
    tool_executor = ToolExecutor(
        project=project,
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

    # RFC-064: Lens resolution
    resolved_lens = None
    lens_context = ""
    if lens_name or auto_lens:
        from sunwell.agent.lens_resolver import resolve_lens_for_goal

        lens_resolution = await resolve_lens_for_goal(
            goal=goal,
            explicit_lens=lens_name,
            project_path=project.root,
            auto_select=auto_lens,
        )
        if lens_resolution.lens:
            resolved_lens = lens_resolution.lens
            lens_context = resolved_lens.to_context()
            if not json_output:
                console.print(f"[dim]Lens: {resolved_lens.metadata.name} ({lens_resolution.source})[/dim]")
            elif json_output:
                import json
                import sys

                from sunwell.agent.events import AgentEvent, EventType

                lens_event = AgentEvent(
                    EventType.LENS_SELECTED,
                    {
                        "name": resolved_lens.metadata.name,
                        "source": lens_resolution.source,
                        "confidence": lens_resolution.confidence,
                        "reason": lens_resolution.reason,
                    },
                )
                print(json.dumps(lens_event.to_dict()), file=sys.stdout, flush=True)
        elif verbose:
            console.print(f"[dim]Lens: none ({lens_resolution.reason})[/dim]")

    # Create planner based on strategy
    planning_strategy = PlanningStrategy(strategy)

    if planning_strategy == PlanningStrategy.HARMONIC:
        # RFC-038: Harmonic planning (multi-candidate optimization)
        # RFC-058: Setup event callback early for planning visibility
        # RFC-116: Scoring version selection
        scoring_version = ScoringVersion(scoring)
        planner = HarmonicPlanner(
            model=synthesis_model,
            candidates=candidates,
            refinement_rounds=refine,
            variance=VarianceStrategy.PROMPTING,
            event_callback=None,  # Will be set up later for all planners
            scoring_version=scoring_version,
        )

        if verbose:
            console.print(
                f"[dim]Harmonic: {candidates} candidates, {refine} refinement rounds, "
                f"scoring={scoring}[/dim]"
            )

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

    # RFC-040: Incremental execution is now automatic for artifact-first planning
    # The --incremental flag is kept for backward compatibility but is no longer needed
    # when using artifact-first planning (it's automatic)
    if incremental and planning_strategy == PlanningStrategy.ARTIFACT_FIRST:
        # Use the dedicated incremental run for advanced features (backlog tracking, etc.)
        await _incremental_run(
            goal, planner, plan_id, force, verbose, time, tool_executor, json_output
        )
        return

    # Full execution (Naaru.run() now handles incremental automatically for artifact-first)
    naaru_config = NaaruConfig()
    if config and hasattr(config, "naaru"):
        naaru_config = config.naaru

    # RFC-053: JSON output mode with real-time event streaming for Sunwell Studio
    # Set up event callback BEFORE creating Naaru (more efficient, cleaner)
    if json_output:
        import json
        import sys

        from sunwell.agent.event_schema import ValidatedEventEmitter
        from sunwell.agent.events import AgentEvent

        def emit_json(event: AgentEvent) -> None:
            """Emit event as NDJSON to stdout for Studio consumption."""
            print(json.dumps(event.to_dict()), file=sys.stdout, flush=True)

        # Wrap with validation
        class CallbackEmitter:
            def __init__(self, callback):
                self.callback = callback

            def emit(self, event: AgentEvent) -> None:
                self.callback(event)

        validated_emitter = ValidatedEventEmitter(
            CallbackEmitter(emit_json),
            validate=True,
        )
        naaru_config.event_callback = validated_emitter.emit

        # Set event callback on planners that support it (RFC-058, RFC-059)
        if isinstance(planner, (HarmonicPlanner, ArtifactPlanner)):
            planner.event_callback = validated_emitter.emit

    # Create Naaru once with callback already configured
    naaru = Naaru(
        workspace=project.root,
        synthesis_model=synthesis_model,
        planner=planner,
        tool_executor=tool_executor,
        config=naaru_config,
    )

    # RFC-064: Build context with lens expertise
    run_context: dict = {"cwd": str(project.root)}
    if lens_context:
        run_context["lens_context"] = lens_context

    if json_output:
        # RFC-053: JSON output mode for Studio - events stream via callback
        try:
            await naaru.run(
                goal=goal,
                context=run_context,
                on_progress=lambda msg: None,  # Suppress console output
                max_time_seconds=time,
                force_rebuild=force,
            )
            # Note: complete event is emitted by Naaru.run() via callback
        except KeyboardInterrupt:
            from sunwell.agent.events import AgentEvent, EventType
            error_event = AgentEvent(EventType.ERROR, {"message": "Interrupted by user"})
            naaru_config.event_callback(error_event)
        except Exception as e:
            from sunwell.agent.events import AgentEvent, EventType
            error_event = AgentEvent(EventType.ERROR, {"message": str(e)})
            naaru_config.event_callback(error_event)
        return

    # Console output mode (non-JSON)
    try:
        result = await naaru.run(
            goal=goal,
            context=run_context,
            on_progress=console.print,
            max_time_seconds=time,
            force_rebuild=force,
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
        tasks = await planner.plan([goal], {"cwd": str(project.root)})
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
        graph = await planner.discover_graph(goal, {"cwd": str(project.root)})
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
    """Show plan preview with cost estimates (RFC-074)."""
    from sunwell.incremental import ExecutionCache, IncrementalExecutor
    from sunwell.naaru.artifacts import select_model_tier

    # Cost estimates per model tier (rough approximations)
    cost_per_artifact = {
        "small": {"tokens": 1000, "cost_usd": 0.001, "duration_s": 3},
        "medium": {"tokens": 2500, "cost_usd": 0.003, "duration_s": 8},
        "large": {"tokens": 5000, "cost_usd": 0.008, "duration_s": 15},
    }

    console.print("[yellow]Plan preview - RFC-074[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(project.root)})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

    # Get execution waves
    waves = graph.execution_waves()

    # Compute model distribution
    model_distribution: dict[str, int] = {"small": 0, "medium": 0, "large": 0}
    for artifact_id in graph:
        artifact = graph[artifact_id]
        tier = select_model_tier(artifact, graph)
        model_distribution[tier] += 1

    # Compute estimates
    estimated_tokens = sum(
        cost_per_artifact[tier]["tokens"] * count
        for tier, count in model_distribution.items()
    )
    estimated_cost_usd = sum(
        cost_per_artifact[tier]["cost_usd"] * count
        for tier, count in model_distribution.items()
    )

    # Duration estimate (parallel execution - max per wave)
    estimated_duration_seconds = 0.0
    for wave in waves:
        wave_durations = []
        for artifact_id in wave:
            artifact = graph[artifact_id]
            tier = select_model_tier(artifact, graph)
            wave_durations.append(cost_per_artifact[tier]["duration_s"])
        if wave_durations:
            estimated_duration_seconds += max(wave_durations)

    # Parallelization factor
    parallelization_factor = len(graph) / len(waves) if waves else 1.0

    console.print(f"[bold]📋 Execution Plan:[/bold] {goal}\n")

    # Show waves
    for i, wave in enumerate(waves, 1):
        parallel = "⚡" if len(wave) > 1 else "→"
        console.print(f"Wave {i} {parallel}")
        for artifact_id in wave:
            artifact = graph[artifact_id]
            tier = select_model_tier(artifact, graph)
            desc = artifact.description[:40] + "..." if len(artifact.description) > 40 else artifact.description
            console.print(f"  [{tier}] {artifact_id}: {desc}")
        console.print()

    # Show estimates
    console.print("[bold]📊 Estimates[/bold]")
    console.print(f"  Artifacts: {len(graph)}")
    console.print(f"  Waves: {len(waves)}")
    console.print(f"  Parallelization: {parallelization_factor:.1f}x")
    console.print(f"  Model mix: {model_distribution}")
    console.print(f"  Est. tokens: ~{estimated_tokens:,}")
    console.print(f"  Est. cost: ~${estimated_cost_usd:.3f}")
    console.print(f"  Est. time: ~{estimated_duration_seconds:.0f}s")

    # Show changes vs previous (if requested)
    if diff_plan:
        cache_path = project.root / ".sunwell" / "cache" / "execution.db"
        cache = ExecutionCache(cache_path)
        executor = IncrementalExecutor(graph=graph, cache=cache)
        plan = executor.plan_execution()

        if plan.to_skip:
            console.print("\n[bold]🔄 Changes vs Previous[/bold]")
            console.print(f"  [green]To rebuild: {len(plan.to_execute)}[/green]")
            console.print(f"  [dim]Unchanged: {len(plan.to_skip)}[/dim]")
            savings_percent = plan.skip_percentage
            console.print(f"  [bold]Savings: {savings_percent:.0f}%[/bold]")

            if verbose and plan.to_execute:
                console.print("\n  Artifacts to rebuild:")
                for aid in plan.to_execute[:10]:
                    decision = plan.decisions.get(aid)
                    reason = decision.reason.value if decision else "unknown"
                    console.print(f"    - {aid} ({reason})")
                if len(plan.to_execute) > 10:
                    console.print(f"    ... and {len(plan.to_execute) - 10} more")
        else:
            console.print("\n[dim]No previous execution found[/dim]")

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
    json_output: bool = False,
) -> None:
    """Run with incremental rebuild support via ExecutionManager (RFC-094).

    All execution logic is now centralized in ExecutionManager for:
    - Consistent backlog lifecycle (claim/complete/fail)
    - IncrementalExecutor with hash-based caching
    - Event-driven UI updates
    - Learnings extraction
    """
    from sunwell.execution import ExecutionManager, StdoutEmitter

    if not json_output:
        console.print("[bold]🔄 Incremental execution (RFC-094)[/bold]\n")

    # Create emitter and manager
    emitter = StdoutEmitter(json_output=json_output)
    manager = ExecutionManager(
        root=project.root,
        emitter=emitter,
    )

    try:
        result = await manager.run_goal(
            goal=goal,
            planner=planner,
            executor=tool_executor,
            goal_id=plan_id,
            force=force,
            verbose=verbose,
        )

        # Console summary (JSON events already emitted by manager)
        if not json_output:
            console.print("\n[bold]═══ Summary ═══[/bold]")
            console.print(f"  Completed: {len(result.artifacts_created)}")
            console.print(f"  Skipped (cached): {len(result.artifacts_skipped)}")
            console.print(f"  Failed: {len(result.artifacts_failed)}")

            if result.artifacts_failed:
                console.print("\n[red]Failed artifacts:[/red]")
                for aid in result.artifacts_failed[:10]:
                    console.print(f"  ✗ {aid}")

            if result.success:
                console.print("\n[green]✓ Incremental build complete[/green]")
            else:
                console.print("\n[yellow]⚠ Build completed with errors[/yellow]")

    except KeyboardInterrupt:
        if not json_output:
            console.print("\n[yellow]Interrupted - progress saved[/yellow]")
    except Exception as e:
        if not json_output:
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
        graph, metrics = await planner.plan_with_metrics(goal, {"cwd": str(project.root)})
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


