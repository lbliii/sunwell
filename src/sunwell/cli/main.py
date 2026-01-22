"""Main CLI entry point - Goal-first interface (RFC-037).

The primary interface is now simply:
    sunwell "Build a REST API with auth"

All other commands are progressive disclosure for power users.
"""


import asyncio
from pathlib import Path

import click
from rich.console import Console

from sunwell.cli.helpers import check_free_threading, load_dotenv

console = Console()


# RFC-037: Custom group that supports goal-first interface
class GoalFirstGroup(click.Group):
    """Custom group that allows 'sunwell "goal"' syntax while preserving subcommands.

    Also supports RFC-086: `sunwell .` and `sunwell ~/path` patterns for project opening.
    """

    def parse_args(self, ctx, args):
        """Override to handle goal-first pattern and path shortcuts."""
        # If no args, proceed normally
        if not args:
            return super().parse_args(ctx, args)

        # Get list of known command names
        command_names = set(self.list_commands(ctx))

        first_arg = args[0]

        # RFC-086: Check if it's a path pattern (starts with . or / or ~)
        # These should be treated as 'open' commands
        if first_arg in (".", "..") or first_arg.startswith(("/", "~", "./")):
            ctx.ensure_object(dict)
            ctx.obj["_open_path"] = first_arg
            args = args[1:]  # Remove path from args
            return super().parse_args(ctx, args)

        # If first arg is NOT a command and NOT an option, treat it as a goal
        if (
            first_arg not in command_names
            and not first_arg.startswith("-")
            and not first_arg.startswith("--")
        ):
            # Store the goal in context for later retrieval
            ctx.ensure_object(dict)
            ctx.obj["_goal"] = first_arg
            args = args[1:]  # Remove goal from args

        return super().parse_args(ctx, args)


@click.group(cls=GoalFirstGroup, invoke_without_command=True)
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--open", "open_studio", is_flag=True, help="Open plan in Studio (with --plan)")
@click.option("--json", "json_output", is_flag=True, help="Output plan as JSON (with --plan)")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider (default: from config)")
@click.option("--model", "-m", help="Override model selection")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--time", "-t", default=300, help="Max execution time (seconds)")
@click.option("--trust", type=click.Choice(["read_only", "workspace", "shell"]),
              default=None, help="Override tool trust level")
@click.option("--workspace", "-w", type=click.Path(exists=False),
              help="Project directory (default: auto-detect or ~/Sunwell/projects/)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress warnings")
@click.version_option(version="0.1.0")
@click.pass_context
def main(
    ctx,
    plan: bool,
    open_studio: bool,
    json_output: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str | None,
    workspace: str | None,
    quiet: bool,
) -> None:
    """Sunwell — AI agent for software tasks.

    \b
    Just tell it what you want:

        sunwell "Build a REST API with auth"
        sunwell "Write docs for the CLI module"
        sunwell "Refactor auth.py to use async"

    \b
    For planning without execution:

        sunwell "Build an app" --plan

    \b
    For a specific project directory:

        sunwell "Add tests" --workspace ~/projects/myapp

    \b
    For interactive mode:

        sunwell chat

    \b
    For power users - see all commands:

        sunwell --help
    """
    load_dotenv()
    check_free_threading(quiet=quiet)

    # Get goal or path from custom parsing
    ctx.ensure_object(dict)
    goal = ctx.obj.get("_goal")
    open_path = ctx.obj.get("_open_path")

    # RFC-086: If a path was provided (sunwell . or sunwell ~/path), open project
    if open_path and ctx.invoked_subcommand is None:
        from sunwell.cli import open_cmd

        ctx.invoke(
            open_cmd.open_project,
            path=open_path,
            lens=None,
            mode="auto",
            dry_run=False,
        )
        return

    # If a goal was provided and no subcommand invoked, run agent
    if goal and ctx.invoked_subcommand is None:
        ctx.invoke(
            _run_goal,
            goal=goal,
            dry_run=plan,
            open_studio=open_studio,
            json_output=json_output,
            provider=provider,
            model=model,
            verbose=verbose,
            time=time,
            trust=trust or "workspace",
            workspace=workspace,
        )


