"""Notification CLI commands for history and management.

Provides visibility into notification history:
- Recent notifications
- Filter by type or date
- Clear history

Commands:
    sunwell notifications              - Show recent notifications
    sunwell notifications --today      - Today's notifications
    sunwell notifications --type error - Filter by type
    sunwell notifications clear        - Clear history
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.interface.cli.notifications import (
    NotificationStore,
    NotificationType,
    get_notification_store,
)

console = Console()


def get_workspace() -> Path:
    """Get the current workspace path."""
    return Path.cwd()


@click.group(invoke_without_command=True)
@click.option("--limit", "-l", default=10, help="Number of notifications to show")
@click.option("--today", "-t", is_flag=True, help="Show only today's notifications")
@click.option(
    "--type", "-T", "notification_type",
    type=click.Choice(["info", "success", "warning", "error", "waiting"]),
    help="Filter by notification type",
)
@click.option("--since", "-s", type=int, help="Show notifications from last N hours")
@click.option("--undelivered", "-u", is_flag=True, help="Show only undelivered notifications")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def notifications(
    ctx: click.Context,
    limit: int,
    today: bool,
    notification_type: str | None,
    since: int | None,
    undelivered: bool,
    as_json: bool,
) -> None:
    """View notification history.

    \b
    Examples:
        sunwell notifications              # Last 10 notifications
        sunwell notifications --today      # Today's notifications
        sunwell notifications --type error # Only errors
        sunwell notifications --since 24   # Last 24 hours
        sunwell notifications --undelivered # Failed deliveries
        sunwell notifications --json       # Output as JSON
    """
    # If a subcommand is being called, don't run the default behavior
    if ctx.invoked_subcommand is not None:
        return
    
    workspace = get_workspace()
    store = get_notification_store(workspace)
    
    # Get notifications based on filters
    if undelivered:
        records = store.get_undelivered()
    elif today:
        records = store.get_today()
    elif since is not None:
        since_time = datetime.now() - timedelta(hours=since)
        records = store.get_since(since_time)
    elif notification_type is not None:
        try:
            ntype = NotificationType(notification_type)
            records = store.get_by_type(ntype, limit=limit)
        except ValueError:
            console.print(f"[red]Invalid notification type: {notification_type}[/red]")
            return
    else:
        records = store.get_recent(limit=limit)
    
    if not records:
        if as_json:
            click.echo(json.dumps([], indent=2))
        else:
            console.print("[dim]No notifications found.[/dim]")
        return
    
    if as_json:
        click.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return
    
    # Display as table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Time", style="dim", width=19)
    table.add_column("Type", width=8)
    table.add_column("Title", style="cyan")
    table.add_column("Message")
    table.add_column("✓", justify="center", width=3)
    
    type_colors = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "waiting": "magenta",
    }
    
    for record in records:
        # Format timestamp
        try:
            ts = datetime.fromisoformat(record.timestamp)
            time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            time_str = record.timestamp[:19]
        
        # Type with color
        color = type_colors.get(record.type, "white")
        type_str = f"[{color}]{record.type}[/{color}]"
        
        # Delivery status
        delivered_str = "[green]✓[/green]" if record.delivered else "[red]✗[/red]"
        
        # Truncate message if too long
        message = record.message
        if len(message) > 50:
            message = message[:47] + "..."
        
        table.add_row(time_str, type_str, record.title, message, delivered_str)
    
    console.print(f"\n[bold]Notification History[/bold] ({len(records)} shown)\n")
    console.print(table)
    
    # Show total count
    total = store.count()
    if total > len(records):
        console.print(f"\n[dim]Showing {len(records)} of {total} total notifications[/dim]")


@notifications.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def clear(force: bool) -> None:
    """Clear all notification history.

    \b
    Examples:
        sunwell notifications clear
        sunwell notifications clear --force
    """
    workspace = get_workspace()
    store = get_notification_store(workspace)
    
    count = store.count()
    
    if count == 0:
        console.print("[dim]No notifications to clear.[/dim]")
        return
    
    if not force:
        if not click.confirm(f"Clear {count} notifications?"):
            console.print("[dim]Cancelled.[/dim]")
            return
    
    store.clear()
    console.print(f"[green]✓ Cleared {count} notifications[/green]")


@notifications.command()
@click.option("--keep", "-k", default=1000, help="Number of recent entries to keep")
def prune(keep: int) -> None:
    """Prune old notifications to save space.

    Removes notifications older than 30 days and keeps only the
    most recent entries.

    \b
    Examples:
        sunwell notifications prune
        sunwell notifications prune --keep 500
    """
    workspace = get_workspace()
    store = get_notification_store(workspace)
    
    count_before = store.count()
    removed = store.prune(keep_recent=keep)
    count_after = store.count()
    
    if removed > 0:
        console.print(f"[green]✓ Pruned {removed} notifications[/green]")
        console.print(f"[dim]Before: {count_before} → After: {count_after}[/dim]")
    else:
        console.print("[dim]No notifications needed pruning.[/dim]")


@notifications.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def stats(as_json: bool) -> None:
    """Show notification statistics.

    \b
    Examples:
        sunwell notifications stats
        sunwell notifications stats --json
    """
    workspace = get_workspace()
    store = get_notification_store(workspace)
    
    records = list(store._read_all())
    
    if not records:
        if as_json:
            click.echo(json.dumps({"total": 0}, indent=2))
        else:
            console.print("[dim]No notifications found.[/dim]")
        return
    
    # Calculate stats
    total = len(records)
    delivered = sum(1 for r in records if r.delivered)
    
    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.type] = by_type.get(r.type, 0) + 1
    
    today_count = sum(
        1 for r in records
        if datetime.fromisoformat(r.timestamp).date() == datetime.now().date()
    )
    
    stats_data = {
        "total": total,
        "delivered": delivered,
        "undelivered": total - delivered,
        "delivery_rate": round(delivered / total * 100, 1) if total > 0 else 0,
        "today": today_count,
        "by_type": by_type,
    }
    
    if as_json:
        click.echo(json.dumps(stats_data, indent=2))
        return
    
    console.print("\n[bold]Notification Statistics[/bold]\n")
    console.print(f"Total:       {total}")
    console.print(f"Delivered:   {delivered} ({stats_data['delivery_rate']}%)")
    console.print(f"Undelivered: {total - delivered}")
    console.print(f"Today:       {today_count}")
    
    console.print("\n[bold]By Type:[/bold]")
    type_colors = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "waiting": "magenta",
    }
    for ntype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        color = type_colors.get(ntype, "white")
        console.print(f"  [{color}]{ntype:8}[/{color}]: {count}")
