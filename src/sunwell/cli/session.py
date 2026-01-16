"""Session command group - Manage conversation sessions."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.simulacrum.store import SimulacrumStore

console = Console()


@click.group()
def sessions() -> None:
    """Manage neverending conversation sessions.
    
    Sessions persist across restarts, enabling multi-day conversations
    that never lose context.
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
