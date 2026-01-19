"""Adaptive Agent CLI command (RFC-042).

Provides the `sunwell adaptive` command for signal-driven execution.
This is the recommended way to run goals - it automatically selects
the right techniques based on complexity, confidence, and budget.

Example:
    sunwell adaptive "Build a Flask forum app"
    sunwell adaptive "Add auth" --verbose
    sunwell adaptive "Fix types" --budget 10000
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("adaptive")
@click.argument("goal", required=True)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress events")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output (JSON events only)")
@click.option("--json", "json_output", is_flag=True, help="Output as newline-delimited JSON")
@click.option("--budget", "-b", type=int, default=50_000, help="Token budget (default: 50000)")
@click.option("--model", "-m", default=None, help="Override model selection")
@click.option("--dry-run", is_flag=True, help="Plan only, don't execute")
@click.option("--no-memory", is_flag=True, help="Disable Simulacrum memory")
@click.option("--session", "-s", default=None, help="Resume from session ID")
def adaptive(
    goal: str,
    verbose: bool,
    quiet: bool,
    json_output: bool,
    budget: int,
    model: str | None,
    dry_run: bool,
    no_memory: bool,
    session: str | None,
) -> None:
    """Run a goal with the Adaptive Agent (RFC-042).

    \b
    The Adaptive Agent automatically selects techniques based on:
    - Complexity signals (harmonic vs single-shot planning)
    - Confidence signals (vortex vs interference vs single-shot)
    - Error signals (compound eye vs direct fix)
    - Budget constraints (automatic downgrade when tight)

    \b
    Examples:
        sunwell adaptive "Build a REST API with auth"
        sunwell adaptive "Fix the type errors in auth.py" --verbose
        sunwell adaptive "Add dark mode" --budget 10000
    """
    # Select renderer mode
    if json_output:
        renderer_mode = "json"
    elif quiet:
        renderer_mode = "quiet"
    elif verbose:
        renderer_mode = "interactive"
    else:
        renderer_mode = "interactive"

    asyncio.run(
        _run_adaptive(
            goal=goal,
            budget=budget,
            model_override=model,
            renderer_mode=renderer_mode,
            dry_run=dry_run,
            use_memory=not no_memory,
            session_id=session,
            verbose=verbose,
        )
    )


async def _run_adaptive(
    goal: str,
    budget: int,
    model_override: str | None,
    renderer_mode: str,
    dry_run: bool,
    use_memory: bool,
    session_id: str | None,
    verbose: bool,
) -> None:
    """Execute goal with Adaptive Agent."""
    from sunwell.adaptive import (
        AdaptiveAgent,
        AdaptiveBudget,
        RendererConfig,
        create_renderer,
    )
    from sunwell.config import get_config

    # Load config
    config = get_config()

    # Create model
    synthesis_model = None
    try:
        from sunwell.models.ollama import OllamaModel

        model_name = model_override
        if not model_name and config and hasattr(config, "naaru"):
            model_name = getattr(config.naaru, "voice", "gemma3:1b")

        if not model_name:
            model_name = "gemma3:1b"

        synthesis_model = OllamaModel(model=model_name)
        if verbose:
            console.print(f"[dim]Using model: {model_name}[/dim]")

    except Exception as e:
        console.print(f"[red]Could not load model: {e}[/red]")
        return

    if not synthesis_model:
        console.print("[red]No model available[/red]")
        return

    # Setup budget
    adaptive_budget = AdaptiveBudget(total_budget=budget)

    # Setup Simulacrum store (optional)
    simulacrum_store = None
    if use_memory:
        try:
            from sunwell.simulacrum import SimulacrumStore, StorageConfig

            store_path = Path.home() / ".sunwell" / "simulacrum"
            simulacrum_store = SimulacrumStore(
                base_path=store_path,
                config=StorageConfig(auto_cleanup=True),
            )
            if session_id:
                simulacrum_store.load_session(session_id)
                if verbose:
                    console.print(f"[dim]Loaded session: {session_id}[/dim]")
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Memory disabled: {e}[/yellow]")

    # Create tool executor
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust

    tool_executor = ToolExecutor(
        workspace=Path.cwd(),
        policy=ToolPolicy(trust_level=ToolTrust.WORKSPACE),
    )

    # Create adaptive agent
    agent = AdaptiveAgent(
        model=synthesis_model,
        budget=adaptive_budget,
        simulacrum=simulacrum_store,
        workspace=Path.cwd(),
        tool_executor=tool_executor,
    )

    # Create renderer
    renderer_config = RendererConfig(
        mode=renderer_mode,
        show_signals=verbose,
        show_gates=verbose,
        show_learning=verbose,
    )
    renderer = create_renderer(renderer_config)

    # Dry run: just show signals and plan
    if dry_run:
        console.print("[yellow]Planning only (--dry-run)[/yellow]\n")
        async for event in agent.plan(goal):
            await renderer.render(event)
        return

    # Full execution
    try:
        async for event in agent.run(goal):
            await renderer.render(event)

        # Show summary
        await renderer.render_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
