"""Review command for recovering from failed agent runs (RFC-125).

Provides an interactive interface for reviewing and fixing failed executions,
similar to GitHub's merge conflict resolution UI.

Examples:
    sunwell review                    # Interactive review
    sunwell review --list             # Just list pending recoveries
    sunwell review abc123 --auto-fix  # Retry with agent
    sunwell review abc123 --skip      # Write only passed files
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()


@click.group(invoke_without_command=True)
@click.argument("recovery_id", required=False)
@click.option("--list", "-l", "list_only", is_flag=True, help="List pending recoveries")
@click.option("--auto-fix", is_flag=True, help="Auto-fix with agent")
@click.option("--skip", is_flag=True, help="Write only passed files, skip failed")
@click.option("--abort", is_flag=True, help="Delete recovery state")
@click.option("--hint", "-H", default=None, help="Hint for agent when using --auto-fix")
@click.option("--errors", is_flag=True, help="Show detailed error list")
@click.option("--context", is_flag=True, help="Show healing context for agent")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider for auto-fix")
@click.option("--model", "-m", default=None, help="Model for auto-fix")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def review(
    ctx,
    recovery_id: str | None,
    list_only: bool,
    auto_fix: bool,
    skip: bool,
    abort: bool,
    hint: str | None,
    errors: bool,
    context: bool,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Review and recover from failed agent runs.

    When Sunwell can't automatically fix errors, it saves progress for review.
    Use this command to see what succeeded, what failed, and choose how to proceed.

    \b
    EXAMPLES:
        sunwell review                    # Interactive review of pending recoveries
        sunwell review --list             # List all pending recoveries
        sunwell review abc123             # Review specific recovery
        sunwell review abc123 --auto-fix  # Retry with agent
        sunwell review abc123 --skip      # Write only passed files
        sunwell review abc123 --hint "User model is in models/user.py"

    \b
    RECOVERY OPTIONS:
        --auto-fix    Let agent retry with full context of what failed
        --skip        Write the files that passed, abandon the rest
        --abort       Delete recovery state entirely
        --hint        Provide a hint to help agent fix the issue
    """
    recovery_dir = Path.cwd() / ".sunwell" / "recovery"

    # List mode
    if list_only or (ctx.invoked_subcommand is None and not recovery_id):
        asyncio.run(_list_recoveries(recovery_dir, verbose))
        return

    # Need recovery_id for other operations
    if not recovery_id:
        asyncio.run(_interactive_review(recovery_dir, provider, model, verbose))
        return

    # Actions on specific recovery
    if abort:
        asyncio.run(_abort_recovery(recovery_dir, recovery_id))
    elif skip:
        asyncio.run(_skip_recovery(recovery_dir, recovery_id, verbose))
    elif auto_fix:
        asyncio.run(_auto_fix_recovery(recovery_dir, recovery_id, hint, provider, model, verbose))
    elif errors:
        asyncio.run(_show_errors(recovery_dir, recovery_id))
    elif context:
        asyncio.run(_show_context(recovery_dir, recovery_id))
    else:
        # Show details and interactive menu
        asyncio.run(_review_recovery(recovery_dir, recovery_id, provider, model, verbose))


