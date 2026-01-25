"""Workflow commands — Autonomous workflow execution (RFC-086).

Provides CLI commands for:
- `sunwell workflow run <chain>` — Run a workflow chain
- `sunwell workflow resume` — Resume last paused workflow
- `sunwell workflow list` — List active workflows
- `sunwell workflow status` — Show workflow status
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def workflow() -> None:
    """Autonomous workflow execution (RFC-086).

    \b
    Workflow chains run multiple skills in sequence with:
    - Checkpoints for review
    - State persistence
    - Error recovery

    \b
    Examples:
        sunwell workflow run feature-docs
        sunwell workflow resume
        sunwell workflow list
    """


@workflow.command()
@click.argument("chain_name")
@click.option("--target", "-t", type=click.Path(), help="Target file or directory")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def run(chain_name: str, target: str | None, dry_run: bool, as_json: bool) -> None:
    """Run a workflow chain.

    \b
    Available chains:
        feature-docs   — Document a new feature end-to-end
        health-check   — Comprehensive validation of existing docs
        quick-fix      — Fast issue resolution
        modernize      — Update legacy documentation
    """
    import json as json_lib

    from sunwell.workflow.types import WORKFLOW_CHAINS

    chain = WORKFLOW_CHAINS.get(chain_name)
    if not chain:
        if as_json:
            click.echo(json_lib.dumps({"error": f"Unknown workflow: {chain_name}"}))
        else:
            console.print(f"[red]Unknown workflow: {chain_name}[/red]")
            console.print(f"Available: {', '.join(WORKFLOW_CHAINS.keys())}")
        return

    if dry_run:
        if as_json:
            click.echo(json_lib.dumps({
                "name": chain.name,
                "description": chain.description,
                "tier": chain.tier.value,
                "steps": [{"skill": s.skill, "purpose": s.purpose} for s in chain.steps],
                "checkpoint_after": list(chain.checkpoint_after),
            }))
        else:
            console.print(f"\n[bold]Workflow: {chain.name}[/bold]")
            console.print(f"Description: {chain.description}")
            console.print(f"Tier: {chain.tier.value}")
            console.print()
            console.print("[bold]Steps:[/bold]")
            for i, step in enumerate(chain.steps, 1):
                checkpoint = " [checkpoint]" if i - 1 in chain.checkpoint_after else ""
                console.print(f"  {i}. {step.skill} — {step.purpose}{checkpoint}")
        return

    # Run the workflow
    asyncio.run(_run_workflow(chain_name, target, as_json))


async def _run_workflow(chain_name: str, target: str | None, as_json: bool = False) -> None:
    """Execute a workflow chain."""
    import json as json_lib

    from sunwell.workflow import WorkflowEngine
    from sunwell.workflow.engine import WriterContext
    from sunwell.workflow.types import WORKFLOW_CHAINS

    chain = WORKFLOW_CHAINS[chain_name]
    state_dir = Path(".sunwell/state")

    engine = WorkflowEngine(state_dir=state_dir)

    context = WriterContext(
        lens=None,
        target_file=Path(target) if target else None,
        working_dir=Path.cwd(),
    )

    if not as_json:
        console.print(f"\n[bold]🔄 Starting workflow: {chain.name}[/bold]")
        console.print(f"Steps: {len(chain.steps)}")
        console.print()

    result = await engine.execute(chain, context)

    if as_json:
        click.echo(json_lib.dumps(result.execution.to_dict()))
        return

    # Show results
    if result.status == "completed":
        console.print("[green]✅ Workflow complete[/green]")
        console.print(f"Steps completed: {len(result.execution.completed_steps)}")
    elif result.status == "paused":
        console.print("[yellow]⏸ Workflow paused[/yellow]")
        console.print("Resume with: sunwell workflow resume")
    elif result.status == "error":
        console.print(f"[red]❌ Workflow error: {result.error}[/red]")

    # Show step summary
    console.print()
    for step_result in result.execution.completed_steps:
        status_icon = "✅" if step_result.status == "success" else "❌"
        duration = f"{step_result.duration_s:.1f}s" if step_result.duration_s else "..."
        console.print(f"  {status_icon} {step_result.skill} ({duration})")


@workflow.command()
def resume() -> None:
    """Resume the last paused workflow."""
    asyncio.run(_resume_workflow())


async def _resume_workflow() -> None:
    """Resume a paused workflow."""
    from sunwell.workflow.state import WorkflowStateManager

    state_dir = Path(".sunwell/state")
    manager = WorkflowStateManager(state_dir)

    active = await manager.list_active()

    if not active:
        console.print("[yellow]No active workflows to resume[/yellow]")
        return

    # Resume the most recent one
    state = active[0]
    console.print(f"\n[bold]Resuming: {state.topic or state.chain_name}[/bold]")
    console.print(f"ID: {state.id}")
    console.print(f"Progress: step {state.current_step + 1}")
    console.print()

    from sunwell.workflow import WorkflowEngine

    engine = WorkflowEngine(state_dir=state_dir)
    result = await engine.resume(state.id)

    if result.status == "completed":
        console.print("[green]✅ Workflow complete[/green]")
    elif result.status == "paused":
        console.print("[yellow]⏸ Workflow paused again[/yellow]")
    elif result.status == "error":
        console.print(f"[red]❌ Error: {result.error}[/red]")


@workflow.command(name="list")
def list_workflows() -> None:
    """List active workflows."""
    asyncio.run(_list_workflows())


async def _list_workflows() -> None:
    """List all active workflows."""
    from sunwell.workflow.state import WorkflowStateManager

    state_dir = Path(".sunwell/state")
    manager = WorkflowStateManager(state_dir)

    states = await manager.list_all()

    if not states:
        console.print("[dim]No workflows found[/dim]")
        return

    table = Table(title="Workflows")
    table.add_column("ID", style="cyan")
    table.add_column("Chain")
    table.add_column("Status")
    table.add_column("Progress")
    table.add_column("Updated")

    for state in states:
        status_style = {
            "completed": "green",
            "paused": "yellow",
            "running": "blue",
            "error": "red",
        }.get(state.status, "white")

        progress = f"{state.current_step + 1}/{len(state.pending_steps) + state.current_step + 1}"

        table.add_row(
            state.id[:20] + "...",
            state.chain_name,
            f"[{status_style}]{state.status}[/{status_style}]",
            progress,
            state.updated_at[:16] if state.updated_at else "-",
        )

    console.print(table)


@workflow.command()
@click.argument("execution_id", required=False)
def status(execution_id: str | None) -> None:
    """Show workflow status."""
    asyncio.run(_show_status(execution_id))


async def _show_status(execution_id: str | None) -> None:
    """Show detailed workflow status."""
    from sunwell.workflow.state import WorkflowStateManager

    state_dir = Path(".sunwell/state")
    manager = WorkflowStateManager(state_dir)

    if execution_id:
        state = await manager.load(execution_id)
        if not state:
            console.print(f"[red]Workflow not found: {execution_id}[/red]")
            return
        states = [state]
    else:
        states = await manager.list_active()
        if not states:
            console.print("[dim]No active workflows[/dim]")
            return

    for state in states:
        console.print(f"\n[bold]{state.topic or state.chain_name}[/bold]")
        console.print(f"ID: {state.id}")
        console.print(f"Chain: {state.chain_name}")
        console.print(f"Status: {state.status}")
        console.print(f"Step: {state.current_step + 1}")
        console.print()

        console.print("[bold]Completed:[/bold]")
        for step in state.completed_steps:
            status_icon = "✅" if step.get("status") == "success" else "❌"
            console.print(f"  {status_icon} {step.get('skill', '?')}")

        console.print("[bold]Pending:[/bold]")
        for skill in state.pending_steps:
            console.print(f"  ⏳ {skill}")


@workflow.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def chains(as_json: bool) -> None:
    """List available workflow chains."""
    import json as json_lib

    from sunwell.workflow.types import WORKFLOW_CHAINS

    if as_json:
        chains_data = [
            {
                "name": chain.name,
                "description": chain.description,
                "steps": [s.skill for s in chain.steps],
                "checkpoint_after": list(chain.checkpoint_after),
                "tier": chain.tier.value,
            }
            for chain in WORKFLOW_CHAINS.values()
        ]
        click.echo(json_lib.dumps(chains_data))
        return

    table = Table(title="Workflow Chains")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Steps")
    table.add_column("Tier")

    for chain in WORKFLOW_CHAINS.values():
        table.add_row(
            chain.name,
            chain.description,
            str(len(chain.steps)),
            chain.tier.value,
        )

    console.print(table)


@workflow.command()
@click.argument("user_input", nargs=-1, required=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def auto(user_input: tuple[str, ...], as_json: bool) -> None:
    """Automatically route a request to the appropriate workflow.

    \b
    Examples:
        sunwell workflow auto "audit and fix this doc"
        sunwell workflow auto "document the batch API"
    """
    import json as json_lib

    from sunwell.workflow import IntentRouter

    router = IntentRouter()
    input_text = " ".join(user_input)

    intent, workflow_chain = router.classify_and_select(input_text)

    if as_json:
        click.echo(json_lib.dumps({
            "category": intent.category.value,
            "confidence": intent.confidence,
            "signals": list(intent.signals),
            "suggested_workflow": workflow_chain.name if workflow_chain else None,
            "tier": intent.tier.value,
        }))
        return

    explanation = router.explain_routing(input_text)
    console.print(explanation)

    if workflow_chain and click.confirm("\nProceed with this workflow?"):
        asyncio.run(_run_workflow(workflow_chain.name, None))
