"""CLI commands for Multi-Instance Coordination (RFC-051).

Provides:
- sunwell workers status: View worker statuses
- sunwell workers start: Start parallel execution
- sunwell workers stop: Stop workers
- sunwell workers merge: Merge worker branches
- sunwell workers conflicts: Show branches with conflicts
- sunwell workers resources: Show resource usage
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def workers() -> None:
    """Multi-Instance Coordination — Parallel autonomous agents.

    Run multiple worker processes in parallel to speed up backlog execution.

    Examples:

        sunwell workers start --workers 4    # Start 4 workers
        sunwell workers status               # View worker statuses
        sunwell workers stop                 # Stop all workers
        sunwell workers merge                # Merge completed branches
    """
    pass


@workers.command()
@click.option("--workers", "-n", "num_workers", default=4, help="Number of workers")
@click.option("--category", help="Limit to specific categories (comma-separated)")
@click.option("--dry-run", is_flag=True, help="Show what would happen")
@click.option("--auto", is_flag=True, help="Auto-detect optimal worker count")
@click.pass_context
def start(
    ctx,
    num_workers: int,
    category: str | None,
    dry_run: bool,
    auto: bool,
) -> None:
    """Start parallel execution with multiple workers.

    Each worker operates on its own git branch, claims goals from the
    shared backlog, and commits changes atomically. At the end, all
    worker branches are merged.

    Examples:

        sunwell workers start --workers 4     # Use 4 workers
        sunwell workers start --auto          # Auto-detect optimal count
        sunwell workers start --dry-run       # Preview without executing
    """
    asyncio.run(_start_workers(num_workers, category, dry_run, auto))


async def _start_workers(
    num_workers: int,
    category: str | None,
    dry_run: bool,
    auto: bool,
) -> None:
    """Start parallel execution (stub - feature removed in Phase 2)."""
    console.print("[yellow]Parallel workers feature removed in Sunwell reboot[/yellow]")
    console.print("Use 'sunwell backlog run <goal_id>' for single-goal execution.")


@workers.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def status(ctx, json_output: bool) -> None:
    """View status of running workers."""
    asyncio.run(_show_status(json_output))


async def _show_status(json_output: bool) -> None:
    """Show worker statuses."""
    root = Path.cwd()
    workers_dir = root / ".sunwell" / "workers"

    if not workers_dir.exists():
        console.print("No workers running")
        return

    statuses = []
    for status_file in sorted(workers_dir.glob("worker-*.json")):
        try:
            data = json.loads(status_file.read_text())
            statuses.append(data)
        except (json.JSONDecodeError, ValueError):
            pass

    if not statuses:
        console.print("No workers found")
        return

    if json_output:
        console.print(json.dumps(statuses, indent=2))
        return

    table = Table(title="🔧 Worker Status")
    table.add_column("ID", style="cyan")
    table.add_column("PID", style="dim")
    table.add_column("State", style="yellow")
    table.add_column("Branch", style="green")
    table.add_column("Current Goal", style="white")
    table.add_column("Completed", justify="right")
    table.add_column("Failed", justify="right")

    for status in statuses:
        state = status.get("state", "unknown")
        state_display = {
            "starting": "🔄 Starting",
            "idle": "⏸️  Idle",
            "claiming": "🔍 Claiming",
            "executing": "⚡ Executing",
            "committing": "💾 Committing",
            "merging": "🔀 Merging",
            "stopped": "⏹️  Stopped",
            "failed": "❌ Failed",
        }.get(state, state)

        table.add_row(
            str(status.get("worker_id", "?")),
            str(status.get("pid", "?")),
            state_display,
            status.get("branch", "?")[-20:],
            (status.get("current_goal_id") or "-")[:20],
            str(status.get("goals_completed", 0)),
            str(status.get("goals_failed", 0)),
        )

    console.print(table)


@workers.command()
@click.option("--all", "stop_all", is_flag=True, help="Stop all workers")
@click.argument("worker_id", required=False, type=int)
@click.pass_context
def stop(ctx, stop_all: bool, worker_id: int | None) -> None:
    """Stop running workers.

    Examples:

        sunwell workers stop --all    # Stop all workers
        sunwell workers stop 1        # Stop worker 1
    """
    if not stop_all and worker_id is None:
        console.print("[red]Specify --all or a worker ID[/red]")
        return

    console.print("⏹️  Stopping workers...")
    console.print("[dim]Note: Workers will finish current goal before stopping[/dim]")


@workers.command()
@click.option("--branch", help="Merge specific branch")
@click.pass_context
def merge(ctx, branch: str | None) -> None:
    """Merge completed worker branches.

    Examples:

        sunwell workers merge                    # Merge all clean branches
        sunwell workers merge --branch sunwell/worker-1  # Merge specific branch
    """
    asyncio.run(_merge_branches(branch))


async def _merge_branches(branch: str | None) -> None:
    """Merge worker branches (stub - feature removed in Phase 2)."""
    console.print("[yellow]Parallel workers feature removed in Sunwell reboot[/yellow]")


@workers.command()
@click.pass_context
def conflicts(ctx) -> None:
    """Show branches with merge conflicts."""
    asyncio.run(_show_conflicts())


async def _show_conflicts() -> None:
    """Show conflict details (stub - feature removed in Phase 2)."""
    console.print("[yellow]Parallel workers feature removed in Sunwell reboot[/yellow]")


@workers.command()
@click.pass_context
def resources(ctx) -> None:
    """Show resource usage across workers."""
    asyncio.run(_show_resources())


async def _show_resources() -> None:
    """Show resource usage (stub - feature removed in Phase 2)."""
    console.print("[yellow]Parallel workers feature removed in Sunwell reboot[/yellow]")


@workers.command()
@click.argument("worker_id", type=int)
@click.pass_context
def logs(ctx, worker_id: int) -> None:
    """View logs for a specific worker.

    Example:
        sunwell workers logs 1
    """
    root = Path.cwd()
    status_file = root / ".sunwell" / "workers" / f"worker-{worker_id}.json"

    if not status_file.exists():
        console.print(f"Worker {worker_id} not found")
        return

    try:
        data = json.loads(status_file.read_text())
        console.print(f"📋 [bold]Worker {worker_id} Status:[/bold]\n")
        console.print(json.dumps(data, indent=2, default=str))
    except (json.JSONDecodeError, ValueError) as e:
        console.print(f"[red]Error reading status: {e}[/red]")


@workers.command()
@click.option("--project", "-p", type=click.Path(exists=True), default=".", help="Project path")
@click.pass_context
def ui_state(ctx, project: str) -> None:
    """Get coordinator state for UI consumption (RFC-100).

    Returns JSON suitable for the ATC view in Studio.

    Example:
        sunwell workers ui-state --json
        sunwell workers ui-state --project ~/my-project
    """
    asyncio.run(_get_ui_state(Path(project)))


async def _get_ui_state(project: Path) -> None:
    """Get UI state for coordinator (stub - feature removed in Phase 2)."""
    console.print(json.dumps({"workers": [], "status": "feature_removed"}, indent=2))


@workers.command()
@click.argument("worker_id", type=int)
@click.pass_context
def pause(ctx, worker_id: int) -> None:
    """Pause a specific worker (RFC-100).

    The worker will finish its current goal and then wait.

    Example:
        sunwell workers pause 1
    """
    root = Path.cwd()
    pause_file = root / ".sunwell" / "workers" / f"pause-{worker_id}.flag"

    pause_file.parent.mkdir(parents=True, exist_ok=True)
    pause_file.write_text(f"paused at {datetime.now().isoformat()}")

    console.print(f"⏸️  Worker {worker_id} will pause after current goal")


@workers.command()
@click.argument("worker_id", type=int)
@click.pass_context
def resume(ctx, worker_id: int) -> None:
    """Resume a paused worker (RFC-100).

    Example:
        sunwell workers resume 1
    """

    root = Path.cwd()
    pause_file = root / ".sunwell" / "workers" / f"pause-{worker_id}.flag"

    if pause_file.exists():
        pause_file.unlink()
        console.print(f"▶️  Worker {worker_id} resumed")
    else:
        console.print(f"Worker {worker_id} is not paused")
