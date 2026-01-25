"""Resume command for agent CLI."""


import asyncio
from pathlib import Path
from typing import Any

import click

from sunwell.interface.generative.cli.theme import create_sunwell_console

console = create_sunwell_console()


@click.command()
@click.option(
    "--checkpoint", "-c",
    default=None,
    help="Path to checkpoint file",
)
@click.option(
    "--plan-id", "-p",
    default=None,
    help="Plan ID to resume (RFC-040)",
)
@click.option(
    "--goal", "-g",
    default=None,
    help="Goal to find checkpoint for (RFC-130)",
)
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
    help="Resume from specific phase (RFC-130)",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "ollama"]),
    default=None,
    help="Model provider (default: from config)",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override model selection",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def resume(
    checkpoint: str | None,
    plan_id: str | None,
    goal: str | None,
    phase: str | None,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Resume an interrupted agent run from checkpoint.

    Supports three modes:
    - Task-based (RFC-032): --checkpoint option
    - Artifact-based (RFC-040): --plan-id option
    - Goal-based (RFC-130): --goal option

    Examples:

    \b
        sunwell agent resume                                    # Latest plan
        sunwell agent resume --plan-id my-api                   # Specific plan
        sunwell agent resume --checkpoint .sunwell/checkpoints/agent-*.json
        sunwell agent resume --goal "Add OAuth"                 # RFC-130: Goal-based
        sunwell agent resume --goal "Add OAuth" --phase design_approved
    """
    asyncio.run(_resume_agent(checkpoint, plan_id, goal, phase, provider, model, verbose))


async def _resume_agent(
    checkpoint_path: str | None,
    plan_id: str | None,
    goal: str | None,
    phase_filter: str | None,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> None:
    """Resume agent from checkpoint."""
    from sunwell.interface.generative.cli.helpers import resolve_model

    # RFC-130: Goal-based resume takes priority
    if goal:
        await _resume_from_goal(goal, phase_filter, provider_override, model_override, verbose)
        return

    # RFC-040: Artifact-based resume
    if plan_id or (not checkpoint_path and not goal):
        # Try artifact-based resume first
        from sunwell.planning.naaru.persistence import PlanStore, get_latest_execution

        store = PlanStore()

        execution = store.load(plan_id) if plan_id else get_latest_execution()

        if execution:
            await _resume_artifact_execution(execution, provider_override, model_override, verbose)
            return
        elif plan_id:
            console.print(f"[void.purple]✗ No plan found with ID: {plan_id}[/void.purple]")
            return
        # Fall through to task-based resume

    # RFC-032: Task-based resume
    from sunwell.planning.naaru.checkpoint import AgentCheckpoint, find_latest_checkpoint

    # Find checkpoint
    if checkpoint_path:
        try:
            cp = AgentCheckpoint.load(Path(checkpoint_path))
        except Exception as e:
            console.print(f"[void.purple]✗ Failed to load checkpoint: {e}[/void.purple]")
            return
    else:
        cp = find_latest_checkpoint()
        if not cp:
            console.print("[void.purple]✗ No checkpoint found.[/void.purple]")
            console.print("[neutral.dim]Run 'sunwell \"goal\"' first.[/neutral.dim]")
            return

    # Show checkpoint info (RFC-131: Holy Light styling)
    summary = cp.get_progress_summary()

    console.print(f"[sunwell.heading]◆ Resuming (task-based):[/] {cp.goal}")
    console.print(f"   Started: {summary['started_at']}")
    console.print(f"   Progress: {summary['completed']}/{summary['total_tasks']} tasks")
    console.print(f"   Remaining: {summary['remaining']} tasks\n")

    remaining = cp.get_remaining_tasks()

    if not remaining:
        console.print("[holy.success]★ All tasks already completed![/holy.success]")
        return

    console.print("[sunwell.heading]Remaining tasks:[/sunwell.heading]")
    for task in remaining[:10]:
        console.print(f"  · {task.description}")

    if len(remaining) > 10:
        console.print(f"  [neutral.dim]... and {len(remaining) - 10} more[/neutral.dim]")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    # Resume execution
    from sunwell.planning.naaru import Naaru
    from sunwell.knowledge.project import ProjectResolutionError, resolve_project
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # RFC-117: Try to resolve project context
    workspace = Path(cp.working_directory)
    project = None
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        pass

    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Load model using resolve_model()
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
    except Exception:
        console.print("[holy.gold]△ Warning: Could not load model[/holy.gold]")

    naaru = Naaru(
        workspace=Path(cp.working_directory),
        synthesis_model=synthesis_model,
        tool_executor=tool_executor,
    )

    # Execute remaining tasks
    # Note: This is a simplified resume - full implementation would restore task graph state
    result = await naaru.run(
        goal=cp.goal,
        context={
            "cwd": cp.working_directory,
            "checkpoint": cp,
            "completed_ids": list(cp.completed_ids),
        },
        on_progress=console.print,
    )

    done = result.completed_count
    total = len(result.tasks)
    console.print(f"\n[holy.success]★ Complete:[/] {done}/{total} tasks")


async def _resume_from_goal(
    goal: str,
    phase_filter: str | None,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> None:
    """Resume execution from goal-based checkpoint (RFC-130).

    Enables intelligent resume from semantic phase boundaries.
    """
    from sunwell.interface.generative.cli.helpers import resolve_model
    from sunwell.planning.naaru.checkpoint import AgentCheckpoint, CheckpointPhase

    workspace = Path.cwd()

    # Find checkpoint for goal
    cp = AgentCheckpoint.find_latest_for_goal(workspace, goal)

    if not cp:
        console.print(f"[void.purple]✗ No checkpoint for goal: {goal}[/void.purple]")
        console.print("[neutral.dim]Hint: sunwell agent resume — list checkpoints[/neutral.dim]")
        return

    # Filter by phase if specified
    if phase_filter:
        target_phase = CheckpointPhase(phase_filter)
        all_checkpoints = AgentCheckpoint.find_all_for_goal(workspace, goal)
        phase_checkpoints = [c for c in all_checkpoints if c.phase == target_phase]
        if phase_checkpoints:
            cp = phase_checkpoints[0]  # Most recent matching phase
        else:
            console.print(f"[void.purple]✗ No checkpoint at phase: {phase_filter}[/void.purple]")
            available = {c.phase.value for c in all_checkpoints}
            phases = ", ".join(sorted(available))
            console.print(f"[neutral.dim]Available: {phases}[/neutral.dim]")
            return

    # Show checkpoint info (RFC-131: Holy Light styling)
    console.print("\n[holy.radiant]◆ Checkpoint Found (Goal-Based Resume)[/holy.radiant]\n")
    console.print(f"[sunwell.heading]Goal:[/] {cp.goal}")
    console.print(f"[sunwell.heading]Phase:[/] {cp.phase.value}")
    console.print(f"[sunwell.heading]Summary:[/] {cp.phase_summary or 'N/A'}")
    console.print(f"[sunwell.heading]Checkpoint at:[/] {cp.checkpoint_at.isoformat()}")

    # Show progress
    summary = cp.get_progress_summary()
    console.print("\n[sunwell.heading]Progress:[/sunwell.heading]")
    console.print(f"  · Tasks: {summary['completed']}/{summary['total_tasks']} completed")
    console.print(f"  · Artifacts: {summary['artifacts']}")
    console.print(f"  · Duration: {summary['duration_seconds']:.1f}s")

    # Show user decisions if any
    if cp.user_decisions:
        console.print("\n[sunwell.heading]User Decisions Preserved:[/sunwell.heading]")
        for decision in cp.user_decisions[:5]:
            console.print(f"  · {decision[:60]}...")
        if len(cp.user_decisions) > 5:
            console.print(f"  [neutral.dim]... and {len(cp.user_decisions) - 5} more[/neutral.dim]")

    # Show spawned specialists if any
    if cp.spawned_specialists:
        console.print(f"\n[sunwell.heading]Spawned Specialists:[/] {len(cp.spawned_specialists)}")

    # Show remaining tasks
    remaining = cp.get_remaining_tasks()
    if remaining:
        console.print(f"\n[sunwell.heading]Remaining Tasks ({len(remaining)}):[/sunwell.heading]")
        for task in remaining[:5]:
            console.print(f"  · {task.description[:60]}...")
        if len(remaining) > 5:
            console.print(f"  [neutral.dim]... and {len(remaining) - 5} more[/neutral.dim]")

    # Confirm resume
    if not click.confirm("\nResume from this checkpoint?"):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    # Resume execution
    from sunwell.planning.naaru import Naaru
    from sunwell.knowledge.project import ProjectResolutionError, resolve_project
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    # Resolve project context
    project = None
    try:
        project = resolve_project(project_root=workspace)
    except ProjectResolutionError:
        pass

    tool_executor = ToolExecutor(
        project=project,
        workspace=workspace if project is None else None,
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Load model
    synthesis_model = None
    try:
        synthesis_model = resolve_model(provider_override, model_override)
    except Exception:
        console.print("[holy.gold]△ Warning: Could not load model[/holy.gold]")

    naaru = Naaru(
        workspace=workspace,
        synthesis_model=synthesis_model,
        tool_executor=tool_executor,
    )

    # Execute remaining tasks with checkpoint context
    console.print(f"\n[holy.radiant]◆ Resuming from phase: {cp.phase.value}[/holy.radiant]\n")

    result = await naaru.run(
        goal=cp.goal,
        context={
            "cwd": cp.working_directory,
            "checkpoint": cp,
            "completed_ids": list(cp.completed_ids),
            "resume_phase": cp.phase.value,
            "user_decisions": list(cp.user_decisions),
        },
        on_progress=console.print if verbose else None,
    )

    # Summary
    done = result.completed_count
    total = len(result.tasks)
    console.print(f"\n[holy.success]★ Complete:[/] {done}/{total} tasks")


async def _resume_artifact_execution(
    execution,
    provider_override: str | None,
    model_override: str | None,
    verbose: bool,
) -> None:
    """Resume artifact-based execution (RFC-040)."""
    from sunwell.interface.generative.cli.helpers import resolve_model
    from sunwell.planning.naaru.persistence import (
        PlanStore,
        resume_execution,
    )

    console.print(f"[sunwell.heading]◆ Resuming (artifact-based):[/] {execution.goal}")
    console.print(f"   Status: {execution.status.value}")
    console.print(f"   Progress: {len(execution.completed)}/{len(execution.graph)} artifacts")
    console.print(f"   Progress: {execution.progress_percent:.0f}%\n")

    remaining = execution.get_remaining_artifacts()

    if not remaining:
        console.print("[holy.success]★ All artifacts already completed![/holy.success]")
        return

    # Show execution waves
    resume_wave = execution.get_resume_wave()
    waves = execution.graph.execution_waves()
    wave_num = resume_wave + 1
    console.print(f"[sunwell.heading]Resume from wave {wave_num}/{len(waves)}[/]")

    console.print("\n[sunwell.heading]Remaining artifacts:[/sunwell.heading]")
    for aid in remaining[:10]:
        artifact = execution.graph[aid]
        console.print(f"  · {aid}: {artifact.description[:40]}...")

    if len(remaining) > 10:
        console.print(f"  [neutral.dim]... and {len(remaining) - 10} more[/neutral.dim]")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[neutral.dim]Aborted[/neutral.dim]")
        return

    # Create artifact creation function using resolve_model()
    from sunwell.planning.naaru.planners import ArtifactPlanner

    try:
        model = resolve_model(provider_override, model_override)
        planner = ArtifactPlanner(model=model)
    except Exception as e:
        console.print(f"[void.purple]✗ Failed to load model: {e}[/void.purple]")
        return

    async def create_artifact(spec: Any) -> str:
        """Create an artifact using the planner."""
        result = await planner.create_artifact(spec, {})
        return result

    # Resume execution
    try:
        result = await resume_execution(
            execution=execution,
            create_fn=create_artifact,
            on_progress=console.print if verbose else None,
        )

        # Save updated execution
        store = PlanStore()
        execution.update_from_result(result)
        store.save(execution)

        # Summary
        console.print("\n[sunwell.heading]═══ Summary ═══[/sunwell.heading]")
        console.print(f"  Completed: {len(result.completed)}")
        console.print(f"  Failed: {len(result.failed)}")

        if len(result.failed) == 0:
            console.print("\n[holy.success]★ Execution complete[/holy.success]")
        else:
            console.print("\n[holy.gold]△ Execution completed with errors[/holy.gold]")
            for aid, error in result.failed.items():
                console.print(f"  ✗ {aid}: {error[:50]}")

    except KeyboardInterrupt:
        console.print("\n[holy.gold]△ Interrupted - progress saved[/holy.gold]")
    except Exception as e:
        console.print(f"\n[void.purple]✗ Error: {e}[/void.purple]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())

