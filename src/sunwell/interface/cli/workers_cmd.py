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
    """Start parallel execution."""
    from sunwell.backlog.manager import BacklogManager
    from sunwell.parallel import (
        Coordinator,
        GoalDependencyGraph,
        MultiInstanceConfig,
        ResourceGovernor,
        ResourceLimits,
    )

    root = Path.cwd()

    # Auto-detect worker count if requested
    if auto:
        governor = ResourceGovernor(ResourceLimits(), root)
        num_workers = governor.get_recommended_workers()
        console.print(f"[cyan]Auto-detected: {num_workers} workers recommended[/cyan]")

    console.print(f"\n🚀 [bold]Starting parallel execution with {num_workers} workers[/bold]\n")

    # Refresh backlog
    manager = BacklogManager(root=root)
    backlog = await manager.refresh()
    goals = backlog.execution_order()

    if not goals:
        console.print("📋 No goals in backlog")
        return

    # Analyze parallelizability
    graph = GoalDependencyGraph.from_backlog(backlog)
    completed_set = backlog.completed

    parallelizable_groups = graph.get_parallelizable_groups(
        [g.id for g in goals if g.id not in completed_set],
        completed_set,
    )

    total_goals = len([g for g in goals if g.id not in completed_set])
    parallel_count = sum(len(g) for g in parallelizable_groups if len(g) > 1)

    parallel_pct = 100 * parallel_count // max(1, total_goals)
    console.print("📊 [bold]Backlog Analysis:[/bold]")
    console.print(f"   Total goals: {total_goals}")
    console.print(f"   Parallelizable: {parallel_count} ({parallel_pct}%)")
    console.print(f"   Sequential (conflicts): {total_goals - parallel_count}")
    console.print()

    if dry_run:
        console.print("[yellow]Dry run - no changes will be made[/yellow]\n")

        table = Table(title="Parallel Execution Plan")
        table.add_column("Wave", style="cyan")
        table.add_column("Goals", style="white")
        table.add_column("Workers", style="green")

        for i, group in enumerate(parallelizable_groups[:10], 1):
            goal_titles = [backlog.goals[gid].title[:30] for gid in group[:3]]
            if len(group) > 3:
                goal_titles.append(f"... +{len(group) - 3} more")
            table.add_row(
                str(i),
                "\n".join(goal_titles),
                str(min(len(group), num_workers)),
            )

        console.print(table)

        # Estimate time savings
        serial_time = total_goals * 5  # 5 min per goal estimate
        parallel_time = len(parallelizable_groups) * 5  # each wave runs in parallel
        speedup = serial_time / max(1, parallel_time)

        console.print("\n⏱️  [bold]Estimated time:[/bold]")
        console.print(f"   Serial: ~{serial_time} minutes")
        console.print(f"   Parallel: ~{parallel_time} minutes")
        console.print(f"   Speedup: {speedup:.1f}×")
        return

    # Create coordinator and run
    config = MultiInstanceConfig(num_workers=num_workers)
    coordinator = Coordinator(root=root, config=config)

    console.print("🔧 [bold]Workers:[/bold]")
    for i in range(1, num_workers + 1):
        console.print(f"   Worker {i}: starting → sunwell/worker-{i}")
    console.print()

    console.print("─" * 60)
    console.print()

    result = await coordinator.execute()

    console.print()
    console.print("─" * 60)
    console.print()

    # Show results
    if result.errors:
        console.print("[red]❌ Errors occurred:[/red]")
        for error in result.errors:
            console.print(f"   {error}")
        return

    completed_msg = f"{result.completed}/{result.total_goals} goals completed"
    console.print(f"📈 [bold]Progress:[/bold] {completed_msg}")
    console.print()

    if result.merged_branches:
        console.print("🔀 [bold]Merged branches:[/bold]")
        for branch in result.merged_branches:
            console.print(f"   ✅ {branch}")

    if result.conflict_branches:
        console.print("\n⚠️  [bold]Branches with conflicts:[/bold]")
        for branch in result.conflict_branches:
            console.print(f"   ❌ {branch}")
        console.print("\n   Run 'sunwell workers conflicts' to see details")

    console.print()
    console.print("🎉 [bold]Parallel execution complete![/bold]")
    console.print()
    console.print(f"   Duration: {result.duration_seconds / 60:.1f} minutes")
    console.print(f"   Goals completed: {result.completed}")
    console.print(f"   Goals failed: {result.failed}")
    console.print(f"   Branches merged: {len(result.merged_branches)}")
    console.print(f"   Conflicts: {len(result.conflict_branches)}")
    console.print()
    console.print("Run `git log --oneline -20` to see changes.")


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
    """Merge worker branches."""
    from sunwell.parallel.git import (
        checkout_branch,
        get_current_branch,
        merge_ff_only,
        run_git,
    )

    root = Path.cwd()
    base_branch = await get_current_branch(root)

    # Find worker branches
    result = await run_git(root, ["branch", "--list", "sunwell/worker-*"])
    branches = [b.strip().lstrip("* ") for b in result.strip().split("\n") if b.strip()]

    if branch:
        branches = [b for b in branches if b == branch]

    if not branches:
        console.print("No worker branches found")
        return

    console.print(f"🔀 [bold]Merging branches to {base_branch}[/bold]\n")

    merged = []
    conflicts = []

    for b in branches:
        try:
            await checkout_branch(root, base_branch)
            await merge_ff_only(root, b)
            merged.append(b)
            console.print(f"   ✅ {b}")
        except Exception as e:
            conflicts.append(b)
            console.print(f"   ❌ {b} - {e}")

    await checkout_branch(root, base_branch)

    console.print()
    console.print(f"Merged: {len(merged)}, Conflicts: {len(conflicts)}")


