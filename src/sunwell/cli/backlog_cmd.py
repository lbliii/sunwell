"""CLI commands for Autonomous Backlog (RFC-046).

Provides:
- sunwell backlog: View prioritized backlog
- sunwell backlog --execute: Execute in supervised mode
- sunwell backlog refresh: Force refresh from signals
- sunwell backlog add "goal": Add explicit goal
- sunwell backlog skip <id>: Skip a goal
- sunwell backlog block <id> "reason": Block a goal
- sunwell backlog history: View completed goals
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sunwell.backlog.goals import GoalPolicy
from sunwell.backlog.manager import BacklogManager
from sunwell.cli.helpers import create_model
from sunwell.intelligence.context import ProjectContext

console = Console()


@click.group()
def backlog() -> None:
    """Autonomous Backlog — Self-directed goal generation.

    Sunwell continuously observes project state and identifies what should
    exist but doesn't — applying artifact-first decomposition to goal selection.

    Examples:

        sunwell backlog                    # View prioritized backlog
        sunwell backlog --execute          # Execute in supervised mode
        sunwell backlog refresh            # Force refresh from signals
        sunwell backlog add "Fix auth bug" # Add explicit goal
        sunwell backlog skip 3             # Skip a goal
        sunwell backlog history            # View completed goals
    """
    pass


@backlog.command()
@click.option("--json", "json_output", is_flag=True, help="Machine-readable output")
@click.option("--mermaid", is_flag=True, help="Export dependency graph as Mermaid")
@click.pass_context
def show(ctx, json_output: bool, mermaid: bool) -> None:
    """Show prioritized backlog."""
    asyncio.run(_show_backlog(json_output, mermaid))


async def _show_backlog(json_output: bool, mermaid: bool) -> None:
    """Show backlog."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    backlog = await manager.refresh()

    if json_output:
        data = {
            "goals": [
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "priority": g.priority,
                    "category": g.category,
                    "complexity": g.estimated_complexity,
                    "auto_approvable": g.auto_approvable,
                    "requires": list(g.requires),
                }
                for g in backlog.goals.values()
            ],
            "completed": list(backlog.completed),
            "in_progress": backlog.in_progress,
            "blocked": backlog.blocked,
        }
        console.print(json.dumps(data, indent=2))
        return

    if mermaid:
        console.print(backlog.to_mermaid())
        return

    # Human-readable table
    table = Table(title="📋 Project Backlog")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="yellow")
    table.add_column("Complexity", style="green")
    table.add_column("Status", style="magenta")

    execution_order = backlog.execution_order()
    if not execution_order:
        console.print("📋 No goals in backlog")
        return

    for goal in execution_order[:20]:  # Show top 20
        status = "✓" if goal.id in backlog.completed else "⏳" if goal.id == backlog.in_progress else "□"
        if goal.id in backlog.blocked:
            status = "🚫"

        table.add_row(
            goal.id[:8],
            goal.title[:50],
            f"{goal.priority:.2f}",
            goal.category,
            goal.estimated_complexity,
            status,
        )

    console.print(table)

    if len(execution_order) > 20:
        console.print(f"\n... and {len(execution_order) - 20} more goals")


@backlog.command()
@click.option("--approve", help="Comma-separated goal IDs to pre-approve")
@click.pass_context
def execute(ctx, approve: str | None) -> None:
    """Execute backlog in supervised mode.

    Executes goals from backlog using ArtifactPlanner and AdaptiveAgent.
    Requires model and agent setup - use 'sunwell agent run' for individual goals.
    """
    console.print("⚠️  Full execution loop requires model/agent setup")
    console.print("For now, use 'sunwell backlog' to view goals")
    console.print("Then execute individual goals with 'sunwell agent run <goal>'")


@backlog.command()
@click.pass_context
def refresh(ctx) -> None:
    """Force refresh backlog from signals."""
    asyncio.run(_refresh_backlog())


async def _refresh_backlog() -> None:
    """Refresh backlog."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    console.print("🔄 Refreshing backlog from signals...")
    backlog = await manager.refresh()
    console.print(f"✅ Found {len(backlog.goals)} goals")


@backlog.command()
@click.argument("goal")
@click.pass_context
def add(ctx, goal: str) -> None:
    """Add explicit goal to backlog."""
    asyncio.run(_add_goal(goal))


async def _add_goal(goal: str) -> None:
    """Add goal."""
    root = Path.cwd()
    manager = BacklogManager(root=root)

    # Generate goal from explicit text
    goals = await manager.goal_generator.generate(
        observable_signals=[],
        intelligence_signals=[],
        explicit_goals=[goal],
    )

    if goals:
        # Add to backlog
        manager.backlog.goals[goals[0].id] = goals[0]
        manager._save()
        console.print(f"✅ Added goal: {goals[0].title}")


@backlog.command()
@click.argument("goal_id")
@click.pass_context
def skip(ctx, goal_id: str) -> None:
    """Skip a goal."""
    root = Path.cwd()
    manager = BacklogManager(root=Path.cwd())
    manager._load()

    if goal_id in manager.backlog.goals:
        asyncio.run(manager.block_goal(goal_id, "User skipped"))
        console.print(f"⏭️  Skipped goal: {goal_id}")
    else:
        console.print(f"❌ Goal not found: {goal_id}")


@backlog.command()
@click.argument("goal_id")
@click.argument("reason")
@click.pass_context
def block(ctx, goal_id: str, reason: str) -> None:
    """Block a goal with reason."""
    root = Path.cwd()
    manager = BacklogManager(root=Path.cwd())
    manager._load()

    if goal_id in manager.backlog.goals:
        asyncio.run(manager.block_goal(goal_id, reason))
        console.print(f"🚫 Blocked goal: {goal_id} - {reason}")
    else:
        console.print(f"❌ Goal not found: {goal_id}")


@backlog.command()
@click.pass_context
def history(ctx) -> None:
    """View completed goals history."""
    root = Path.cwd()
    history_path = root / ".sunwell" / "backlog" / "completed.jsonl"

    if not history_path.exists():
        console.print("No completed goals yet")
        return

    table = Table(title="📜 Completed Goals")
    table.add_column("Goal ID", style="cyan")
    table.add_column("Success", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Files Changed", style="yellow")

    with history_path.open() as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                table.add_row(
                    entry.get("goal_id", "")[:8],
                    "✓" if entry.get("success") else "✗",
                    f"{entry.get('duration_seconds', 0):.1f}s",
                    str(len(entry.get("files_changed", []))),
                )

    console.print(table)
