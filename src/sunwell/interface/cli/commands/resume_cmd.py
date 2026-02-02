"""Top-level resume command for goal continuity.

Provides a simple way to resume interrupted goals:
    sunwell resume              # Resume latest
    sunwell resume --list       # List resumable goals
    sunwell resume <session-id> # Resume specific
"""

import asyncio
from datetime import datetime
from pathlib import Path

import click

from sunwell.interface.cli.core.async_runner import async_command
from sunwell.interface.cli.core.theme import create_sunwell_console

console = create_sunwell_console()


def _format_time_ago(dt: datetime) -> str:
    """Format a datetime as relative time (e.g., '2 min ago')."""
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"


@click.command()
@click.argument("session_id", required=False)
@click.option("--list", "-l", "list_sessions", is_flag=True, help="List resumable goals")
@click.option(
    "--workspace", "-w", is_flag=True, help="Filter to current workspace only"
)
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all sessions, not just resumable")
@click.option("--provider", "-p", default=None, help="Model provider")
@click.option("--model", "-m", default=None, help="Override model")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@async_command
async def resume(
    session_id: str | None,
    list_sessions: bool,
    workspace: bool,
    show_all: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Resume an interrupted goal.

    Without arguments, resumes the most recent paused goal.

    \b
    Examples:
        sunwell resume              # Resume latest paused goal
        sunwell resume --list       # List all resumable goals
        sunwell resume abc123       # Resume specific session
        sunwell resume -w           # Resume latest in current workspace
    """
    from sunwell.planning.naaru.session_store import SessionStore, SessionSummary
    from sunwell.planning.naaru.types import SessionStatus

    store = SessionStore()

    # List mode
    if list_sessions or show_all:
        await _list_sessions(store, show_all, workspace)
        return

    # Find session to resume
    if session_id:
        # Resume specific session
        state = store.load(session_id)
        if not state:
            console.print(f"[void.purple]✗ Session not found:[/] {session_id}")
            console.print("[dim]Run 'sunwell resume --list' to see available sessions[/dim]")
            return
        session = SessionSummary(
            session_id=state.session_id,
            status=state.status,
            goals=state.config.goals,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
            stop_reason=state.stop_reason,
            opportunities_total=len(state.opportunities) + len(state.completed),
            opportunities_completed=len(state.completed),
            project_id=None,
            workspace_id=None,
        )
    else:
        # Find latest resumable
        resumable = store.get_resumable_sessions()

        # Filter by workspace if requested
        if workspace:
            workspace_path = str(Path.cwd())
            resumable = [s for s in resumable if s.workspace_id == workspace_path]

        if not resumable:
            console.print("[neutral.dim]No resumable goals found.[/neutral.dim]")
            console.print("[dim]Run a goal first: sunwell \"your goal\"[/dim]")
            return

        session = resumable[0]  # Most recent

    # Show session info
    goal_preview = session.goals[0] if session.goals else "Unknown goal"
    if len(goal_preview) > 60:
        goal_preview = goal_preview[:57] + "..."

    console.print()
    console.print(f"[sunwell.heading]◆ Resuming:[/] {goal_preview}")
    console.print(f"   Session: {session.session_id}")
    console.print(f"   Started: {_format_time_ago(session.started_at)}")
    console.print(f"   Status: {session.status.value}")

    if session.opportunities_total > 0:
        console.print(
            f"   Progress: {session.opportunities_completed}/{session.opportunities_total} tasks"
        )

    console.print()

    # Confirm resume
    if not click.confirm("Resume this goal?", default=True):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    # Delegate to agent resume
    await _execute_resume(session.session_id, session.goals, provider, model, verbose)


async def _list_sessions(
    store,
    show_all: bool,
    filter_workspace: bool,
) -> None:
    """List sessions in a formatted table."""
    from sunwell.planning.naaru.types import SessionStatus

    if show_all:
        sessions = store.list_sessions(limit=20)
    else:
        sessions = store.get_resumable_sessions()

    if filter_workspace:
        workspace_path = str(Path.cwd())
        sessions = [s for s in sessions if s.workspace_id == workspace_path]

    if not sessions:
        if show_all:
            console.print("[neutral.dim]No sessions found.[/neutral.dim]")
        else:
            console.print("[neutral.dim]No resumable goals found.[/neutral.dim]")
        console.print("[dim]Run a goal first: sunwell \"your goal\"[/dim]")
        return

    # Header
    title = "All Sessions" if show_all else "Resumable Goals"
    console.print(f"\n[sunwell.heading]◆ {title}[/sunwell.heading]\n")

    # Status indicators
    status_icons = {
        SessionStatus.RUNNING: "[yellow]●[/yellow]",
        SessionStatus.PAUSED: "[cyan]◐[/cyan]",
        SessionStatus.COMPLETED: "[green]✓[/green]",
        SessionStatus.FAILED: "[red]✗[/red]",
        SessionStatus.INITIALIZING: "[dim]○[/dim]",
    }

    for session in sessions:
        goal_preview = session.goals[0] if session.goals else "Unknown"
        if len(goal_preview) > 50:
            goal_preview = goal_preview[:47] + "..."

        icon = status_icons.get(session.status, "○")
        time_ago = _format_time_ago(session.started_at)

        # Progress info
        progress = ""
        if session.opportunities_total > 0:
            progress = f" ({session.opportunities_completed}/{session.opportunities_total})"

        console.print(
            f"  {icon} [bold]{session.session_id[:8]}[/bold] "
            f"{goal_preview}{progress} [dim]{time_ago}[/dim]"
        )

    console.print()
    console.print("[dim]Resume with: sunwell resume <session-id>[/dim]")


async def _execute_resume(
    session_id: str,
    goals: tuple[str, ...],
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Execute the resume using Naaru."""
    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.planning.naaru import Naaru
    from sunwell.planning.naaru.session_store import SessionStore
    from sunwell.planning.naaru.types import SessionStatus
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    store = SessionStore()
    state = store.load(session_id)

    if not state:
        console.print("[void.purple]✗ Session state not found[/void.purple]")
        return

    workspace = Path.cwd()

    # Resolve project context
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        project = create_project_from_workspace(workspace)

    tool_executor = ToolExecutor(
        project=project,
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Load model
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider, model)
    except Exception as e:
        console.print(f"[holy.gold]△ Warning: Could not load model: {e}[/holy.gold]")

    # Update status to running
    state.status = SessionStatus.RUNNING
    store.save(state)

    naaru = Naaru(
        workspace=workspace,
        synthesis_model=synthesis_model,
        tool_executor=tool_executor,
    )

    goal = goals[0] if goals else "Resume previous task"

    console.print(f"\n[holy.radiant]◆ Resuming execution[/holy.radiant]\n")

    try:
        result = await naaru.run(
            goal=goal,
            context={
                "cwd": str(workspace),
                "session_id": session_id,
                "completed_ids": [c.opportunity_id for c in state.completed] if state.completed else [],
                "resume": True,
            },
            on_progress=console.print if verbose else None,
        )

        # Update session state
        state.status = SessionStatus.COMPLETED
        state.stop_reason = "Goal completed via resume"
        store.save(state)

        done = result.completed_count
        total = len(result.tasks)
        console.print(f"\n[holy.success]★ Complete:[/holy.success] {done}/{total} tasks")

    except KeyboardInterrupt:
        # Save as paused
        state.status = SessionStatus.PAUSED
        state.stop_reason = "Interrupted by user"
        store.save(state)

        console.print("\n  [neutral.dim]◈ Goal paused[/]")
        console.print("  [dim]Resume with: sunwell resume[/dim]")

    except Exception as e:
        state.status = SessionStatus.FAILED
        state.stop_reason = str(e)
        store.save(state)

        console.print(f"\n[void.purple]✗ Error: {e}[/void.purple]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
