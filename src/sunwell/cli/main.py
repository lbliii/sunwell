"""Main CLI entry point - Goal-first interface (RFC-037, RFC-109).

The primary interface is now simply:
    sunwell "Build a REST API with auth"
    sunwell -s a-2 docs/api.md

RFC-109: CLI simplified to 5 primary commands.
All other commands are progressive disclosure or hidden for Studio.
"""


import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

from sunwell.cli.helpers import check_free_threading, load_dotenv
from sunwell.cli.shortcuts import complete_shortcut, complete_target

console = Console()


def cli_entrypoint() -> None:
    """Wrapped entrypoint with global error handling.

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
        # User cancelled (Ctrl+C)
        console.print("\n[dim]Aborted.[/dim]")
        sys.exit(130)
    except Exception as e:
        # Handle SunwellError with nice formatting
        from sunwell.cli.error_handler import handle_error
        from sunwell.core.errors import SunwellError

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

    def parse_args(self, ctx, args):
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
@click.option("--all-commands", is_flag=True, hidden=True,
              help="Show all commands including hidden")
@click.version_option(version="0.2.0")
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
    all_commands: bool,
) -> None:
    """Sunwell — AI agent for software tasks.

    \b
    USAGE:
        sunwell [OPTIONS] [GOAL]
        sunwell -s <SHORTCUT> [TARGET]
        sunwell <COMMAND>

    \b
    EXAMPLES:
        sunwell "Build a REST API with auth"
        sunwell -s a-2 docs/api.md
        sunwell -s a-2 docs/api.md "focus on the migration section"
        sunwell -s p docs/cli.md
        sunwell config model
        sunwell project ~/myapp

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
    For all commands (including hidden):

        sunwell --all-commands
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
        from sunwell.cli.shortcuts import run_shortcut

        # Get positional target from context (after the shortcut)
        positional_target = ctx.obj.get("_positional_target")
        target = skill_target or positional_target
        context_str = ctx.obj.get("_context_str")

        asyncio.run(
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
    """Execute goal with Agent (RFC-110).

    This is THE unified entry point. The Agent automatically:
    - Extracts signals to select techniques
    - Uses Harmonic planning for complex goals
    - Validates at gates with fail-fast
    - Auto-fixes errors with Compound Eye
    - Persists learnings via Simulacrum

    RFC-110: Agent renamed to Agent and moved to agent/ module.

    RFC-090 additions:
    - open_studio: Launch Studio with plan after --plan
    - json_output: Output plan as JSON for scripting
    """
    from sunwell.agent import (
        AdaptiveBudget,
        Agent,
        EventType,
        RunOptions,
        RunRequest,
        create_renderer,
    )
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
        if verbose and not json_output:
            provider = provider_override or config.model.default_provider if config else "ollama"
            model_name = model_override or config.model.default_model if config else "gemma3:4b"
            console.print(f"[dim]Using model: {provider}:{model_name}[/dim]")

    except Exception as e:
        if not json_output:
            console.print(f"[yellow]Warning: Could not load model: {e}[/yellow]")

    if not synthesis_model:
        if json_output:
            print('{"type": "error", "data": {"message": "No model available"}}')
        else:
            console.print("[red]No model available[/red]")
        return

    # RFC-117: Try to resolve project context for workspace
    from sunwell.project import ProjectResolutionError, resolve_project

    project = None
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        pass  # Use workspace directly

    # Setup tool executor with resolved workspace
    trust_level = ToolTrust.from_string(trust)
    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(trust_level=trust_level),
    )

    if verbose and not json_output:
        console.print(f"[dim]Trust level: {trust}[/dim]")
        available_tools = frozenset(tool_executor.get_available_tools())
        console.print(f"[dim]Available tools: {', '.join(sorted(available_tools))}[/dim]")

    # Create Agent with resolved workspace (RFC-110)
    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=workspace,
        budget=AdaptiveBudget(total_budget=50_000),
    )

    # Build RunRequest
    request = RunRequest(
        goal=goal,
        context={"cwd": str(Path.cwd())},
        cwd=workspace,
        options=RunOptions(
            trust=trust,
            timeout_seconds=time,
        ),
    )

    # Dry run: just plan (RFC-090 enhanced)
    if dry_run:
        plan_data = None
        async for event in agent.plan(request):
            if event.type == EventType.PLAN_WINNER:
                plan_data = event.data
            elif event.type == EventType.ERROR and not json_output:
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

    # Create renderer based on output mode (RFC-110: import from agent/)
    renderer_mode = "json" if json_output else "interactive"
    renderer = create_renderer(mode=renderer_mode, verbose=verbose)

    # Full execution (RFC-110: Agent.run() takes RunRequest)
    try:
        await renderer.render(agent.run(request))

    except KeyboardInterrupt:
        if json_output:
            print('{"type": "error", "data": {"message": "Interrupted by user"}}')
        else:
            console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        if json_output:
            import json as json_module
            print(json_module.dumps({"type": "error", "data": {"message": str(e)}}))
        else:
            console.print(f"\n[red]Error: {e}[/red]")
            if verbose:
                import traceback
                console.print(traceback.format_exc())


