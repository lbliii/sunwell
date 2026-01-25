"""Status command for agent CLI."""


from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command()
def status() -> None:
    """Show agent status and available checkpoints."""
    from sunwell.naaru.checkpoint import find_latest_checkpoint
    from sunwell.naaru.persistence import PlanStore

    checkpoint_dir = Path.cwd() / ".sunwell" / "checkpoints"
    store = PlanStore()

    console.print("[bold]Agent Status[/bold]\n")

    # Check for saved plans (RFC-040)
    plans = store.list_recent(limit=5)
    if plans:
        console.print(f"[green]✓[/green] Found {len(plans)} saved plan(s)")
        console.print("\n[bold]Recent plans:[/bold]")
        for plan in plans[:3]:
            status_icon = "✓" if plan.is_complete else "◐"
            console.print(f"  [{status_icon}] {plan.goal[:50]}...")
            console.print(f"      ID: {plan.goal_hash} | Progress: {plan.progress_percent:.0f}%")
    else:
        console.print("[dim]No saved plans found[/dim]")

    # Check for checkpoints
    if checkpoint_dir.exists():
        checkpoint_files = list(checkpoint_dir.glob("agent-*.json"))

        if checkpoint_files:
            console.print(f"\n[green]✓[/green] Found {len(checkpoint_files)} checkpoint(s)")

            # Show latest
            latest = find_latest_checkpoint(checkpoint_dir)
            if latest:
                summary = latest.get_progress_summary()
                console.print("\n[bold]Latest checkpoint:[/bold]")
                console.print(f"  Goal: {summary['goal'][:60]}...")
                console.print(f"  Progress: {summary['completed']}/{summary['total_tasks']} tasks")
                console.print(f"  Created: {summary['checkpoint_at']}")
        else:
            console.print("\n[dim]No task checkpoints found[/dim]")
    else:
        console.print("\n[dim]No checkpoint directory found[/dim]")

    # Check for models
    console.print("\n[bold]Model Status:[/bold]")
    try:
        from sunwell.models.ollama import OllamaModel
        _ = OllamaModel(model="gemma3:1b")  # noqa: F841
        console.print("  [green]✓[/green] Ollama available")
    except Exception:
        console.print("  [red]✗[/red] Ollama not available")

