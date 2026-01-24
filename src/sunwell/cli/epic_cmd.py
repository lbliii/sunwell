"""CLI commands for Hierarchical Goal Decomposition (RFC-115).

Provides:
- sunwell epic status: Show epic progress
- sunwell epic milestones: List milestones for an epic
- sunwell epic skip-milestone: Skip current milestone
- sunwell epic replan: Re-plan current milestone

Examples:
    sunwell run "build an RTS game"           # Auto-detects epic, decomposes
    sunwell run --epic "write a mystery novel" # Explicit epic submission
    sunwell epic status                        # View current epic progress
    sunwell epic milestones                    # List all milestones
    sunwell epic skip-milestone                # Skip to next milestone
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn

from sunwell.backlog.manager import BacklogManager
from sunwell.backlog.tracker import MilestoneTracker

console = Console()


@click.group()
def epic() -> None:
    """Hierarchical Goal Decomposition — Epic progress management.

    Epics are ambitious goals that get decomposed into milestones.
    Each milestone is then planned with HarmonicPlanner when reached.

    Examples:

        sunwell epic status                # View current epic progress
        sunwell epic status <epic_id>      # View specific epic
        sunwell epic milestones            # List milestones for active epic
        sunwell epic skip-milestone        # Skip current milestone
        sunwell epic replan                # Re-plan current milestone
    """
    pass


@epic.command()
@click.argument("epic_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def status(ctx, epic_id: str | None, json_output: bool) -> None:
    """Show epic progress.

    If no epic_id is provided, shows the active epic's progress.
    """
    asyncio.run(_show_status(epic_id, json_output))


async def _show_status(epic_id: str | None, json_output: bool) -> None:
    """Show epic status."""
    root = Path.cwd()
    manager = BacklogManager(root=root)
    tracker = MilestoneTracker(backlog_manager=manager)

    # If no epic_id, use active epic
    if not epic_id:
        epic_id = manager.backlog.active_epic

    if not epic_id:
        if json_output:
            console.print(json.dumps({"error": "No active epic", "epics": []}))
        else:
            console.print("📋 No active epic")
            # Show available epics
            epics = [g for g in manager.backlog.goals.values() if g.goal_type == "epic"]
            if epics:
                console.print("\n[dim]Available epics:[/dim]")
                for e in epics:
                    status_icon = (
                        "✅"
                        if e.id in manager.backlog.completed
                        else "🔄"
                        if e.id == manager.backlog.active_epic
                        else "⏳"
                    )
                    console.print(f"  {status_icon} {e.id[:12]}  {e.title[:50]}")
        return

    # Get progress
    progress = tracker.get_progress(epic_id)

    if not progress:
        if json_output:
            console.print(json.dumps({"error": f"Epic not found: {epic_id}"}))
        else:
            console.print(f"❌ Epic not found: {epic_id}")
        return

    if json_output:
        console.print(json.dumps(progress.to_dict(), indent=2))
        return

    # Human-readable display
    console.print()
    console.print(
        Panel(
            f"[bold]🎯 {progress.epic_title}[/bold]\n"
            f"[dim]ID: {progress.epic_id}[/dim]",
            expand=False,
        )
    )

    # Progress bar
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        console=console,
        transient=False,
    ) as progress_bar:
        progress_bar.add_task(
            "Milestones",
            total=progress.total_milestones,
            completed=progress.completed_milestones,
        )

    # Current milestone
    if progress.current_milestone_id:
        console.print()
        console.print(
            f"[cyan]Current:[/cyan] {progress.current_milestone_title}"
        )
        if progress.current_milestone_tasks_total > 0:
            task_pct = (
                progress.current_milestone_tasks_completed
                / progress.current_milestone_tasks_total
                * 100
            )
            console.print(
                f"  Tasks: {progress.current_milestone_tasks_completed}/{progress.current_milestone_tasks_total} ({task_pct:.0f}%)"
            )
    else:
        console.print("\n[green]✅ Epic completed![/green]")

    console.print()


@epic.command()
@click.argument("epic_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def milestones(ctx, epic_id: str | None, json_output: bool) -> None:
    """List milestones for an epic."""
    asyncio.run(_show_milestones(epic_id, json_output))


async def _show_milestones(epic_id: str | None, json_output: bool) -> None:
    """Show milestones for an epic."""
    root = Path.cwd()
    manager = BacklogManager(root=root)
    tracker = MilestoneTracker(backlog_manager=manager)

    # If no epic_id, use active epic
    if not epic_id:
        epic_id = manager.backlog.active_epic

    if not epic_id:
        if json_output:
            console.print(json.dumps({"error": "No active epic"}))
        else:
            console.print("❌ No active epic. Provide an epic_id or run an epic first.")
        return

    # Get timeline
    timeline = tracker.get_milestone_timeline(epic_id)

    if not timeline:
        if json_output:
            console.print(json.dumps({"error": f"No milestones found for: {epic_id}"}))
        else:
            console.print(f"❌ No milestones found for: {epic_id}")
        return

    if json_output:
        console.print(json.dumps({"milestones": timeline}, indent=2))
        return

    # Human-readable table
    epic = manager.backlog.get_epic(epic_id)
    epic_title = epic.title if epic else epic_id

    console.print()
    console.print(f"[bold]🎯 {epic_title}[/bold]")
    console.print()

    for m in timeline:
        # Status icon
        status_icons = {
            "completed": "✅",
            "active": "🔄",
            "blocked": "⏭",
            "pending": "⏳",
        }
        icon = status_icons.get(m["status"], "⏳")

        # Progress indicator for active milestone
        task_progress = ""
        if m["status"] == "active" and m["tasks_total"] > 0:
            task_progress = f" [{m['tasks_completed']}/{m['tasks_total']}]"

        # Style based on status
        title_style = {
            "completed": "dim strike",
            "active": "cyan bold",
            "blocked": "dim",
            "pending": "white",
        }.get(m["status"], "white")

        # Index
        idx = m.get("index", 0)
        console.print(f"  {icon} [dim]M{idx + 1}[/dim] [{title_style}]{m['title']}[/{title_style}]{task_progress}")

        # Produces (artifacts)
        if m["produces"]:
            produces_str = ", ".join(m["produces"][:4])
            if len(m["produces"]) > 4:
                produces_str += f" +{len(m['produces']) - 4} more"
            console.print(f"     [dim]→ {produces_str}[/dim]")

    console.print()


@epic.command(name="skip-milestone")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def skip_milestone(ctx, json_output: bool) -> None:
    """Skip the current milestone and advance to next."""
    asyncio.run(_skip_milestone(json_output))


async def _skip_milestone(json_output: bool) -> None:
    """Skip current milestone."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    if not manager.backlog.active_milestone:
        if json_output:
            console.print(json.dumps({"error": "No active milestone to skip"}))
        else:
            console.print("❌ No active milestone to skip")
        return

    current = manager.backlog.get_current_milestone()
    next_milestone = await manager.skip_milestone()

    if json_output:
        console.print(
            json.dumps(
                {
                    "skipped": current.id if current else None,
                    "next": next_milestone.id if next_milestone else None,
                }
            )
        )
        return

    if current:
        console.print(f"⏭ Skipped: {current.title}")

    if next_milestone:
        console.print(f"▶ Next: {next_milestone.title}")
    else:
        console.print("[green]✅ Epic complete (no more milestones)[/green]")


