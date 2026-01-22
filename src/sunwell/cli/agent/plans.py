"""Plans command for agent CLI."""


import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command(name="plans")
@click.option("--list", "-l", "list_plans", is_flag=True, help="List saved plans")
@click.option("--clean", is_flag=True, help="Clean old plans (>7 days)")
@click.option("--delete", "-d", "delete_id", help="Delete a specific plan by ID")
@click.option("--show", "-s", "show_id", help="Show details of a specific plan")
def plans_cmd(list_plans: bool, clean: bool, delete_id: str | None, show_id: str | None) -> None:
    """Manage saved execution plans (RFC-040).

    Examples:

    \b
        sunwell agent plans --list
        sunwell agent plans --show abc123
        sunwell agent plans --delete abc123
        sunwell agent plans --clean
    """
    from sunwell.naaru.persistence import PlanStore

    store = PlanStore()

    if show_id:
        execution = store.load(show_id)
        if not execution:
            console.print(f"[red]Plan not found: {show_id}[/red]")
            return

        console.print(f"[bold]Plan: {execution.goal_hash}[/bold]\n")
        console.print(f"  Goal: {execution.goal}")
        console.print(f"  Status: {execution.status.value}")
        console.print(f"  Created: {execution.created_at}")
        console.print(f"  Updated: {execution.updated_at}")
        console.print("\n[bold]Progress:[/bold]")
        console.print(f"  Artifacts: {len(execution.graph)}")
        console.print(f"  Completed: {len(execution.completed)}")
        console.print(f"  Failed: {len(execution.failed)}")
        console.print(f"  Progress: {execution.progress_percent:.0f}%")

        if execution.failed:
            console.print("\n[bold]Failed artifacts:[/bold]")
            for aid, error in list(execution.failed.items())[:5]:
                console.print(f"  ✗ {aid}: {error[:40]}...")

        console.print("\n[bold]Model distribution:[/bold]")
        for tier, count in execution.model_distribution.items():
            console.print(f"  {tier}: {count}")
        return

    if delete_id:
        if store.delete(delete_id):
            console.print(f"[green]✓[/green] Deleted plan: {delete_id}")
        else:
            console.print(f"[yellow]Plan not found: {delete_id}[/yellow]")
        return

    if clean:
        count = store.clean_old(max_age_hours=168.0)  # 7 days
        console.print(f"[green]✓[/green] Cleaned {count} old plan(s)")
        return

    # Default: list plans
    plans = store.list_recent(limit=20)
    if not plans:
        console.print("[dim]No saved plans found[/dim]")
        return

    table = Table(title="Saved Plans")
    table.add_column("ID", style="cyan")
    table.add_column("Goal")
    table.add_column("Status", style="magenta")
    table.add_column("Progress")
    table.add_column("Updated")

    for plan in plans:
        status_style = "green" if plan.is_complete else "yellow"
        progress = f"{plan.progress_percent:.0f}%"
        updated = plan.updated_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(
            plan.goal_hash[:8],
            plan.goal[:40] + ("..." if len(plan.goal) > 40 else ""),
            f"[{status_style}]{plan.status.value}[/{status_style}]",
            progress,
            updated,
        )

    console.print(table)