@workers.command()
@click.pass_context
def conflicts(ctx) -> None:
    """Show branches with merge conflicts."""
    asyncio.run(_show_conflicts())


async def _show_conflicts() -> None:
    """Show conflict details."""
    from sunwell.parallel.git import run_git

    root = Path.cwd()

    # Find worker branches
    result = await run_git(root, ["branch", "--list", "sunwell/worker-*"])
    branches = [b.strip().lstrip("* ") for b in result.strip().split("\n") if b.strip()]

    if not branches:
        console.print("No worker branches found")
        return

    console.print("⚠️  [bold]Worker Branches:[/bold]\n")

    for branch in branches:
        # Get commit count
        try:
            count_result = await run_git(root, ["rev-list", "--count", f"HEAD..{branch}"])
            commit_count = count_result.strip()
        except Exception:
            commit_count = "?"

        console.print(f"   {branch}: {commit_count} commits ahead")

    console.print("\nTo resolve conflicts manually:")
    console.print("  git checkout <branch>")
    console.print("  git rebase main")
    console.print("  # resolve conflicts")
    console.print("  git checkout main")
    console.print("  git merge --ff-only <branch>")


@workers.command()
@click.pass_context
def resources(ctx) -> None:
    """Show resource usage across workers."""
    asyncio.run(_show_resources())


async def _show_resources() -> None:
    """Show resource usage."""
    from sunwell.parallel import ResourceGovernor, ResourceLimits

    root = Path.cwd()
    governor = ResourceGovernor(ResourceLimits(), root)

    console.print("📊 [bold]Resource Usage:[/bold]\n")

    # LLM slots
    llm_count = governor._read_llm_count()
    console.print(f"   LLM slots: {llm_count}/{governor.limits.max_concurrent_llm_calls}")

    # Recommended workers
    recommended = governor.get_recommended_workers()
    console.print(f"   Recommended workers: {recommended}")

    # Memory (if psutil available)
    try:
        import psutil

        mem = psutil.virtual_memory()
        console.print(f"   Available memory: {mem.available / 1024 / 1024:.0f} MB")
        console.print(f"   CPU cores: {psutil.cpu_count()}")
    except ImportError:
        console.print("   [dim]Install psutil for detailed resource info[/dim]")


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
    """Get UI state for coordinator."""
    from sunwell.parallel import Coordinator, MultiInstanceConfig

    root = project.resolve()
    config = MultiInstanceConfig()
    coordinator = Coordinator(root=root, config=config)

    try:
        ui_state = await coordinator.get_ui_state()
        console.print(json.dumps(ui_state.to_dict(), indent=2))
    except Exception:
        # Return empty state on error
        from sunwell.parallel.types import CoordinatorUIState
        empty_state = CoordinatorUIState()
        console.print(json.dumps(empty_state.to_dict(), indent=2))


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
