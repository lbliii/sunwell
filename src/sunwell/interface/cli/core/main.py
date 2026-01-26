"""Main CLI entry point - Goal-first interface (RFC-037, RFC-109, RFC-131).

The primary interface is now simply:
    sunwell "Build a REST API with auth"
    sunwell -s a-2 docs/api.md

RFC-109: CLI simplified to 5 primary commands.
RFC-131: Holy Light CLI aesthetic with branded styling.
All other commands are progressive disclosure or hidden for Studio.
"""


import re
import sys
from pathlib import Path
import click

from sunwell.interface.cli.helpers import check_free_threading, load_dotenv
from sunwell.interface.cli.core.async_runner import async_command, run_async
from sunwell.interface.cli.core.shortcuts import complete_shortcut, complete_target
from sunwell.interface.cli.core.theme import create_sunwell_console


# RFC-131: Holy Light themed console
console = create_sunwell_console()


def cli_entrypoint() -> None:
    """Wrapped entrypoint with global error handling (RFC-131).

    This catches SunwellError and displays it nicely instead of ugly tracebacks.
    Called from pyproject.toml [project.scripts].
    """
    try:
        main(standalone_mode=False)
    except click.ClickException as e:
        # Let Click handle its own exceptions
        e.show()
        sys.exit(e.exit_code)
    except click.Abort:
        # RFC-131: Holy Light styled interrupt message
        console.print("\n  [neutral.dim]◈ Paused[/]")
        sys.exit(130)
    except Exception as e:
        # Handle SunwellError with nice formatting
        from sunwell.interface.cli.core.error_handler import handle_error
        from sunwell.foundation.errors import SunwellError

        if isinstance(e, SunwellError):
            handle_error(e, json_output=False)
        else:
            # Wrap unknown errors
            handle_error(e, json_output=False)


# RFC-037, RFC-109: Custom group that supports goal-first and shortcut interfaces
class GoalFirstGroup(click.Group):
    """Custom group that allows multiple entry patterns:

    - `sunwell "goal"` - Goal-first (RFC-037)
    - `sunwell -s a-2 file.md` - Shortcut execution (RFC-109)
    - `sunwell .` or `sunwell ~/path` - Project opening (RFC-086)
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Override to handle goal-first, shortcut, and path patterns."""
        # If no args, proceed normally
        if not args:
            return super().parse_args(ctx, args)

        # Get list of known command names
        command_names = set(self.list_commands(ctx))

        first_arg = args[0]

        # RFC-086: Check if it's a path pattern (starts with . or / or ~)
        if first_arg in (".", "..") or first_arg.startswith(("/", "~", "./")):
            ctx.ensure_object(dict)
            ctx.obj["_open_path"] = first_arg
            args = args[1:]
            return super().parse_args(ctx, args)

        # RFC-109: Check for shortcut pattern with positional target
        # sunwell -s a-2 file.md "context string"
        # We need to capture positional args after the options are parsed
        ctx.ensure_object(dict)

        # Find -s/--skill in args and capture what comes after
        skill_idx = None
        for i, arg in enumerate(args):
            if arg in ("-s", "--skill"):
                skill_idx = i
                break

        if skill_idx is not None and len(args) > skill_idx + 2:
            # There's something after "-s shortcut"
            # Check if there are positional args (not options)
            remaining_args = args[skill_idx + 2:]
            positional_args = []
            for arg in remaining_args:
                if arg.startswith("-"):
                    break
                positional_args.append(arg)

            if positional_args:
                # First positional is target, rest is context
                ctx.obj["_positional_target"] = positional_args[0]
                if len(positional_args) > 1:
                    ctx.obj["_context_str"] = " ".join(positional_args[1:])
                # Remove positional args from args list (keep as list for Click parser)
                args = list(args)
                for pa in positional_args:
                    if pa in args:
                        args.remove(pa)

        # If first arg is NOT a command and NOT an option, treat it as a goal
        if (
            first_arg not in command_names
            and not first_arg.startswith("-")
            and not first_arg.startswith("--")
        ):
            ctx.obj["_goal"] = first_arg
            args = args[1:]

        return super().parse_args(ctx, args)


