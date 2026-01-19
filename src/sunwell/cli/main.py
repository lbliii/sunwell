"""Main CLI entry point - Goal-first interface (RFC-037).

The primary interface is now simply:
    sunwell "Build a REST API with auth"
    
All other commands are progressive disclosure for power users.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

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
        )


@main.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
def _run_goal(
    goal: str,
    dry_run: bool,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str,
) -> None:
    """Internal command for goal execution."""
    asyncio.run(_run_agent(goal, time, trust, dry_run, verbose, model))


async def _run_agent(
    goal: str,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    model_override: str | None,
) -> None:
    """Execute agent mode (RFC-032, RFC-036, RFC-037).
    
    This is the unified entry point for goal execution.
    Strategy is always artifact_first (RFC-036) - no flag needed.
    """
    from sunwell.config import get_config
    from sunwell.naaru import Naaru
    from sunwell.naaru.planners import ArtifactPlanner
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
        if verbose:
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

    if verbose:
        console.print(f"[dim]Trust level: {trust}[/dim]")
        available_tools = frozenset(tool_executor.get_available_tools())
        console.print(f"[dim]Available tools: {', '.join(sorted(available_tools))}[/dim]")

    # RFC-036: Always use artifact-first planning
    planner = ArtifactPlanner(model=synthesis_model)

    if dry_run:
        await _artifact_dry_run(goal, planner, verbose)
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


async def _artifact_dry_run(goal: str, planner, verbose: bool) -> None:
    """Dry run for artifact-first planning (RFC-036)."""
    from rich.table import Table

    from sunwell.naaru import get_model_distribution

    console.print("[yellow]Planning only (--plan)[/yellow]\n")

    try:
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
    except Exception as e:
        console.print(f"[red]Discovery failed: {e}[/red]")
        return

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
from sunwell.cli import runtime_cmd, skill, lens
main.add_command(runtime_cmd.runtime)
main.add_command(skill.exec)
main.add_command(skill.validate)
main.add_command(lens.lens)
