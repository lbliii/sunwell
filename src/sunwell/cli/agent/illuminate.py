"""Illuminate command for agent CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command()
@click.option(
    "--goals", "-g",
    multiple=True,
    required=True,
    help="Goals for self-improvement",
)
@click.option(
    "--time", "-t",
    default=120,
    help="Max execution time in seconds",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output",
)
def illuminate(goals: tuple[str, ...], time: int, verbose: bool) -> None:
    """Self-improvement mode (RFC-019 behavior).

    The original Naaru mode - finds and addresses opportunities to
    improve Sunwell's own codebase.

    Examples:

    \b
        sunwell agent illuminate -g "improve error handling"
        sunwell agent illuminate -g "add tests" -g "improve docs" --time 300
    """
    asyncio.run(_illuminate(list(goals), time, verbose))


async def _illuminate(goals: list[str], time: int, verbose: bool) -> None:
    """Run self-improvement mode."""
    from sunwell.naaru import Naaru
    from sunwell.types.config import NaaruConfig

    # Load config
    config = get_config()

    # Create models
    synthesis_model = None
    judge_model = None

    try:
        from sunwell.models.ollama import OllamaModel

        if config and hasattr(config, "naaru"):
            voice = getattr(config.naaru, "voice", "gemma3:1b")
            wisdom = getattr(config.naaru, "wisdom", "gemma3:4b")
        else:
            voice = "gemma3:1b"
            wisdom = "gemma3:4b"

        synthesis_model = OllamaModel(model=voice)
        judge_model = OllamaModel(model=wisdom)

        if verbose:
            console.print(f"[dim]Voice: {voice}, Wisdom: {wisdom}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load models: {e}[/yellow]")

    # Create Naaru config
    naaru_config = NaaruConfig()
    if config and hasattr(config, "naaru"):
        naaru_config = config.naaru

    naaru = Naaru(
        sunwell_root=Path.cwd(),
        synthesis_model=synthesis_model,
        judge_model=judge_model,
        config=naaru_config,
    )

    try:
        results = await naaru.illuminate(
            goals=goals,
            max_time_seconds=time,
            on_output=console.print,
        )

        # Show final summary
        if results.get("completed_proposals"):
            count = len(results['completed_proposals'])
            console.print(f"\n[bold]Completed {count} proposals[/bold]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())