@main.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--open-studio", is_flag=True)
@click.option("--json-output", is_flag=True)
@click.option("--provider", "-p", default=None)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
@click.option("--workspace", "-w", default=None)
def _run_goal(
    goal: str,
    dry_run: bool,
    open_studio: bool,
    json_output: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str,
    workspace: str | None,
) -> None:
    """Internal command for goal execution."""
    workspace_path = Path(workspace) if workspace else None
    asyncio.run(_run_agent(
        goal, time, trust, dry_run, verbose, provider, model, workspace_path,
        open_studio=open_studio, json_output=json_output,
    ))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    provider_override: str | None,
    model_override: str | None,
    workspace_path: Path | None = None,
    *,
    open_studio: bool = False,
    json_output: bool = False,
) -> None:
    """Execute goal with Adaptive Agent (RFC-042, RFC-090).

    This is the unified entry point. The Adaptive Agent automatically:
    - Extracts signals to select techniques
    - Uses Harmonic planning for complex goals
    - Validates at gates with fail-fast
    - Auto-fixes errors with Compound Eye
    - Persists learnings via Simulacrum

    RFC-090 additions:
    - open_studio: Launch Studio with plan after --plan
    - json_output: Output plan as JSON for scripting
    """
    from sunwell.adaptive import AdaptiveAgent, AdaptiveBudget, EventType, create_renderer
    from sunwell.cli.helpers import resolve_model
    from sunwell.cli.workspace_prompt import resolve_workspace_interactive
    from sunwell.config import get_config
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # Load config
    config = get_config()

    # Resolve workspace (RFC-043 addendum)
    # Extract project name hint from goal for new projects
    project_name = _extract_project_name(goal)
    workspace = resolve_workspace_interactive(
        explicit=workspace_path,
        project_name=project_name,
        quiet=not verbose,
    )

    # Create model using resolve_model() helper
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
        if verbose:
            provider = provider_override or config.model.default_provider if config else "ollama"
            model_name = model_override or config.model.default_model if config else "gemma3:4b"
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not load model: {e}[/yellow]")

    if not synthesis_model:
        console.print("[red]No model available[/red]")
        return

    # Setup tool executor with resolved workspace
    trust_level = ToolTrust.from_string(trust)
    tool_executor = ToolExecutor(
        workspace=workspace,
        policy=ToolPolicy(trust_level=trust_level),
    )

    if verbose:
        console.print(f"[dim]Trust level: {trust}[/dim]")
        available_tools = frozenset(tool_executor.get_available_tools())
        console.print(f"[dim]Available tools: {', '.join(sorted(available_tools))}[/dim]")

    # Create Adaptive Agent with resolved workspace
    agent = AdaptiveAgent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=workspace,
        budget=AdaptiveBudget(total_budget=50_000),
    )

    # Dry run: just plan (RFC-090 enhanced)
    if dry_run:
        plan_data = None
        async for event in agent.plan(goal):
            if event.type == EventType.PLAN_WINNER:
                plan_data = event.data
            elif event.type == EventType.ERROR:
                if not json_output:
                    _print_event(event, verbose)

        if plan_data:
            # RFC-090: JSON output for scripting
            if json_output:
                import json
                click.echo(json.dumps(plan_data, indent=2))
                return

            # Rich output
            console.print("[yellow]Planning only (--plan)[/yellow]\n")
            _print_plan_details(plan_data, verbose, goal)

            # Open in Studio if requested
            if open_studio:
                _open_plan_in_studio(plan_data, goal, workspace)

        return

    # Create renderer based on verbosity
    from sunwell.adaptive import RendererConfig
    renderer_config = RendererConfig(
        mode="interactive",
        show_learnings=verbose,
        verbose=verbose,
    )
    renderer = create_renderer(renderer_config)

    # Full execution
    try:
        # renderer.render() expects the full event stream, not individual events
        await renderer.render(agent.run(goal, context={"cwd": str(Path.cwd())}))

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


def _print_event(event, verbose: bool) -> None:
    """Print an agent event to console."""
    from sunwell.adaptive import EventType

    if event.type == EventType.PLAN_WINNER:
        data = event.data or {}
        tasks = data.get("tasks", 0)
        gates = data.get("gates", 0)
        technique = data.get("technique", "unknown")
        console.print(f"\n[bold]Plan ready[/bold] ({technique})")
        console.print(f"  • {tasks} tasks, {gates} validation gates")
    elif event.type == EventType.ERROR:
        console.print(f"[red]Error: {event.data}[/red]")
    elif verbose:
        console.print(f"[dim]{event.type.value}: {event.data}[/dim]")