def _show_all_commands(ctx: click.Context) -> None:
    """Show all commands including hidden ones (RFC-109)."""
    from rich.table import Table

    table = Table(title="All Sunwell Commands", show_header=True)
    table.add_column("Command", style="cyan")
    table.add_column("Tier", style="magenta")
    table.add_column("Description")

    # Tier definitions
    tier_1_2 = {"config", "project", "session", "lens", "setup"}  # Visible in --help
    tier_3 = {"benchmark", "chat", "demo", "eval", "index", "runtime"}  # Hidden, developer
    tier_4 = {
        "backlog", "dag", "interface", "naaru", "scan", "security", "self",
        "skill", "surface", "weakness", "workers", "workflow", "workspace",
    }  # Internal, Studio only

    # Get all commands
    for name in sorted(main.list_commands(ctx)):
        cmd = main.get_command(ctx, name)
        if cmd is None:
            continue

        # Determine tier
        if name in tier_1_2:
            tier = "1-2 (Visible)"
        elif name in tier_3:
            tier = "3 (Hidden)"
        elif name in tier_4:
            tier = "4 (Internal)"
        else:
            tier = "?" if cmd.hidden else "1-2"

        # Get description
        desc = cmd.get_short_help_str(limit=50) if cmd.help else "-"

        table.add_row(name, tier, desc)

    console.print(table)
    console.print("\n[dim]Tier 1-2: Shown in --help (user-facing)[/dim]")
    console.print("[dim]Tier 3: Hidden but accessible (developer tools)[/dim]")
    console.print("[dim]Tier 4: Internal only (Studio integration)[/dim]")


@click.group(cls=GoalFirstGroup, invoke_without_command=True)
@click.option("-s", "--skill", "skill_shortcut", shell_complete=complete_shortcut,
              help="Run skill shortcut (a-2, p, health, etc.)")
@click.option("-t", "--target", "skill_target", shell_complete=complete_target,
              help="Target file/directory for skill")
@click.option("-l", "--lens", default="tech-writer", help="Lens to use")
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--open", "open_studio", is_flag=True, help="Open plan in Studio (with --plan)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider (default: from config)")
@click.option("--model", "-m", help="Override model selection")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--time", default=300, help="Max execution time (seconds)")
@click.option("--trust", type=click.Choice(["read_only", "workspace", "shell"]),
              default=None, help="Override tool trust level")
@click.option("--workspace", "-w", type=click.Path(exists=False),
              help="Project directory (default: auto-detect)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress warnings")
@click.option("--converge/--no-converge", default=False,
              help="Enable convergence loops (iterate until lint/types pass)")
@click.option("--converge-gates", default="lint,type",
              help="Gates for convergence (comma-separated: lint,type,test)")
@click.option("--converge-max", default=5, type=int,
              help="Maximum convergence iterations")
@click.option("--all-commands", is_flag=True, hidden=True,
              help="Show all commands including hidden")