@epic.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def replan(ctx, json_output: bool) -> None:
    """Re-plan the current milestone.

    Useful when:
    - Scope has changed
    - Previous plan encountered unexpected issues
    - Need to adjust approach based on learnings
    """
    asyncio.run(_replan_milestone(json_output))


async def _replan_milestone(json_output: bool) -> None:
    """Re-plan current milestone."""
    root = Path.cwd()
    manager = BacklogManager(root=root)
    tracker = MilestoneTracker(backlog_manager=manager)

    if not manager.backlog.active_milestone:
        if json_output:
            console.print(json.dumps({"error": "No active milestone to replan"}))
        else:
            console.print("❌ No active milestone to replan")
        return

    milestone = manager.backlog.get_current_milestone()
    if not milestone:
        if json_output:
            console.print(json.dumps({"error": "Could not find active milestone"}))
        else:
            console.print("❌ Could not find active milestone")
        return

    # Get context for replanning
    epic_id = milestone.parent_goal_id
    if not epic_id:
        if json_output:
            console.print(json.dumps({"error": "Milestone has no parent epic"}))
        else:
            console.print("❌ Milestone has no parent epic")
        return

    context = tracker.get_context_for_next(epic_id)

    if json_output:
        console.print(
            json.dumps(
                {
                    "milestone_id": milestone.id,
                    "milestone_title": milestone.title,
                    "replan_context": context,
                    "status": "ready_for_replan",
                }
            )
        )
        return

    console.print(f"🔄 Re-planning milestone: {milestone.title}")
    console.print()
    console.print("[dim]Context built from:[/dim]")
    console.print(f"  • {len(context.get('completed_milestones', []))} completed milestones")
    console.print(f"  • {len(context.get('completed_artifacts', []))} artifacts available")
    console.print(f"  • {len(context.get('learnings', []))} learnings extracted")
    console.print()
    console.print("[yellow]Run `sunwell run` to execute the replanned milestone[/yellow]")


@epic.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.pass_context
def list_epics(ctx, json_output: bool) -> None:
    """List all epics in the backlog."""
    asyncio.run(_list_epics(json_output))


async def _list_epics(json_output: bool) -> None:
    """List all epics."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    epics = [g for g in manager.backlog.goals.values() if g.goal_type == "epic"]

    if json_output:
        data = [
            {
                "id": e.id,
                "title": e.title,
                "description": e.description,
                "completed": e.id in manager.backlog.completed,
                "active": e.id == manager.backlog.active_epic,
            }
            for e in epics
        ]
        console.print(json.dumps({"epics": data}, indent=2))
        return

    if not epics:
        console.print("📋 No epics in backlog")
        console.print()
        console.print("[dim]Submit an ambitious goal to create an epic:[/dim]")
        console.print('  sunwell run "build an RTS game"')
        return

    table = Table(title="🎯 Epics")
    table.add_column("Status", width=3)
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")

    for e in epics:
        if e.id in manager.backlog.completed:
            status = "✅"
        elif e.id == manager.backlog.active_epic:
            status = "🔄"
        else:
            status = "⏳"

        table.add_row(
            status,
            e.id[:12],
            e.title[:60],
        )

    console.print(table)
