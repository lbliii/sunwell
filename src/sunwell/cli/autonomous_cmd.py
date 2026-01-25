"""Autonomous CLI commands for RFC-130.

Commands for fully autonomous multi-agent workflows.
"""

import asyncio
from pathlib import Path

import click
from rich.panel import Panel

from sunwell.cli.theme import create_sunwell_console

console = create_sunwell_console()


@click.group()
def autonomous():
    """Run fully autonomous multi-agent workflows (RFC-130)."""
    pass


@autonomous.command()
@click.argument("goal")
@click.option(
    "--max-hours", "-t",
    default=4.0,
    type=float,
    help="Maximum duration in hours (default: 4)",
)
@click.option(
    "--trust-level",
    type=click.Choice(["conservative", "guarded", "supervised", "full"]),
    default="supervised",
    help="Trust level for guardrails (default: supervised)",
)
@click.option(
    "--no-spawn",
    is_flag=True,
    help="Disable specialist spawning",
)
@click.option(
    "--no-memory",
    is_flag=True,
    help="Disable memory-informed prefetch",
)
@click.option(
    "--no-guard-learning",
    is_flag=True,
    help="Disable adaptive guard learning",
)
@click.option(
    "--checkpoint-interval",
    default=15.0,
    type=float,
    help="Checkpoint interval in minutes (default: 15)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def run(
    goal: str,
    max_hours: float,
    trust_level: str,
    no_spawn: bool,
    no_memory: bool,
    no_guard_learning: bool,
    checkpoint_interval: float,
    verbose: bool,
) -> None:
    """Run a goal autonomously.

    Combines all RFC-130 features:
    - Dynamic specialist spawning
    - Semantic checkpoints
    - Adaptive guards
    - Memory-informed prefetch

    Examples:

    \b
        sunwell autonomous run "Add user authentication"
        sunwell autonomous run "Refactor auth module" --max-hours 2
        sunwell autonomous run "Fix CI failures" --trust-level full
        sunwell autonomous run "Implement API" --no-spawn --verbose
    """
    asyncio.run(_run_autonomous(
        goal=goal,
        max_hours=max_hours,
        trust_level=trust_level,
        enable_spawn=not no_spawn,
        enable_memory=not no_memory,
        enable_guard_learning=not no_guard_learning,
        checkpoint_interval=checkpoint_interval,
        verbose=verbose,
    ))