@click.version_option(prog_name="sunwell")  # Dynamic version from pyproject.toml
@click.pass_context
def main(
    ctx,
    skill_shortcut: str | None,
    skill_target: str | None,
    lens: str,
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
    converge: bool,
    converge_gates: str,
    converge_max: int,
    all_commands: bool,
) -> None:
    """✦ Sunwell — AI agent for software tasks.

    \b
    USAGE:
        sunwell [GOAL]           Run a goal
        sunwell -s [SHORTCUT]    Quick skills
        sunwell [COMMAND]        Subcommands

    \b
    EXAMPLES:
        sunwell "Build a REST API with auth"
        sunwell -s a-2 docs/api.md
        sunwell -s p docs/cli.md
        sunwell config model

    \b
    SHORTCUTS (use with -s):
        a, a-2      Audit (quick, deep)
        p           Polish
        health      Health check
        drift       Drift detection
        pipeline    Full docs pipeline

    \b
    For interactive mode:

        sunwell chat

    \b
    The light illuminates the path. ✧
    """
    load_dotenv()
    check_free_threading(quiet=quiet)

    # RFC-109: Show all commands if requested
    if all_commands:
        _show_all_commands(ctx)
        return

    # Get goal or path from custom parsing
    ctx.ensure_object(dict)
    goal = ctx.obj.get("_goal")
    open_path = ctx.obj.get("_open_path")

    # RFC-109: Handle -s/--skill shortcut execution
    if skill_shortcut and ctx.invoked_subcommand is None:
        from sunwell.interface.cli.core.shortcuts import run_shortcut

        # Get positional target from context (after the shortcut)
        positional_target = ctx.obj.get("_positional_target")
        target = skill_target or positional_target
        context_str = ctx.obj.get("_context_str")

        run_async(
            run_shortcut(
                shortcut=skill_shortcut,
                target=target,
                context_str=context_str,
                lens_name=lens,
                provider=provider,
                model=model,
                plan_only=plan,
                json_output=json_output,
                verbose=verbose,
            )
        )
        return

    # RFC-086: If a path was provided (sunwell . or sunwell ~/path), open project
    if open_path and ctx.invoked_subcommand is None:
        from sunwell.interface.cli.commands import open_cmd

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
        from sunwell.interface.cli.commands.goal import run_goal

        ctx.invoke(
            run_goal,
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
            converge=converge,
            converge_gates=converge_gates,
            converge_max=converge_max,
        )


@main.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--json-output", is_flag=True)
@click.option("--provider", "-p", default=None)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
@click.option("--workspace", "-w", default=None)
@async_command
async def _run_goal(
    goal: str,
    dry_run: bool,
    json_output: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
    time: int,
    trust: str,
    workspace: str | None,
) -> None:
    """Internal command for goal execution (RFC-MEMORY)."""
    from sunwell.interface.cli.commands.goal import run_agent

    workspace_path = Path(workspace) if workspace else None
    # RFC-MEMORY: Single unified execution path - use modular version
    await run_agent(
        goal, time, trust, dry_run, verbose, provider, model, workspace_path,
        json_output=json_output,
    )


# =============================================================================
# RFC-109: COMMAND REGISTRATION (Tiered Visibility)
# =============================================================================
#
# Tier 1-2 (Visible): config, project, session, lens, setup
# Tier 3 (Hidden):    benchmark, chat, demo, eval, index, runtime
# Tier 4 (Internal):  backlog, dag, interface, naaru, scan, security, self,
#                     skill, surface, weakness, workers, workflow, workspace
# =============================================================================


# -----------------------------------------------------------------------------
# TIER 1-2: Primary User Interface (shown in --help)
# These are the 5 primary commands users interact with
# -----------------------------------------------------------------------------

# Configuration management (absorbs bind, env)
from sunwell.interface.cli.commands import config_cmd

main.add_command(config_cmd.config)

# Project operations (absorbs workspace, scan, import)
from sunwell.interface.cli.commands import project_cmd

main.add_command(project_cmd.project)

# Session management (absorbs team)
from sunwell.interface.cli.core import session

main.add_command(session.sessions)

# Lens management
from sunwell.interface.cli.core import lens

main.add_command(lens.lens)

# First-time setup wizard
from sunwell.interface.cli.core import setup

main.add_command(setup.setup)

# HTTP server for Studio UI (RFC-113)
from sunwell.interface.cli.commands import serve_cmd

main.add_command(serve_cmd.serve)

# Debug and diagnostics (RFC-120)
from sunwell.interface.cli.commands import debug_cmd

main.add_command(debug_cmd.debug)

# Artifact Lineage (RFC-121)
from sunwell.interface.cli.commands import lineage_cmd

main.add_command(lineage_cmd.lineage)

# Recovery & Review (RFC-125)
from sunwell.interface.cli.commands import review_cmd

main.add_command(review_cmd.review)


# -----------------------------------------------------------------------------
# TIER 3: Hidden Commands (developer/power user)
# Accessible via full command name, but not shown in --help
# Use `sunwell --all-commands` to see these
# -----------------------------------------------------------------------------

