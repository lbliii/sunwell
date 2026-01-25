"""Session command group - Manage conversation sessions (RFC-120).

Provides:
- Conversation session management (existing)
- Session activity summaries (RFC-120)
"""


from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.simulacrum.core.store import SimulacrumStore

console = Console()


@click.group()
def sessions() -> None:
    """Manage conversation sessions and view activity summaries.

    Sessions persist across restarts, enabling multi-day conversations
    that never lose context. Activity summaries show what was accomplished.
    """
    pass


@sessions.command("list")
@click.option("--path", "-p", type=click.Path(), default=".sunwell/memory", help="Memory store path")
def sessions_list(path: str) -> None:
    """List all saved conversation sessions.

    Examples:

        sunwell sessions list

        sunwell sessions list --path ~/my-sessions/
    """
    store = SimulacrumStore(Path(path))
    saved = store.list_sessions()

    if not saved:
        console.print("[yellow]No sessions found.[/yellow]")
        console.print(f"[dim]Storage path: {path}[/dim]")
        return

    table = Table(title="Saved Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Turns", style="yellow")
    table.add_column("Created", style="dim")

    for s in saved:
        table.add_row(
            s["id"],
            s.get("name", "-"),
            str(s.get("turns", 0)),
            s.get("created", "-")[:16] if s.get("created") else "-",
        )

    console.print(table)


@sessions.command("stats")
@click.option("--path", "-p", type=click.Path(), default=".sunwell/memory", help="Memory store path")
def sessions_stats(path: str) -> None:
    """Show storage statistics.

    Examples:

        sunwell sessions stats
    """
    store = SimulacrumStore(Path(path))
    stats = store.stats()

    table = Table(title="Memory Store Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Session ID", stats.get("session_id", "-"))
    table.add_row("Hot Turns", str(stats.get("hot_turns", 0)))
    table.add_row("Warm Files", str(stats.get("warm_files", 0)))
    table.add_row("Warm Size", f"{stats.get('warm_size_mb', 0):.2f} MB")
    table.add_row("Cold Files", str(stats.get("cold_files", 0)))
    table.add_row("Cold Size", f"{stats.get('cold_size_mb', 0):.2f} MB")

    if "dag_stats" in stats:
        dag = stats["dag_stats"]
        table.add_row("---", "---")
        table.add_row("Total Turns", str(dag.get("total_turns", 0)))
        table.add_row("Branches", str(dag.get("branches", 0)))
        table.add_row("Dead Ends", str(dag.get("dead_ends", 0)))
        table.add_row("Learnings", str(dag.get("learnings", 0)))

    console.print(table)


@sessions.command("archive")
@click.option("--path", "-p", type=click.Path(), default=".sunwell/memory", help="Memory store path")
@click.option("--older-than", "-o", type=int, default=168, help="Archive turns older than N hours (default: 168 = 1 week)")
def sessions_archive(path: str, older_than: int) -> None:
    """Archive old turns to cold storage (compressed).

    Examples:

        sunwell sessions archive

        sunwell sessions archive --older-than 24  # Archive anything older than 1 day
    """
    store = SimulacrumStore(Path(path))
    moved = store.move_to_cold(older_than_hours=older_than)

    console.print(f"[green]✓ Archived {moved} files to cold storage[/green]")


# =============================================================================
# Session Activity Summary (RFC-120)
# =============================================================================