def _print_event(event, verbose: bool) -> None:
    """Print an agent event to console."""
    from sunwell.agent import EventType

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

    console.print("\n[cyan]Opening plan in Studio...[/cyan]")

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
                heuristics = ", ".join(summary.get("heuristics", []))
                sources = ", ".join(summary.get("source_lenses", []))
                console.print(f"[dim]  Heuristics: {heuristics}[/dim]")
                console.print(f"[dim]  Sources: {sources}[/dim]")
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
from sunwell.cli import config_cmd

main.add_command(config_cmd.config)

# Project operations (absorbs workspace, scan, import)
from sunwell.cli import project_cmd

main.add_command(project_cmd.project)

# Session management (absorbs team)
from sunwell.cli import session

main.add_command(session.sessions)

# Lens management
from sunwell.cli import lens

main.add_command(lens.lens)

# First-time setup wizard
from sunwell.cli import setup

main.add_command(setup.setup)

# HTTP server for Studio UI (RFC-113)
from sunwell.cli import serve_cmd

main.add_command(serve_cmd.serve)


# -----------------------------------------------------------------------------
# TIER 3: Hidden Commands (developer/power user)
# Accessible via full command name, but not shown in --help
# Use `sunwell --all-commands` to see these
# -----------------------------------------------------------------------------

# Interactive REPL mode
from sunwell.cli import chat

main.add_command(click.Command(
    name="chat",
    callback=chat.chat.callback,
    params=chat.chat.params,
    help=chat.chat.help,
    hidden=True,  # RFC-109: Deprioritized but retained
))

# Benchmark suite
from sunwell.benchmark.cli import benchmark

main.add_command(click.Command(
    name="benchmark",
    callback=benchmark.callback if hasattr(benchmark, 'callback') else benchmark,
    help="Run benchmark suite",
    hidden=True,
))

# Demo command - Prism Principle demonstrations
from sunwell.cli import demo_cmd

main.add_command(click.Command(
    name="demo",
    callback=demo_cmd.demo.callback,
    params=demo_cmd.demo.params,
    help=demo_cmd.demo.help,
    hidden=True,
))

# Evaluation suite
from sunwell.cli import eval_cmd

main.add_command(click.Command(
    name="eval",
    callback=eval_cmd.eval_cmd.callback,
    params=eval_cmd.eval_cmd.params,
    help=eval_cmd.eval_cmd.help,
    hidden=True,
))

# Runtime management
from sunwell.cli import runtime_cmd

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
from sunwell.cli import backlog_cmd

backlog_cmd.backlog.hidden = True
main.add_command(backlog_cmd.backlog)

# DAG and Incremental Execution (RFC-074) - Studio: dag plan/cache/impact
from sunwell.cli import dag_cmd

dag_cmd.dag.hidden = True
main.add_command(dag_cmd.dag)

# Generative Interface (RFC-075) - Studio: interface demo
from sunwell.cli import interface_cmd

interface_cmd.interface.hidden = True
main.add_command(interface_cmd.interface)

# Naaru coordination - Studio: naaru process/convergence
from sunwell.cli.agent import agent

agent.hidden = True
main.add_command(agent)
# Keep 'naaru' as hidden alias for backward compatibility
naaru_alias = click.Group(
    name="naaru",
    commands=agent.commands,
    help=agent.help,
    hidden=True,
)
main.add_command(naaru_alias)

# State DAG Scanning (RFC-100) - Studio: scan <path>
from sunwell.cli import scan_cmd

scan_cmd.scan.hidden = True
main.add_command(scan_cmd.scan)

# Security-First Skill Execution (RFC-089) - Studio: security analyze/approve/audit/scan
from sunwell.cli import security_cmd

security_cmd.security.hidden = True
main.add_command(security_cmd.security)

# Self-Knowledge (RFC-085) - Studio: self source/analysis/proposals/summary
from sunwell.cli import self_cmd

self_cmd.self_cmd.hidden = True
main.add_command(self_cmd.self_cmd, name="self")

# RFC-110: skill CLI deprecated - skill execution moved to Agent