# Interactive REPL mode
from sunwell.interface.cli.chat import chat

main.add_command(chat)

# Benchmark suite
from sunwell.benchmark.cli import benchmark

main.add_command(click.Command(
    name="benchmark",
    callback=benchmark.callback if hasattr(benchmark, 'callback') else benchmark,
    help="Run benchmark suite",
    hidden=True,
))

# Demo command - Prism Principle demonstrations
from sunwell.interface.cli.commands import demo_cmd

main.add_command(click.Command(
    name="demo",
    callback=demo_cmd.demo.callback,
    params=demo_cmd.demo.params,
    help=demo_cmd.demo.help,
    hidden=True,
))

# Evaluation suite
from sunwell.interface.cli.commands import eval_cmd

main.add_command(click.Command(
    name="eval",
    callback=eval_cmd.eval_cmd.callback,
    params=eval_cmd.eval_cmd.params,
    help=eval_cmd.eval_cmd.help,
    hidden=True,
))

# Runtime management
from sunwell.interface.cli.commands import runtime_cmd

main.add_command(click.Command(
    name="runtime",
    callback=runtime_cmd.runtime.callback if hasattr(runtime_cmd.runtime, 'callback') else None,
    help="Runtime management",
    hidden=True,
))


# -----------------------------------------------------------------------------
# TIER 4: Internal Commands (Studio integration only)
# These are called by Studio via subprocess - MUST remain stable
# Hidden from all help, but fully functional
# -----------------------------------------------------------------------------

# Autonomous Backlog (RFC-046) - Studio: backlog refresh/run
from sunwell.interface.cli.commands import backlog_cmd

backlog_cmd.backlog.hidden = True
main.add_command(backlog_cmd.backlog)

# DAG and Incremental Execution (RFC-074) - Studio: dag plan/cache/impact
from sunwell.interface.cli.commands import dag_cmd

dag_cmd.dag.hidden = True
main.add_command(dag_cmd.dag)

# Generative Interface (RFC-075) - Studio: interface demo
from sunwell.interface.cli.commands import interface_cmd

interface_cmd.interface.hidden = True
main.add_command(interface_cmd.interface)

# Naaru coordination - Studio: naaru process/convergence
from sunwell.interface.cli.commands.agent import agent

agent.hidden = True
main.add_command(agent)

# State DAG Scanning (RFC-100) - Studio: scan <path>
from sunwell.interface.cli.commands import scan_cmd

scan_cmd.scan.hidden = True
main.add_command(scan_cmd.scan)

# Security-First Skill Execution (RFC-089) - Studio: security analyze/approve/audit/scan
from sunwell.interface.cli.commands import security_cmd

security_cmd.security.hidden = True
main.add_command(security_cmd.security)

# Self-Knowledge (RFC-085) - Studio: self source/analysis/proposals/summary
from sunwell.interface.cli.commands import self_cmd

self_cmd.self_cmd.hidden = True
main.add_command(self_cmd.self_cmd, name="self")

# Surface Primitives & Layout (RFC-072) - Studio: surface registry
from sunwell.interface.cli.surface import surface

surface.hidden = True
main.add_command(surface)

# Weakness Cascade (RFC-063) - Studio: weakness scan/preview/extract-contract
from sunwell.interface.cli.commands import weakness_cmd

weakness_cmd.weakness.hidden = True
main.add_command(weakness_cmd.weakness)

# Multi-Instance Coordination (RFC-051) - Studio: workers ui-state/pause/resume/start
from sunwell.interface.cli.commands import workers_cmd

workers_cmd.workers.hidden = True
main.add_command(workers_cmd.workers)

# Autonomous Workflow Execution (RFC-086) - Studio: workflow auto/run/stop/resume/skip/chains/list
from sunwell.interface.cli.commands import workflow_cmd

workflow_cmd.workflow.hidden = True
main.add_command(workflow_cmd.workflow)

# Workspace-Aware Scanning (RFC-103) - Studio: workspace detect/show/link/unlink/list
from sunwell.interface.cli.commands import workspace_cmd