@sessions.command("summary")
@click.option("--session-id", "-s", default=None, help="Specific session ID to summarize")
@click.option("--format", "output_format", type=click.Choice(["human", "json"]), default="human")
def sessions_summary(session_id: str | None, output_format: str) -> None:
    """Show session activity summary.

    Displays what was accomplished during a coding session:
    - Goals completed/failed
    - Files created/modified
    - Lines added/removed
    - Top edited files
    - Timeline of activity

    \b
    Examples:
        sunwell sessions summary           # Current/recent session
        sunwell sessions summary --format json
        sunwell sessions summary -s abc123  # Specific session
    """
    import json

    from sunwell.session.tracker import SessionTracker

    # Try to load session
    if session_id:
        # Find specific session
        recent = SessionTracker.list_recent(limit=100)
        session_path = None
        for p in recent:
            if session_id in p.stem:
                session_path = p
                break

        if not session_path:
            console.print(f"[red]Session {session_id} not found[/red]")
            return

        tracker = SessionTracker.load(session_path)
    else:
        # Check for recent sessions
        recent = SessionTracker.list_recent(limit=1)
        if recent:
            tracker = SessionTracker.load(recent[0])
        else:
            # No saved sessions - create empty summary
            console.print("[yellow]No session data available yet.[/yellow]")
            console.print("[dim]Session data is recorded as goals complete.[/dim]")
            return

    summary = tracker.get_summary()

    if output_format == "json":
        print(json.dumps(summary.to_dict(), indent=2))
        return

    # Human format - rich display
    _display_session_summary(summary)


def _display_session_summary(summary) -> None:
    """Display session summary in rich format."""
    from datetime import datetime, timedelta

    # Header panel
    duration = timedelta(seconds=summary.total_duration_seconds)
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes = remainder // 60

    if hours > 0:
        duration_str = f"{hours}h {minutes}m"
    else:
        duration_str = f"{minutes}m"

    header = f"""📊 Session Summary
Started: {summary.started_at.strftime('%Y-%m-%d %H:%M')}
Duration: {duration_str}"""

    console.print(Panel(header, border_style="blue"))

    # Goals section
    console.print(f"\n[bold]Goals:[/bold] {summary.goals_completed} completed, {summary.goals_failed} failed")

    # Files section
    total_files = summary.files_created + summary.files_modified
    console.print(f"[bold]Files:[/bold] {summary.files_created} created, {summary.files_modified} modified")

    # Code changes
    console.print(f"[bold]Code:[/bold]  +{summary.lines_added} lines, -{summary.lines_removed} lines")

    # Top files
    if summary.top_files:
        console.print("\n[bold]Top files:[/bold]")
        for path, count in summary.top_files[:5]:
            # Truncate long paths
            display_path = path if len(path) < 40 else "..." + path[-37:]
            console.print(f"  {display_path:40} ({count} edits)")

    # Learnings
    if summary.learnings_added > 0 or summary.dead_ends_recorded > 0:
        console.print(f"\n[bold]Learnings:[/bold] {summary.learnings_added} new patterns recorded")
        console.print(f"[bold]Dead ends:[/bold] {summary.dead_ends_recorded} avoided")

    # Timeline
    if summary.goals:
        console.print("\n[bold]Timeline:[/bold]")
        for goal in summary.goals[-10:]:  # Last 10 goals
            status_icon = "✓" if goal.status == "completed" else "✗"
            time_str = goal.started_at.strftime("%H:%M")
            goal_preview = goal.goal[:40] + ("..." if len(goal.goal) > 40 else "")
            console.print(f"  {time_str}  {status_icon} {goal_preview}")


@sessions.command("history")
@click.option("--limit", "-l", default=10, help="Maximum sessions to show")
def sessions_history(limit: int) -> None:
    """List recent session summaries.

    \b
    Examples:
        sunwell sessions history
        sunwell sessions history --limit 20
    """
    from sunwell.session.tracker import SessionTracker

    recent = SessionTracker.list_recent(limit=limit)

    if not recent:
        console.print("[yellow]No session history found.[/yellow]")
        return

    table = Table(title="Recent Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Goals", style="green")
    table.add_column("Files", style="yellow")
    table.add_column("Duration", style="magenta")

    for path in recent:
        try:
            tracker = SessionTracker.load(path)
            summary = tracker.get_summary()

            duration_mins = int(summary.total_duration_seconds / 60)

            table.add_row(
                summary.session_id[:8],
                summary.started_at.strftime("%Y-%m-%d"),
                f"{summary.goals_completed}/{summary.goals_started}",
                str(summary.files_modified + summary.files_created),
                f"{duration_mins}m",
            )
        except Exception:
            continue

    console.print(table)
    console.print("\n[dim]Use 'sunwell sessions summary -s <id>' for details[/dim]")
