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
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from sunwell.features.backlog.manager import BacklogManager
from sunwell.features.backlog.tracker import MilestoneTracker
from sunwell.foundation.utils import safe_json_dumps
from sunwell.interface.cli.core.theme import create_sunwell_console

console = create_sunwell_console()


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
            console.print(safe_json_dumps({"error": "No active epic", "epics": []}))
        else:
            console.print("[neutral.dim]≡ No active epic[/neutral.dim]")
            # Show available epics
            epics = [g for g in manager.backlog.goals.values() if g.goal_type == "epic"]
            if epics:
                console.print("\n[neutral.dim]Available epics:[/neutral.dim]")
                for e in epics:
                    if e.id in manager.backlog.completed:
                        status_icon = "[holy.success]★[/]"
                    elif e.id == manager.backlog.active_epic:
                        status_icon = "[holy.radiant]◎[/]"
                    else:
                        status_icon = "[neutral.dim]◇[/]"
                    console.print(f"  {status_icon} {e.id[:12]}  {e.title[:50]}")
        return

    # Get progress
    progress = tracker.get_progress(epic_id)

    if not progress:
        if json_output:
            console.print(safe_json_dumps({"error": f"Epic not found: {epic_id}"}))
        else:
            console.print(f"[void.purple]✗ Epic not found: {epic_id}[/void.purple]")
        return

    if json_output:
        console.print(safe_json_dumps(progress.to_dict(), indent=2))
        return

    # Human-readable display (RFC-131: Holy Light)
    console.print()
    console.print(
        Panel(
            f"[sunwell.heading]◆ {progress.epic_title}[/sunwell.heading]\n"
            f"[neutral.dim]ID: {progress.epic_id}[/neutral.dim]",
            expand=False,
            border_style="holy.gold",
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
            f"[holy.radiant]Current:[/] {progress.current_milestone_title}"
        )
        if progress.current_milestone_tasks_total > 0:
            task_pct = (
                progress.current_milestone_tasks_completed
                / progress.current_milestone_tasks_total
                * 100
            )
            done = progress.current_milestone_tasks_completed
            total = progress.current_milestone_tasks_total
            console.print(f"  Tasks: {done}/{total} ({task_pct:.0f}%)")
    else:
        console.print("\n[holy.success]★ Epic completed![/holy.success]")

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
            console.print(safe_json_dumps({"error": "No active epic"}))
        else:
            console.print("[void.purple]✗ No active epic.[/void.purple]")
            console.print("[neutral.dim]Provide epic_id or run epic first.[/neutral.dim]")
        return

    # Get timeline
    timeline = tracker.get_milestone_timeline(epic_id)

    if not timeline:
        if json_output:
            console.print(safe_json_dumps({"error": f"No milestones found for: {epic_id}"}))
        else:
            console.print(f"[void.purple]✗ No milestones for: {epic_id}[/void.purple]")
        return

    if json_output:
        console.print(safe_json_dumps({"milestones": timeline}, indent=2))
        return

    # Human-readable table
    epic = manager.backlog.get_epic(epic_id)
    epic_title = epic.title if epic else epic_id

    console.print()
    console.print(f"[sunwell.heading]◆ {epic_title}[/sunwell.heading]")
    console.print()

    for m in timeline:
        # Status icon (RFC-131: Holy Light)
        status_icons = {
            "completed": "[holy.success]★[/]",
            "active": "[holy.radiant]◎[/]",
            "blocked": "[holy.gold]△[/]",
            "pending": "[neutral.dim]◇[/]",
        }
        icon = status_icons.get(m["status"], "[neutral.dim]◇[/]")

        # Progress indicator for active milestone
        task_progress = ""
        if m["status"] == "active" and m["tasks_total"] > 0:
            task_progress = f" [{m['tasks_completed']}/{m['tasks_total']}]"

        # Style based on status
        title_style = {
            "completed": "neutral.dim strike",
            "active": "holy.radiant bold",
            "blocked": "neutral.dim",
            "pending": "white",
        }.get(m["status"], "white")

        # Index
        idx = m.get("index", 0)
        title = m["title"]
        console.print(f"  {icon} [dim]M{idx + 1}[/] [{title_style}]{title}[/]{task_progress}")

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
            console.print(safe_json_dumps({"error": "No active milestone to skip"}))
        else:
            console.print("[void.purple]✗ No active milestone to skip[/void.purple]")
        return

    current = manager.backlog.get_current_milestone()
    next_milestone = await manager.skip_milestone()

    if json_output:
        console.print(
            safe_json_dumps(
                {
                    "skipped": current.id if current else None,
                    "next": next_milestone.id if next_milestone else None,
                }
            )
        )
        return

    if current:
        console.print(f"[neutral.dim]◇ Skipped: {current.title}[/neutral.dim]")

    if next_milestone:
        console.print(f"[holy.radiant]◆ Next: {next_milestone.title}[/holy.radiant]")
    else:
        console.print("[holy.success]★ Epic complete (no more milestones)[/holy.success]")


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
            console.print(safe_json_dumps({"error": "No active milestone to replan"}))
        else:
            console.print("[void.purple]✗ No active milestone to replan[/void.purple]")
        return

    milestone = manager.backlog.get_current_milestone()
    if not milestone:
        if json_output:
            console.print(safe_json_dumps({"error": "Could not find active milestone"}))
        else:
            console.print("[void.purple]✗ Could not find active milestone[/void.purple]")
        return

    # Get context for replanning
    epic_id = milestone.parent_goal_id
    if not epic_id:
        if json_output:
            console.print(safe_json_dumps({"error": "Milestone has no parent epic"}))
        else:
            console.print("[void.purple]✗ Milestone has no parent epic[/void.purple]")
        return

    context = tracker.get_context_for_next(epic_id)

    if json_output:
        console.print(
            safe_json_dumps(
                {
                    "milestone_id": milestone.id,
                    "milestone_title": milestone.title,
                    "replan_context": context,
                    "status": "ready_for_replan",
                }
            )
        )
        return

    console.print(f"[holy.radiant]↻ Re-planning milestone: {milestone.title}[/holy.radiant]")
    console.print()
    console.print("[neutral.dim]Context built from:[/neutral.dim]")
    console.print(f"  · {len(context.get('completed_milestones', []))} completed milestones")
    console.print(f"  · {len(context.get('completed_artifacts', []))} artifacts available")
    console.print(f"  · {len(context.get('learnings', []))} learnings extracted")
    console.print()
    console.print("[holy.gold]Run `sunwell run` to execute replanned milestone[/holy.gold]")


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
        console.print(safe_json_dumps({"epics": data}, indent=2))
        return

    if not epics:
        console.print("[neutral.dim]≡ No epics in backlog[/neutral.dim]")
        console.print()
        console.print("[neutral.dim]Submit an ambitious goal to create an epic:[/neutral.dim]")
        console.print('  sunwell run "build an RTS game"')
        return

    table = Table(title="◆ Epics")
    table.add_column("Status", width=3)
    table.add_column("ID", style="holy.radiant")
    table.add_column("Title")

    for e in epics:
        if e.id in manager.backlog.completed:
            status = "[holy.success]★[/]"
        elif e.id == manager.backlog.active_epic:
            status = "[holy.radiant]◎[/]"
        else:
            status = "[neutral.dim]◇[/]"

        table.add_row(
            status,
            e.id[:12],
            e.title[:60],
        )

    console.print(table)