def _print_plan_details(data: dict, verbose: bool, goal: str) -> None:
    """Print rich plan details with truncation (RFC-090)."""
    technique = data.get("technique", "unknown")
    tasks = data.get("tasks", 0)
    gates = data.get("gates", 0)
    task_list = data.get("task_list", [])
    gate_list = data.get("gate_list", [])

    # Header
    console.print(f"[bold]Plan ready[/bold] ({technique})")
    console.print(f"  • {tasks} tasks, {gates} validation gates\n")

    # Task list with truncation
    if task_list:
        console.print("[bold]📋 Tasks[/bold]")
        display_limit = len(task_list) if verbose else 10
        for i, task in enumerate(task_list[:display_limit], 1):
            deps = ""
            if task.get("depends_on"):
                if verbose:
                    # Show IDs with --verbose
                    deps = f" (←{','.join(task['depends_on'][:3])})"
                else:
                    # Show numbers by default
                    dep_nums = [
                        str(j + 1) for j, t in enumerate(task_list)
                        if t["id"] in task["depends_on"]
                    ]
                    deps = f" (←{','.join(dep_nums)})" if dep_nums else ""

            produces = ""
            if task.get("produces"):
                produces = f" → {task['produces'][0]}"

            # Format: index. [id] description deps produces
            task_id = task["id"][:12].ljust(12)
            desc = task["description"][:35].ljust(35)
            console.print(f"  {i:2}. [{task_id}] {desc}{deps}{produces}")

        # Truncation notice
        if not verbose and len(task_list) > 10:
            remaining = len(task_list) - 10
            console.print(f"  [dim]... and {remaining} more tasks (use --verbose to see all)[/dim]")
        console.print()

    # Gate list
    if gate_list:
        console.print("[bold]🔒 Validation Gates[/bold]")
        for gate in gate_list:
            after = ", ".join(gate.get("after_tasks", [])[:3])
            gate_type = gate.get("type", "unknown").ljust(12)
            console.print(f"  • [{gate['id']}] {gate_type} after: {after}")
        console.print()

    # Next steps
    console.print("━" * 50)
    console.print("[bold]💡 Next steps:[/bold]")
    # Escape the goal for display (avoid rich markup issues)
    safe_goal = goal.replace("[", "\\[").replace("]", "\\]")
    console.print(f'  • sunwell "{safe_goal}" [dim]Run now[/dim]')
    console.print(f'  • sunwell "{safe_goal}" --plan --open [dim]Open in Studio[/dim]')
    console.print('  • sunwell plan "..." -o . [dim]Save plan[/dim]')


def _open_plan_in_studio(plan_data: dict, goal: str, workspace: Path) -> None:
    """Save plan and open in Studio (RFC-090)."""
    import json
    from datetime import datetime

    from sunwell.cli.open_cmd import launch_studio

    # Ensure .sunwell directory exists
    plan_dir = workspace / ".sunwell"
    plan_dir.mkdir(exist_ok=True)

    # Save plan with goal context
    plan_file = plan_dir / "current-plan.json"
    plan_data["goal"] = goal
    plan_data["created_at"] = datetime.now().isoformat()
    plan_file.write_text(json.dumps(plan_data, indent=2))

    console.print(f"\n[cyan]Opening plan in Studio...[/cyan]")

    # Launch Studio in planning mode with plan file
    launch_studio(
        project=str(workspace),
        lens="coder",
        mode="planning",
        plan_file=str(plan_file),
    )