# Surface Primitives & Layout (RFC-072) - Studio: surface registry
from sunwell.cli import surface

surface.surface.hidden = True
main.add_command(surface.surface)

# Weakness Cascade (RFC-063) - Studio: weakness scan/preview/extract-contract
from sunwell.cli import weakness_cmd

weakness_cmd.weakness.hidden = True
main.add_command(weakness_cmd.weakness)

# Multi-Instance Coordination (RFC-051) - Studio: workers ui-state/pause/resume/start
from sunwell.cli import workers_cmd

workers_cmd.workers.hidden = True
main.add_command(workers_cmd.workers)

# Autonomous Workflow Execution (RFC-086) - Studio: workflow auto/run/stop/resume/skip/chains/list
from sunwell.cli import workflow_cmd

workflow_cmd.workflow.hidden = True
main.add_command(workflow_cmd.workflow)

# Workspace-Aware Scanning (RFC-103) - Studio: workspace detect/show/link/unlink/list
from sunwell.cli import workspace_cmd

workspace_cmd.workspace.hidden = True
main.add_command(workspace_cmd.workspace)

# Continuous Codebase Indexing (RFC-108) - Studio: index build/query/metrics
from sunwell.cli import index_cmd

index_cmd.index.hidden = True
main.add_command(index_cmd.index)


# -----------------------------------------------------------------------------
# TIER 4 CONTINUED: Additional internal commands
# -----------------------------------------------------------------------------

# Project Intelligence commands (RFC-045) - hidden
from sunwell.cli import intel_cmd

intel_cmd.intel.hidden = True
main.add_command(intel_cmd.intel)

# Plan command for DAG visualization - hidden
from sunwell.cli import plan_cmd

plan_cmd.plan.hidden = True
main.add_command(plan_cmd.plan)

# Deep Verification (RFC-047) - hidden
from sunwell.cli import verify_cmd

verify_cmd.verify.hidden = True
main.add_command(verify_cmd.verify)

# Autonomy Guardrails (RFC-048) - hidden
from sunwell.cli import guardrails_cmd

guardrails_cmd.guardrails.hidden = True
main.add_command(guardrails_cmd.guardrails)

# External Integration (RFC-049) - hidden
from sunwell.cli import external_cmd

external_cmd.external.hidden = True
main.add_command(external_cmd.external)

# Fast Bootstrap (RFC-050) - hidden
from sunwell.cli import bootstrap_cmd

bootstrap_cmd.bootstrap.hidden = True
main.add_command(bootstrap_cmd.bootstrap)

# Team Intelligence (RFC-052) - hidden
from sunwell.cli import team_cmd

team_cmd.team.hidden = True
main.add_command(team_cmd.team)

# Project Import (RFC-043 addendum) - hidden
from sunwell.cli import import_cmd

import_cmd.import_project.hidden = True
main.add_command(import_cmd.import_project, name="import")

# Briefing System (RFC-071) - hidden
from sunwell.cli import briefing_cmd

briefing_cmd.briefing.hidden = True
main.add_command(briefing_cmd.briefing)

# Reasoned Decisions (RFC-073) - hidden
from sunwell.cli import reason

reason.reason.hidden = True
main.add_command(reason.reason)

# Universal Writing Environment (RFC-086) - hidden
from sunwell.cli import open_cmd

open_cmd.open_project.hidden = True
main.add_command(open_cmd.open_project, name="open")

# User Environment Model (RFC-104) - hidden
from sunwell.cli import env_cmd

env_cmd.env.hidden = True
main.add_command(env_cmd.env)

# Configuration binding - hidden (absorbed into config)
from sunwell.cli import bind

bind.bind.hidden = True
main.add_command(bind.bind)

# RFC-110: Legacy commands deleted (ask, apply, do_cmd, naaru_cmd)
# These entry points are consolidated into Agent.run()
# - sunwell ask -> sunwell "goal"
# - sunwell apply -> sunwell -s shortcut
# - sunwell do -> sunwell -s shortcut
# - sunwell naaru process -> sunwell "goal"

# RFC-110: Legacy skill commands removed - skill execution moved to Agent

# RFC-111: Skill library management (learn, list, import)
from sunwell.cli import skills_cmd

main.add_command(skills_cmd.skills_group)

# RFC-115: Hierarchical Goal Decomposition (epic commands)
from sunwell.cli import epic_cmd

main.add_command(epic_cmd.epic)

# -----------------------------------------------------------------------------
# RFC-109: Register deprecated command aliases
# -----------------------------------------------------------------------------

from sunwell.cli.deprecated import register_deprecated_commands

register_deprecated_commands(main)
