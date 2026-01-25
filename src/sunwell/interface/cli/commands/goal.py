"""Goal execution command for CLI."""

import asyncio
from pathlib import Path

import click

from sunwell.agent import (
    AdaptiveBudget,
    Agent,
    EventType,
    RunOptions,
    create_renderer,
)
from sunwell.foundation.utils import safe_json_dumps
from sunwell.interface.cli.helpers.project import extract_project_name
from sunwell.interface.cli.helpers.events import print_event, print_plan_details
from sunwell.interface.cli.helpers import resolve_model  # type: ignore[attr-defined]  # In helpers.py, not helpers/
from sunwell.interface.cli.core.theme import console, print_banner
from sunwell.interface.cli.workspace_prompt import resolve_workspace_interactive
from sunwell.foundation.config import get_config
from sunwell.agent.context.session import SessionContext
from sunwell.memory import PersistentMemory
from sunwell.knowledge.project import ProjectResolutionError, resolve_project
from sunwell.tools.execution import ToolExecutor
from sunwell.tools.core.types import ToolPolicy, ToolTrust


@click.command(name="_run", hidden=True)
@click.argument("goal")
@click.option("--dry-run", is_flag=True)
@click.option("--json-output", is_flag=True)
@click.option("--provider", "-p", default=None)
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--time", "-t", default=300)
@click.option("--trust", default="workspace")
@click.option("--workspace", "-w", default=None)
def run_goal(
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
    workspace_path = Path(workspace) if workspace else None
    # RFC-MEMORY: Single unified execution path
    asyncio.run(run_agent(
        goal, time, trust, dry_run, verbose, provider, model, workspace_path,
        json_output=json_output,
    ))


async def run_agent(
    goal: str,
    time: int,
    trust: str,
    dry_run: bool,
    verbose: bool,
    provider_override: str | None,
    model_override: str | None,
    workspace_path: Path | None = None,
    *,
    json_output: bool = False,
) -> None:
    """Execute goal with Agent (RFC-MEMORY, RFC-131).

    This is THE unified entry point using:
    - SessionContext: All session state in one object
    - PersistentMemory: Unified access to all memory stores
    - Agent.run(session, memory): Memory flows through, not around

    The Agent automatically:
    - Orients using persistent memory (decisions, failures, patterns)
    - Extracts signals to select techniques
    - Uses Harmonic planning with memory constraints
    - Validates at gates with fail-fast
    - Auto-fixes errors with Compound Eye
    - Persists learnings via PersistentMemory

    Args:
        goal: The goal to execute
        time: Max execution time in seconds
        trust: Trust level (read_only, workspace, shell)
        dry_run: If True, only plan without executing
        verbose: Show verbose output
        provider_override: Override provider selection
        model_override: Override model selection
        workspace_path: Explicit workspace path
        json_output: Output as JSON
    """
    # RFC-131: Show Holy Light banner (except in JSON mode)
    if not json_output:
        print_banner(console, version="0.3.0", small=True)

    # Load config (currently unused but needed for future config access)
    _ = get_config()

    # Resolve workspace
    project_name = extract_project_name(goal)
    workspace = resolve_workspace_interactive(
        explicit=workspace_path,
        project_name=project_name,
        quiet=not verbose,
    )

    # Create model
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
    except Exception as e:
        # RFC-131: Holy Light error styling
        console.print(f"  [void.purple]✗[/] [sunwell.error]Failed to load model:[/] {e}")
        return

    # Create tool executor
    trust_map = {
        "read_only": ToolTrust.READ_ONLY,
        "workspace": ToolTrust.WORKSPACE,
        "shell": ToolTrust.SHELL,
    }
    trust_level = trust_map.get(trust, ToolTrust.WORKSPACE)
    policy = ToolPolicy(trust_level=trust_level)
    
    # Resolve project from workspace
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError as e:
        console.print(f"  [void.purple]✗[/] [sunwell.error]Failed to resolve project:[/] {e}")
        return
    
    tool_executor = ToolExecutor(project=project, policy=policy)

    # Create agent
    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=workspace,
        budget=AdaptiveBudget(total_budget=50_000),
    )

    # RFC-MEMORY: Build SessionContext and load PersistentMemory
    options = RunOptions(
        trust=trust,
        timeout_seconds=time,
    )
    session = SessionContext.build(workspace, goal, options)
    memory = PersistentMemory.load(workspace)

    # RFC-131: Holy Light styled verbose output
    if verbose:
        console.print(f"  [neutral.dim]· Session: {session.session_id}[/]")
        fw = session.framework or "no framework"
        console.print(f"  [neutral.dim]· Project: {session.project_type} ({fw})[/]")
        learn = memory.learning_count
        dec = memory.decision_count
        fail = memory.failure_count
        console.print(f"  [neutral.dim]· Memory: {learn}L / {dec}D / {fail}F[/]")
        console.print()

    # Dry run: just plan
    if dry_run:
        if not json_output:
            # RFC-131: Holy Light styled dry run message
            console.print("  [void.indigo]◇[/] [sunwell.warning]Dry run mode — planning only[/]\n")

        plan_data: dict[str, str | int | list[dict[str, str | list[str]]]] | None = None
        async for event in agent.plan(session, memory):
            if event.type == EventType.PLAN_WINNER:
                plan_data = event.data
            elif event.type == EventType.ERROR and not json_output:
                print_event(event, verbose)

        if plan_data:
            if json_output:
                click.echo(safe_json_dumps(plan_data, indent=2))
                return
            print_plan_details(plan_data, verbose, goal)
        return

    # Create renderer
    renderer_mode = "json" if json_output else "interactive"
    renderer = create_renderer(mode=renderer_mode, verbose=verbose)

    # RFC-MEMORY: Full execution with new architecture
    try:
        await renderer.render(agent.run(session, memory))

    except KeyboardInterrupt:
        if json_output:
            print('{"type": "error", "data": {"message": "Interrupted by user"}}')
        else:
            # RFC-131: Holy Light styled interrupt
            console.print("\n  [neutral.dim]◈ Paused by user[/]")
    except Exception as e:
        if json_output:
            import json as json_module
            print(json_module.dumps({"type": "error", "data": {"message": str(e)}}))
        else:
            # RFC-131: Holy Light error styling
            console.print(f"\n  [void.purple]✗[/] [sunwell.error]Error:[/] {e}")
            if verbose:
                import traceback
                console.print(f"[neutral.dim]{traceback.format_exc()}[/]")