async def _run_autonomous(
    goal: str,
    max_hours: float,
    trust_level: str,
    enable_spawn: bool,
    enable_memory: bool,
    enable_guard_learning: bool,
    checkpoint_interval: float,
    verbose: bool,
) -> None:
    """Run autonomous workflow."""
    from sunwell.autonomous import AutonomousConfig, autonomous_goal

    config = AutonomousConfig(
        max_duration_hours=max_hours,
        checkpoint_interval_minutes=checkpoint_interval,
        enable_spawning=enable_spawn,
        enable_memory_prefetch=enable_memory,
        enable_guard_learning=enable_guard_learning,
        trust_level=trust_level,
    )

    workspace = Path.cwd()

    # Display header (RFC-131: Holy Light styling)
    spawn_status = "on" if enable_spawn else "off"
    mem_status = "on" if enable_memory else "off"
    guard_status = "on" if enable_guard_learning else "off"
    console.print(Panel.fit(
        f"[holy.radiant]✦ Autonomous Execution[/holy.radiant]\n\n"
        f"[sunwell.heading]Goal:[/] {goal}\n"
        f"[sunwell.heading]Duration:[/] {max_hours}h | [sunwell.heading]Trust:[/] {trust_level}\n"
        f"[sunwell.heading]Spawn:[/] {spawn_status} | "
        f"[sunwell.heading]Memory:[/] {mem_status} | "
        f"[sunwell.heading]Guards:[/] {guard_status}",
        title="RFC-130 Agent Constellation",
    ))

    console.print()

    # Track stats
    stats = {
        "specialists": 0,
        "checkpoints": 0,
        "tasks": 0,
        "learnings": 0,
    }

    try:
        async for event in autonomous_goal(goal, workspace, config):
            _handle_event(event, verbose, stats)

    except KeyboardInterrupt:
        console.print("\n[holy.gold]△ Interrupted - checkpoint saved[/holy.gold]")

    except Exception as e:
        console.print(f"\n[void.purple]✗ Error: {e}[/void.purple]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())

    # Summary (RFC-131: Holy Light styling)
    console.print("\n" + "═" * 50)
    console.print("[holy.radiant]≡ Execution Summary[/holy.radiant]\n")
    console.print(f"  Specialists spawned: {stats['specialists']}")
    console.print(f"  Checkpoints saved: {stats['checkpoints']}")
    console.print(f"  Tasks completed: {stats['tasks']}")
    console.print(f"  Learnings extracted: {stats['learnings']}")


def _handle_event(event, verbose: bool, stats: dict) -> None:
    """Handle an event from autonomous execution (RFC-131: Holy Light styling)."""
    from sunwell.agent.events import EventType

    match event.type:
        case EventType.SESSION_START:
            if event.data.get("auto_resume"):
                console.print("[holy.success]◆ Resuming from checkpoint[/holy.success]")
            else:
                console.print("[holy.success]● Session started[/holy.success]")

        case EventType.SPECIALIST_SPAWNED:
            stats["specialists"] += 1
            console.print(
                f"[holy.radiant]↻ Spawned specialist:[/holy.radiant] {event.data['role']} - "
                f"{event.data['focus'][:50]}..."
            )

        case EventType.SPECIALIST_COMPLETED:
            status = "✓" if event.data["success"] else "✗"
            console.print(
                f"[neutral.dim]   {status} Specialist complete:[/neutral.dim] "
                f"{event.data['summary'][:40]}"
            )

        case EventType.CHECKPOINT_SAVED:
            stats["checkpoints"] += 1
            console.print(
                f"[holy.gold.dim]▤ Checkpoint:[/holy.gold.dim] {event.data['phase']} - "
                f"{event.data.get('tasks_completed', 0)} tasks"
            )

        case EventType.CHECKPOINT_FOUND:
            console.print(
                f"[holy.gold]◆ Found checkpoint:[/holy.gold] {event.data['phase']} "
                f"from {event.data['checkpoint_at'][:10]}"
            )

        case EventType.TASK_START:
            if verbose:
                console.print(f"[neutral.dim]◆ Task:[/neutral.dim] {event.data['task_id']}")

        case EventType.TASK_COMPLETE:
            stats["tasks"] += 1
            if verbose:
                ms = event.data["duration_ms"]
                console.print(f"[neutral.dim]  ✓ Done ({ms}ms)[/neutral.dim]")

        case EventType.MEMORY_LEARNING:
            stats["learnings"] += 1
            if verbose:
                fact = event.data.get("fact", "")[:40]
                console.print(f"[neutral.dim]✧ Learning:[/neutral.dim] {fact}")

        case EventType.AUTONOMOUS_ACTION_BLOCKED:
            console.print(
                f"[holy.gold]⊗ Guard blocked:[/holy.gold] {event.data['action_type']} - "
                f"{event.data['reason'][:40]}"
            )

        case EventType.GUARD_EVOLUTION_SUGGESTED:
            console.print(
                f"[void.purple]≡ Guard evolution:[/void.purple] {event.data['evolution_type']} "
                f"({event.data['confidence']:.0%})"
            )

        case EventType.TIMEOUT:
            console.print(
                f"[holy.gold]◔ Timeout:[/holy.gold] Max duration reached "
                f"({event.data['duration_hours']}h)"
            )

        case EventType.COMPLETE:
            tasks = event.data["tasks_completed"]
            learns = event.data.get("learnings", 0)
            console.print(f"\n[holy.success]★ Complete:[/] {tasks} tasks, {learns} learnings")

        case EventType.ERROR:
            msg = event.data.get("message", "Unknown")
            console.print(f"[void.purple]✗ Error:[/void.purple] {msg}")

        case _:
            if verbose:
                console.print(f"[neutral.dim]{event.type.value}[/neutral.dim]")


@autonomous.command()
@click.argument("goal")
@click.option(
    "--phase",
    type=click.Choice([
        "orient_complete",
        "exploration_complete",
        "plan_complete",
        "design_approved",
        "implementation_complete",
        "review_complete",
    ]),
    default=None,
    help="Resume from specific phase",
)
def resume(goal: str, phase: str | None) -> None:
    """Resume an interrupted autonomous workflow.

    Examples:

    \b
        sunwell autonomous resume "Add user authentication"
        sunwell autonomous resume "Fix tests" --phase implementation_complete
    """
    asyncio.run(_resume_autonomous(goal, phase))


async def _resume_autonomous(goal: str, phase: str | None) -> None:
    """Resume autonomous workflow."""
    from sunwell.autonomous import AutonomousConfig, autonomous_goal
    from sunwell.naaru.checkpoint import AgentCheckpoint, CheckpointPhase

    workspace = Path.cwd()

    # Find checkpoint
    checkpoint = AgentCheckpoint.find_latest_for_goal(workspace, goal)

    if not checkpoint:
        console.print(f"[void.purple]✗ No checkpoint found for goal: {goal}[/void.purple]")
        return

    # If phase specified, find specific checkpoint
    if phase:
        all_checkpoints = AgentCheckpoint.find_all_for_goal(workspace, goal)
        target_phase = CheckpointPhase(phase)
        phase_checkpoints = [c for c in all_checkpoints if c.phase == target_phase]
        if phase_checkpoints:
            checkpoint = phase_checkpoints[0]
        else:
            console.print(f"[void.purple]✗ No checkpoint at phase: {phase}[/void.purple]")
            available = {c.phase.value for c in all_checkpoints}
            console.print(f"[neutral.dim]Available: {', '.join(sorted(available))}[/neutral.dim]")
            return

    # Show checkpoint info (RFC-131: Holy Light styling)
    console.print(Panel.fit(
        f"[holy.radiant]◆ Resuming from Checkpoint[/holy.radiant]\n\n"
        f"[sunwell.heading]Goal:[/sunwell.heading] {checkpoint.goal}\n"
        f"[sunwell.heading]Phase:[/sunwell.heading] {checkpoint.phase.value}\n"
        f"[sunwell.heading]Summary:[/sunwell.heading] {checkpoint.phase_summary or 'N/A'}\n"
        f"[sunwell.heading]Saved:[/sunwell.heading] {checkpoint.checkpoint_at.isoformat()[:19]}",
        title="RFC-130 Resume",
    ))

    if not click.confirm("\nResume from this checkpoint?"):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    # Resume with auto_resume
    config = AutonomousConfig(auto_resume=True)

    stats = {"specialists": 0, "checkpoints": 0, "tasks": 0, "learnings": 0}

    async for event in autonomous_goal(goal, workspace, config):
        _handle_event(event, verbose=False, stats=stats)


@autonomous.command()
def status() -> None:
    """Show status of autonomous sessions.

    Lists recent checkpoints and session statistics.
    """

    workspace = Path.cwd()
    checkpoint_dir = workspace / ".sunwell" / "checkpoints"

    if not checkpoint_dir.exists():
        console.print("[holy.gold]◇ No autonomous sessions found.[/holy.gold]")
        return

    # Find all checkpoints
    checkpoint_files = list(checkpoint_dir.glob("*.json"))

    if not checkpoint_files:
        console.print("[holy.gold]◇ No checkpoints found.[/holy.gold]")
        return

    console.print("\n[holy.radiant]≡ Autonomous Sessions[/holy.radiant]\n")

    # Group by goal
    from collections import defaultdict

    from sunwell.naaru.checkpoint import AgentCheckpoint

    by_goal: dict[str, list[AgentCheckpoint]] = defaultdict(list)

    for path in checkpoint_files:
        try:
            cp = AgentCheckpoint.load(path)
            by_goal[cp.goal[:50]].append(cp)
        except Exception:
            continue

    for goal, checkpoints in sorted(by_goal.items()):
        latest = max(checkpoints, key=lambda c: c.checkpoint_at)
        console.print(f"[bold]{goal}...[/bold]")
        console.print(f"  Phase: {latest.phase.value}")
        console.print(f"  Progress: {len(latest.completed_ids)}/{len(latest.tasks)} tasks")
        console.print(f"  Last checkpoint: {latest.checkpoint_at.isoformat()[:19]}")
        console.print()