workspace_cmd.workspace.hidden = True
main.add_command(workspace_cmd.workspace)

# Continuous Codebase Indexing (RFC-108) - Studio: index build/query/metrics
from sunwell.interface.cli.commands import index_cmd

index_cmd.index.hidden = True
main.add_command(index_cmd.index)

# ToC Navigation (RFC-124) - Studio: nav build/find/show/stats
from sunwell.interface.cli.commands import nav_cmd

nav_cmd.nav.hidden = True
main.add_command(nav_cmd.nav)


# -----------------------------------------------------------------------------
# TIER 4 CONTINUED: Additional internal commands
# -----------------------------------------------------------------------------

# Project Intelligence commands (RFC-045) - hidden
from sunwell.interface.cli.commands import intel_cmd

intel_cmd.intel.hidden = True
main.add_command(intel_cmd.intel)

# Plan command for DAG visualization - hidden
from sunwell.interface.cli.commands import plan_cmd

plan_cmd.plan.hidden = True
main.add_command(plan_cmd.plan)

# Deep Verification (RFC-047) - hidden
from sunwell.interface.cli.commands import verify_cmd

verify_cmd.verify.hidden = True
main.add_command(verify_cmd.verify)

# Autonomy Guardrails (RFC-048) - hidden
from sunwell.interface.cli.commands import guardrails_cmd

guardrails_cmd.guardrails.hidden = True
main.add_command(guardrails_cmd.guardrails)

# External Integration (RFC-049) - hidden
from sunwell.interface.cli.commands import external_cmd

external_cmd.external.hidden = True
main.add_command(external_cmd.external)

# Fast Bootstrap (RFC-050) - hidden
from sunwell.interface.cli.commands import bootstrap_cmd

bootstrap_cmd.bootstrap.hidden = True
main.add_command(bootstrap_cmd.bootstrap)

# Team Intelligence (RFC-052) - hidden
from sunwell.interface.cli.commands import team_cmd

team_cmd.team.hidden = True
main.add_command(team_cmd.team)

# Project Import (RFC-043 addendum) - hidden
from sunwell.interface.cli.commands import import_cmd

import_cmd.import_project.hidden = True
main.add_command(import_cmd.import_project, name="import")

# Briefing System (RFC-071) - hidden
from sunwell.interface.cli.commands import briefing_cmd

briefing_cmd.briefing.hidden = True
main.add_command(briefing_cmd.briefing)

# Reasoned Decisions (RFC-073) - hidden
from sunwell.interface.cli.core import reason

reason.reason.hidden = True
main.add_command(reason.reason)

# Universal Writing Environment (RFC-086) - hidden
from sunwell.interface.cli.commands import open_cmd

open_cmd.open_project.hidden = True
main.add_command(open_cmd.open_project, name="open")

# User Environment Model (RFC-104) - hidden
from sunwell.interface.cli.commands import env_cmd

env_cmd.env.hidden = True
main.add_command(env_cmd.env)

# Configuration binding - hidden (absorbed into config)
from sunwell.interface.cli.core import bind

bind.bind.hidden = True
main.add_command(bind.bind)

# RFC-111: Skill library management (learn, list, import)
from sunwell.interface.cli.commands import skills_cmd

main.add_command(skills_cmd.skills_group)

# RFC-115: Hierarchical Goal Decomposition (epic commands)
from sunwell.interface.cli.commands import epic_cmd

main.add_command(epic_cmd.epic)

# RFC-130: Agent Constellation (autonomous and guard commands)
from sunwell.interface.cli.commands import autonomous_cmd, guard_cmd

main.add_command(autonomous_cmd.autonomous)
main.add_command(guard_cmd.guard)

# -----------------------------------------------------------------------------
# Internal Command Group (CLI Core Refactor)
# Provides organized access to all internal/Studio commands via:
#   sunwell internal <group> <subcommand>
# Original top-level hidden commands are kept for backwards compatibility.
# -----------------------------------------------------------------------------
from sunwell.interface.cli.commands.internal_cmd import register_internal_commands

register_internal_commands(main)
