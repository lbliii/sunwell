"""Resume command for agent CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

console = Console()


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
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def resume(checkpoint: str | None, plan_id: str | None, verbose: bool) -> None:
    """Resume an interrupted agent run from checkpoint.

    Supports two modes:
    - Task-based (RFC-032): --checkpoint option
    - Artifact-based (RFC-040): --plan-id option

    Examples:

    \b
        sunwell agent resume                                    # Latest plan
        sunwell agent resume --plan-id my-api                   # Specific plan
        sunwell agent resume --checkpoint .sunwell/checkpoints/agent-*.json
    """
    asyncio.run(_resume_agent(checkpoint, plan_id, verbose))


async def _resume_agent(checkpoint_path: str | None, plan_id: str | None, verbose: bool) -> None:
    """Resume agent from checkpoint."""
    # RFC-040: Artifact-based resume
    if plan_id or (not checkpoint_path):
        # Try artifact-based resume first
        from sunwell.naaru.persistence import PlanStore, get_latest_execution

        store = PlanStore()

        execution = store.load(plan_id) if plan_id else get_latest_execution()

        if execution:
            await _resume_artifact_execution(execution, verbose)
            return
        elif plan_id:
            console.print(f"[red]No plan found with ID: {plan_id}[/red]")
            return
        # Fall through to task-based resume

    # RFC-032: Task-based resume
    from sunwell.naaru.checkpoint import AgentCheckpoint, find_latest_checkpoint

    # Find checkpoint
    if checkpoint_path:
        try:
            cp = AgentCheckpoint.load(Path(checkpoint_path))
        except Exception as e:
            console.print(f"[red]Failed to load checkpoint: {e}[/red]")
            return
    else:
        cp = find_latest_checkpoint()
        if not cp:
            console.print("[red]No checkpoint found. Run 'sunwell \"goal\"' first.[/red]")
            return

    # Show checkpoint info
    summary = cp.get_progress_summary()

    console.print(f"[bold]Resuming (task-based):[/bold] {cp.goal}")
    console.print(f"   Started: {summary['started_at']}")
    console.print(f"   Progress: {summary['completed']}/{summary['total_tasks']} tasks")
    console.print(f"   Remaining: {summary['remaining']} tasks\n")

    remaining = cp.get_remaining_tasks()

    if not remaining:
        console.print("[green]All tasks already completed![/green]")
        return

    console.print("[bold]Remaining tasks:[/bold]")
    for task in remaining[:10]:
        console.print(f"  • {task.description}")

    if len(remaining) > 10:
        console.print(f"  ... and {len(remaining) - 10} more")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[dim]Aborted[/dim]")
        return

    # Resume execution
    from sunwell.naaru import Naaru
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    tool_executor = ToolExecutor(
        workspace=Path(cp.working_directory),
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Try to load model
    synthesis_model = None
    try:
        from sunwell.models.ollama import OllamaModel
        synthesis_model = OllamaModel(model="gemma3:1b")
    except Exception:
        console.print("[yellow]Warning: Could not load model[/yellow]")

    naaru = Naaru(
        sunwell_root=Path(cp.working_directory),
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

    console.print(f"\n✨ Complete: {result.completed_count}/{len(result.tasks)} tasks")


async def _resume_artifact_execution(execution, verbose: bool) -> None:
    """Resume artifact-based execution (RFC-040)."""
    from sunwell.naaru.persistence import (
        PlanStore,
        resume_execution,
    )

    console.print(f"[bold]Resuming (artifact-based):[/bold] {execution.goal}")
    console.print(f"   Status: {execution.status.value}")
    console.print(f"   Progress: {len(execution.completed)}/{len(execution.graph)} artifacts")
    console.print(f"   Progress: {execution.progress_percent:.0f}%\n")

    remaining = execution.get_remaining_artifacts()

    if not remaining:
        console.print("[green]All artifacts already completed![/green]")
        return

    # Show execution waves
    resume_wave = execution.get_resume_wave()
    waves = execution.graph.execution_waves()
    console.print(f"[bold]Resume from wave {resume_wave + 1}/{len(waves)}[/bold]")

    console.print("\n[bold]Remaining artifacts:[/bold]")
    for aid in remaining[:10]:
        artifact = execution.graph[aid]
        console.print(f"  • {aid}: {artifact.description[:40]}...")

    if len(remaining) > 10:
        console.print(f"  ... and {len(remaining) - 10} more")

    # Confirm resume
    if not click.confirm("\nResume execution?"):
        console.print("[dim]Aborted[/dim]")
        return

    # Create artifact creation function
    # This is a simplified implementation - would need proper planner integration
    from sunwell.models.ollama import OllamaModel
    from sunwell.naaru.planners import ArtifactPlanner

    try:
        model = OllamaModel(model="gemma3:1b")
        planner = ArtifactPlanner(model=model)
    except Exception as e:
        console.print(f"[red]Failed to load model: {e}[/red]")
        return

    async def create_artifact(spec):
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
        console.print("\n[bold]═══ Summary ═══[/bold]")
        console.print(f"  Completed: {len(result.completed)}")
        console.print(f"  Failed: {len(result.failed)}")

        if len(result.failed) == 0:
            console.print("\n[green]✓ Execution complete[/green]")
        else:
            console.print("\n[yellow]⚠ Execution completed with errors[/yellow]")
            for aid, error in result.failed.items():
                console.print(f"  ✗ {aid}: {error[:50]}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted - progress saved[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())