async def _list_recoveries(recovery_dir: Path, verbose: bool) -> None:
    """List all pending recoveries."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)
    pending = manager.list_pending()

    if not pending:
        console.print("[dim]No pending recoveries.[/dim]")
        console.print(
            "\n[dim]Recoveries are created when agent runs fail with partial progress.[/dim]"
        )
        return

    table = Table(title="🔄 Pending Recoveries", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Goal", max_width=50)
    table.add_column("✅", style="green", justify="right")
    table.add_column("⚠️", style="yellow", justify="right")
    table.add_column("⏸️", style="dim", justify="right")
    table.add_column("Age")

    for summary in pending:
        table.add_row(
            summary.goal_hash[:8],
            summary.goal_preview[:50] + ("..." if len(summary.goal_preview) > 50 else ""),
            str(summary.passed),
            str(summary.failed),
            str(summary.waiting),
            summary.age_str,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(pending)} pending recoveries[/dim]")
    console.print("\n[bold]Commands:[/bold]")
    console.print("  sunwell review <id>           # Review specific recovery")
    console.print("  sunwell review <id> --auto-fix  # Retry with agent")
    console.print("  sunwell review <id> --skip      # Write passed files only")


async def _interactive_review(
    recovery_dir: Path,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Interactive review of pending recoveries."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)
    pending = manager.list_pending()

    if not pending:
        console.print("[dim]No pending recoveries to review.[/dim]")
        return

    # Show first recovery
    summary = pending[0]
    console.print(f"\n[bold]Recovery: {summary.goal_hash[:8]}[/bold] ({summary.age_str})")
    console.print(f"[dim]{summary.goal_preview}[/dim]\n")

    await _review_recovery(recovery_dir, summary.goal_hash, provider, model, verbose)


async def _review_recovery(
    recovery_dir: Path,
    recovery_id: str,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Review a specific recovery with interactive menu."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)

    # Find recovery by prefix match
    state = manager.load(recovery_id)
    if not state:
        # Try prefix match
        pending = manager.list_pending()
        matches = [s for s in pending if s.goal_hash.startswith(recovery_id)]
        if len(matches) == 1:
            state = manager.load(matches[0].goal_hash)
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{recovery_id}':[/yellow]")
            for m in matches:
                console.print(f"  {m.goal_hash[:8]} - {m.goal_preview[:40]}")
            return
        else:
            console.print(f"[red]Recovery not found: {recovery_id}[/red]")
            return

    if not state:
        console.print(f"[red]Recovery not found: {recovery_id}[/red]")
        return

    # Display recovery state
    _display_recovery_state(state)

    # Interactive menu
    console.print("\n[bold]Actions:[/bold]")
    console.print("  [a] Auto-fix with agent")
    console.print("  [e] Edit failed file in $EDITOR")
    console.print("  [h] Give agent a hint")
    console.print("  [s] Skip failed, write passed files")
    console.print("  [v] View errors in detail")
    console.print("  [c] View healing context")
    console.print("  [d] Delete recovery")
    console.print("  [q] Quit")

    choice = Prompt.ask("\nChoice", choices=["a", "e", "h", "s", "v", "c", "d", "q"], default="q")

    if choice == "a":
        await _auto_fix_recovery(recovery_dir, state.goal_hash, None, provider, model, verbose)
    elif choice == "e":
        await _edit_failed_file(state)
    elif choice == "h":
        hint = Prompt.ask("Enter hint for agent")
        await _auto_fix_recovery(recovery_dir, state.goal_hash, hint, provider, model, verbose)
    elif choice == "s":
        await _skip_recovery(recovery_dir, state.goal_hash, verbose)
    elif choice == "v":
        await _show_errors(recovery_dir, state.goal_hash)
    elif choice == "c":
        await _show_context(recovery_dir, state.goal_hash)
    elif choice == "d":
        await _abort_recovery(recovery_dir, state.goal_hash)
    # q = quit, do nothing


def _display_recovery_state(state) -> None:
    """Display recovery state in a nice format."""
    # Header
    console.print(Panel(
        f"[bold]{state.goal}[/bold]\n\n"
        f"Run ID: {state.run_id}\n"
        f"Reason: {state.failure_reason}",
        title="🔄 Recovery State",
        border_style="yellow",
    ))

    # Artifact status table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Status")
    table.add_column("File")
    table.add_column("Details", max_width=50)

    for artifact in state.passed_artifacts:
        table.add_row(
            "[green]✅ passed[/green]",
            str(artifact.path),
            "[dim]All gates passed[/dim]",
        )

    for artifact in state.failed_artifacts:
        error_preview = artifact.errors[0][:50] if artifact.errors else "Unknown error"
        table.add_row(
            "[yellow]⚠️ failed[/yellow]",
            str(artifact.path),
            f"[red]{error_preview}...[/red]" if len(artifact.errors) > 0 else "",
        )

    for artifact in state.waiting_artifacts:
        table.add_row(
            "[dim]⏸️ waiting[/dim]",
            str(artifact.path),
            "[dim]Blocked on failed dependency[/dim]",
        )

    console.print(table)
    console.print(f"\n[dim]Summary: {state.summary}[/dim]")


async def _auto_fix_recovery(
    recovery_dir: Path,
    recovery_id: str,
    hint: str | None,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Retry with agent using healing context."""
    from sunwell.cli.helpers import resolve_model
    from sunwell.recovery import RecoveryManager, build_healing_context

    manager = RecoveryManager(recovery_dir)
    state = manager.load(recovery_id)

    if not state:
        console.print(f"[red]Recovery not found: {recovery_id}[/red]")
        return

    console.print("[cyan]Building healing context...[/cyan]")

    # Build context
    healing_context = build_healing_context(state, hint)

    if verbose:
        console.print("\n[dim]Healing context:[/dim]")
        preview = healing_context[:500] + "..." if len(healing_context) > 500 else healing_context
        console.print(preview)
        console.print()

    # Resolve model
    try:
        synthesis_model = resolve_model(provider, model)
    except Exception as e:
        console.print(f"[red]Could not load model: {e}[/red]")
        return

    console.print(f"[cyan]Retrying with {synthesis_model}...[/cyan]\n")

    # Create focused fix goal
    failed_files = [str(a.path) for a in state.failed_artifacts]
    fix_goal = f"Fix the following files: {', '.join(failed_files)}\n\n{healing_context}"

    # Run agent with focused goal
    from sunwell.agent import (
        AdaptiveBudget,
        Agent,
        RunOptions,
        RunRequest,
        create_renderer,
    )
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    cwd = Path.cwd()
    tool_executor = ToolExecutor(
        workspace=cwd,
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    agent = Agent(
        model=synthesis_model,
        tool_executor=tool_executor,
        cwd=cwd,
        budget=AdaptiveBudget(total_budget=30_000),
    )

    request = RunRequest(
        goal=fix_goal,
        context={
            "cwd": str(cwd),
            "recovery_id": recovery_id,
            "is_recovery": True,
        },
        cwd=cwd,
        options=RunOptions(
            trust="workspace",
            timeout_seconds=300,
            converge=True,
        ),
    )

    renderer = create_renderer(mode="interactive", verbose=verbose)

    try:
        await renderer.render(agent.run(request))
        # If successful, mark resolved
        manager.mark_resolved(recovery_id)
        console.print("\n[green]✅ Recovery completed! Artifacts fixed.[/green]")
    except Exception as e:
        console.print(f"\n[yellow]Fix attempt failed: {e}[/yellow]")
        console.print("[dim]Recovery state preserved for another attempt.[/dim]")


async def _skip_recovery(recovery_dir: Path, recovery_id: str, verbose: bool) -> None:
    """Write only passed files, skip failed ones."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)
    state = manager.load(recovery_id)

    if not state:
        console.print(f"[red]Recovery not found: {recovery_id}[/red]")
        return

    passed = state.passed_artifacts
    if not passed:
        console.print("[yellow]No passed artifacts to write.[/yellow]")
        return

    console.print(f"[cyan]Writing {len(passed)} passed artifacts...[/cyan]")

    written = 0
    for artifact in passed:
        try:
            artifact.path.parent.mkdir(parents=True, exist_ok=True)
            artifact.path.write_text(artifact.content)
            written += 1
            if verbose:
                console.print(f"  ✅ {artifact.path}")
        except Exception as e:
            console.print(f"  [red]❌ {artifact.path}: {e}[/red]")

    console.print(f"\n[green]Written {written}/{len(passed)} files.[/green]")

    # Mark resolved
    manager.mark_resolved(recovery_id)
    console.print("[dim]Recovery marked as resolved (skipped failed artifacts).[/dim]")


async def _abort_recovery(recovery_dir: Path, recovery_id: str) -> None:
    """Delete recovery state."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)

    # Confirm
    confirm = Prompt.ask(
        f"Delete recovery {recovery_id[:8]}? This cannot be undone",
        choices=["y", "n"],
        default="n",
    )

    if confirm != "y":
        console.print("[dim]Aborted.[/dim]")
        return

    manager.delete(recovery_id)
    console.print(f"[green]Recovery {recovery_id[:8]} deleted.[/green]")


async def _show_errors(recovery_dir: Path, recovery_id: str) -> None:
    """Show detailed errors for a recovery."""
    from sunwell.recovery import RecoveryManager

    manager = RecoveryManager(recovery_dir)
    state = manager.load(recovery_id)

    if not state:
        console.print(f"[red]Recovery not found: {recovery_id}[/red]")
        return

    console.print(Panel(
        "\n".join(state.error_details[:30]) or "[dim]No error details[/dim]",
        title="Error Details",
        border_style="red",
    ))

    if len(state.error_details) > 30:
        console.print(f"[dim]... and {len(state.error_details) - 30} more errors[/dim]")


async def _show_context(recovery_dir: Path, recovery_id: str) -> None:
    """Show healing context that would be sent to agent."""
    from sunwell.recovery import RecoveryManager, build_healing_context

    manager = RecoveryManager(recovery_dir)
    state = manager.load(recovery_id)

    if not state:
        console.print(f"[red]Recovery not found: {recovery_id}[/red]")
        return

    context = build_healing_context(state)
    console.print(Panel(context, title="Healing Context", border_style="cyan"))


async def _edit_failed_file(state) -> None:
    """Open failed file in editor."""
    import os
    import subprocess

    failed = state.failed_artifacts
    if not failed:
        console.print("[dim]No failed artifacts to edit.[/dim]")
        return

    # Pick first failed file
    artifact = failed[0]

    # Write current content to file
    artifact.path.parent.mkdir(parents=True, exist_ok=True)
    artifact.path.write_text(artifact.content)

    # Get editor
    editor = os.environ.get("EDITOR", "vim")

    console.print(f"[cyan]Opening {artifact.path} in {editor}...[/cyan]")

    try:
        subprocess.run([editor, str(artifact.path)])
        console.print("[green]File edited. Re-run validation with:[/green]")
        console.print(f"  sunwell review {state.goal_hash[:8]} --auto-fix")
    except Exception as e:
        console.print(f"[red]Could not open editor: {e}[/red]")
