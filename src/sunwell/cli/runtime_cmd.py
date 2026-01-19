"""Runtime information command."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.core.freethreading import runtime_info

console = Console()


@click.command()
def runtime() -> None:
    """Show runtime information and parallelism status.

    Displays Python version, free-threading status, and optimal worker counts.
    Use this to verify Sunwell is running with optimal settings.
    """
    info = runtime_info()

    # Status indicator
    if info["free_threaded"]:
        status = "[green]✅ FREE-THREADED[/green]"
        detail = "True parallelism enabled - optimal performance"
    else:
        status = "[yellow]⚠️  GIL ENABLED[/yellow]"
        detail = "Limited parallelism - consider using Python 3.14t"

    console.print(Panel.fit(
        f"[bold]Sunwell Runtime[/bold]\n\n"
        f"Python: {info['python_version']}\n"
        f"Status: {status}\n"
        f"CPUs:   {info['cpu_count']} cores\n\n"
        f"[dim]{detail}[/dim]",
        title="🔧 Runtime Info",
    ))

    # Worker table
    table = Table(title="Adaptive Worker Counts")
    table.add_column("Workload Type", style="cyan")
    table.add_column("Workers", justify="right")
    table.add_column("Reason", style="dim")

    for workload, count in info["optimal_workers"].items():
        if workload == "io_bound":
            reason = "Threads wait on I/O"
        elif workload == "cpu_bound":
            if info["free_threaded"]:
                reason = "True parallelism"
            else:
                reason = "GIL serializes - minimal benefit"
        else:
            reason = "Balanced for mixed workloads"

        table.add_row(workload.replace("_", "-"), str(count), reason)

    console.print(table)

    # Recommendation
    if not info["free_threaded"]:
        console.print()
        console.print("[bold]Recommendation:[/bold]")
        console.print("  Use Python 3.14t for 5-10x speedup on CPU-bound tasks:")
        console.print("  [cyan]/usr/local/bin/python3.14t -m sunwell chat[/cyan]")