def _extract_project_name(goal: str) -> str | None:
    """Extract a project name hint from a goal.

    Simple heuristic extraction - looks for common patterns like
    "build a X app" or "create X".

    Args:
        goal: Natural language goal

    Returns:
        Extracted project name or None if unclear
    """
    import re

    goal_lower = goal.lower()

    # Pattern: "build/create/make a X app/api/tool/site"
    patterns = [
        r"(?:build|create|make|write)\s+(?:a\s+)?(.+?)\s+(?:app|api|tool|site|website|service)",
        r"(?:build|create|make|write)\s+(?:a\s+)?(.+?)\s+(?:with|using)",
        r"(?:build|create|make)\s+(?:a\s+)?(.+?)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, goal_lower)
        if match:
            name = match.group(1).strip()
            # Filter out very short or generic results
            if len(name) > 2 and name not in ("a", "an", "the", "new", "simple"):
                return name

    return None


async def _artifact_dry_run(goal: str, planner, verbose: bool) -> None:
    """Dry run for artifact-first planning (RFC-036, RFC-039)."""
    from rich.table import Table

    from sunwell.naaru import get_model_distribution

    console.print("[yellow]Planning only (--plan)[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

    # RFC-039: Show expertise info if available
    if hasattr(planner, "get_expertise_summary"):
        summary = planner.get_expertise_summary()
        if summary.get("loaded"):
            console.print(f"[cyan]Expertise:[/cyan] {summary.get('domain', 'unknown')} domain")
            if verbose:
                console.print(f"[dim]  Heuristics: {', '.join(summary.get('heuristics', []))}[/dim]")
                console.print(f"[dim]  Sources: {', '.join(summary.get('source_lenses', []))}[/dim]")
            console.print()

    console.print(f"[bold]Plan for:[/bold] {goal}\n")

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

    # Show graph if verbose
    if verbose:
        console.print("\n[bold]Dependency Graph (Mermaid):[/bold]")
        console.print("```mermaid")
        console.print(graph.to_mermaid())
        console.print("```")


# =============================================================================
# TIER 1: The 90% Path (visible in --help)
# =============================================================================

# Import and register chat command (interactive mode)
from sunwell.cli import chat

main.add_command(chat.chat)

# Import and register setup command (first-time setup)
from sunwell.cli import setup

main.add_command(setup.setup)


# =============================================================================
# TIER 2: Power User (visible in --help, grouped)
# =============================================================================

# Manage saved configurations
from sunwell.cli import bind

main.add_command(bind.bind)

# Global settings
from sunwell.cli import config_cmd

main.add_command(config_cmd.config)


# =============================================================================
# TIER 3: Advanced (shown in --help, but organized as subgroups)
# =============================================================================

# Agent commands (renamed from 'naaru' for clarity - RFC-037)
from sunwell.cli.agent import agent

main.add_command(agent)

# Keep 'naaru' as hidden alias for backward compatibility
# We create a copy of the agent group with hidden=True
naaru_alias = click.Group(
    name="naaru",
    commands=agent.commands,
    help=agent.help,
    hidden=True,
)
main.add_command(naaru_alias)

# Legacy commands (with deprecation warnings)
from sunwell.cli import apply, ask

main.add_command(apply.apply)
main.add_command(ask.ask)

# Session management
from sunwell.cli import session

main.add_command(session.sessions)

# Benchmark suite
from sunwell.benchmark.cli import benchmark

main.add_command(benchmark)

# Development tools
from sunwell.cli import lens, runtime_cmd, skill

main.add_command(runtime_cmd.runtime)
main.add_command(skill.skill)  # RFC-087: Full skill command group
main.add_command(skill.exec_legacy, name="exec")  # Legacy backward compat
main.add_command(skill.validate_legacy, name="validate")  # Legacy backward compat
main.add_command(lens.lens)

# Plan command for DAG visualization (RFC-043 prep)

# Autonomous Backlog (RFC-046)
from sunwell.cli import backlog_cmd

main.add_command(backlog_cmd.backlog)

# Project Intelligence commands (RFC-045)
from sunwell.cli import intel_cmd

main.add_command(intel_cmd.intel)
from sunwell.cli import plan_cmd

main.add_command(plan_cmd.plan)

# Deep Verification (RFC-047)
from sunwell.cli import verify_cmd

main.add_command(verify_cmd.verify)

# Autonomy Guardrails (RFC-048)
from sunwell.cli import guardrails_cmd

main.add_command(guardrails_cmd.guardrails)

# External Integration (RFC-049)
from sunwell.cli import external_cmd

main.add_command(external_cmd.external)

# Fast Bootstrap (RFC-050)
from sunwell.cli import bootstrap_cmd

main.add_command(bootstrap_cmd.bootstrap)

# Multi-Instance Coordination (RFC-051)
from sunwell.cli import workers_cmd

main.add_command(workers_cmd.workers)

# Team Intelligence (RFC-052)
from sunwell.cli import team_cmd

main.add_command(team_cmd.team)

# Project Import (RFC-043 addendum)
from sunwell.cli import import_cmd

main.add_command(import_cmd.import_project, name="import")

# Weakness Cascade (RFC-063)
from sunwell.cli import weakness_cmd

main.add_command(weakness_cmd.weakness)

# Briefing System (RFC-071)
from sunwell.cli import briefing_cmd

main.add_command(briefing_cmd.briefing)

# DAG and Incremental Execution (RFC-074)
from sunwell.cli import dag_cmd

main.add_command(dag_cmd.dag)

# Surface Primitives & Layout (RFC-072)
from sunwell.cli import surface

main.add_command(surface.surface)

# Generative Interface (RFC-075)
from sunwell.cli import interface_cmd

main.add_command(interface_cmd.interface)

# Reasoned Decisions (RFC-073)
from sunwell.cli import reason

main.add_command(reason.reason)

# Project Analysis (RFC-079)
from sunwell.cli import project_cmd

main.add_command(project_cmd.project)

# Self-Knowledge (RFC-085)
from sunwell.cli import self_cmd

main.add_command(self_cmd.self_cmd, name="self")

# Universal Writing Environment (RFC-086)
from sunwell.cli import open_cmd

main.add_command(open_cmd.open_project, name="open")

# Autonomous Workflow Execution (RFC-086)
from sunwell.cli import workflow_cmd

main.add_command(workflow_cmd.workflow)

# Security-First Skill Execution (RFC-089)
from sunwell.cli import security_cmd

main.add_command(security_cmd.security)
