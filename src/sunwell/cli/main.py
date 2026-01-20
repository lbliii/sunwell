"""Main CLI entry point - Goal-first interface (RFC-037).

The primary interface is now simply:
    sunwell "Build a REST API with auth"

All other commands are progressive disclosure for power users.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

from sunwell.cli.helpers import check_free_threading, load_dotenv

console = Console()


# RFC-037: Custom group that supports goal-first interface
class GoalFirstGroup(click.Group):
    """Custom group that allows 'sunwell "goal"' syntax while preserving subcommands."""

    def parse_args(self, ctx, args):
        """Override to handle goal-first pattern."""
        # If no args, proceed normally
        if not args:
            return super().parse_args(ctx, args)

        # Get list of known command names
        command_names = set(self.list_commands(ctx))

        # If first arg is NOT a command and NOT an option, treat it as a goal
        first_arg = args[0]
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

    # Get goal from custom parsing (if any)
    ctx.ensure_object(dict)
    goal = ctx.obj.get("_goal")

    # If a goal was provided and no subcommand invoked, run agent
    if goal and ctx.invoked_subcommand is None:
        ctx.invoke(
            _run_goal,
            goal=goal,
            dry_run=plan,
            model=model,
            verbose=verbose,
            time=time,
            trust=trust or "workspace",
            workspace=workspace,
        )


@main.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
@click.option("--workspace", "-w", default=None)
def _run_goal(
    goal: str,
    dry_run: bool,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str,
    workspace: str | None,
) -> None:
    """Internal command for goal execution."""
    workspace_path = Path(workspace) if workspace else None
    asyncio.run(_run_agent(goal, time, trust, dry_run, verbose, model, workspace_path))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    model_override: str | None,
    workspace_path: Path | None = None,
) -> None:
    """Execute goal with Adaptive Agent (RFC-042).

    This is the unified entry point. The Adaptive Agent automatically:
    - Extracts signals to select techniques
    - Uses Harmonic planning for complex goals
    - Validates at gates with fail-fast
    - Auto-fixes errors with Compound Eye
    - Persists learnings via Simulacrum
    """
    from sunwell.adaptive import AdaptiveAgent, AdaptiveBudget, EventType, create_renderer
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
        if verbose:
            console.print(f"[dim]Using model: {model_name}[/dim]")

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

    # Dry run: just plan
    if dry_run:
        console.print("[yellow]Planning only (--plan)[/yellow]\n")
        async for event in agent.plan(goal):
            if verbose or event.type in (EventType.PLAN_COMPLETE, EventType.ERROR):
                _print_event(event, verbose)
        return

    # Create renderer based on verbosity
    from sunwell.adaptive import RendererConfig
    renderer_config = RendererConfig(
        mode="interactive",
        show_signals=verbose,
        show_gates=verbose,
        show_learning=verbose,
    )
    renderer = create_renderer(renderer_config)

    # Full execution
    try:
        async for event in agent.run(goal, context={"cwd": str(Path.cwd())}):
            await renderer.render(event)

            # Show key milestones even in non-verbose mode
            if not verbose and event.type == EventType.COMPLETE:
                data = event.data or {}
                tasks = data.get("tasks_completed", 0)
                gates = data.get("gates_passed", 0)
                duration = data.get("duration_s", 0)
                console.print(
                    f"\n[green]✓ Complete[/green]: {tasks} tasks, "
                    f"{gates} gates passed ({duration:.1f}s)"
                )

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

    if event.type == EventType.PLAN_COMPLETE:
        data = event.data or {}
        console.print(f"\n[bold]Plan:[/bold] {data.get('task_count', 0)} tasks")
        for task in data.get("tasks", [])[:10]:
            console.print(f"  • {task.get('description', task.get('id', '?'))}")
    elif event.type == EventType.ERROR:
        console.print(f"[red]Error: {event.data}[/red]")
    elif verbose:
        console.print(f"[dim]{event.type.value}: {event.data}[/dim]")


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
from sunwell.cli import agent_cmd

main.add_command(agent_cmd.agent)

# Keep 'naaru' as hidden alias for backward compatibility
# We create a copy of the agent group with hidden=True
naaru_alias = click.Group(
    name="naaru",
    commands=agent_cmd.agent.commands,
    help=agent_cmd.agent.help,
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
main.add_command(skill.exec)
main.add_command(skill.validate)
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
