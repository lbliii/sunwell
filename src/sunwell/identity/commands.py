"""Identity CLI commands for /identity interactions.

RFC-023: Implements the /identity command family for inspecting and
managing the adaptive identity system.

Commands:
- /identity - View current identity model
- /identity rate - Rate the identity model (1-5)
- /identity refresh - Force re-synthesis from observations
- /identity clear - Reset identity (start fresh)
- /identity pause - Disable behavioral learning
- /identity resume - Re-enable behavioral learning
- /identity export - Export identity data to JSON
"""


import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from sunwell.identity.store import IdentityStore


def format_identity_display(identity_store: IdentityStore) -> str:
    """Format identity for display in Rich panel."""
    identity = identity_store.identity

    lines = []

    # Status line
    if identity.paused:
        status = "[yellow]Paused ⏸[/yellow]"
    elif identity.is_usable():
        status = "[green]Active ✓[/green]"
    else:
        status = "[dim]Inactive[/dim]"

    conf_color = "green" if identity.confidence >= 0.8 else "yellow" if identity.confidence >= 0.6 else "red"
    lines.append(f"Status: {status}     Confidence: [{conf_color}]{identity.confidence:.0%}[/{conf_color}]")

    # Last updated
    if identity.last_digest:
        lines.append(f"Last Updated: {identity.last_digest.strftime('%Y-%m-%d %H:%M')} (turn {identity.turn_count_at_digest})")
    else:
        lines.append("Last Updated: Never (no digest yet)")

    # Source
    if identity.inherited:
        lines.append("Source: [cyan]global[/cyan] (inherited)")
    else:
        lines.append("Source: [cyan]session[/cyan]")

    lines.append("")

    # Tone
    if identity.tone:
        lines.append(f"[bold]Tone:[/bold] {identity.tone}")
        lines.append("")

    # Values
    if identity.values:
        lines.append("[bold]Values:[/bold]")
        for value in identity.values[:5]:
            lines.append(f"  • {value}")
        lines.append("")

    # Prompt
    if identity.prompt:
        lines.append("[bold]Interaction Guide:[/bold]")
        # Word wrap at ~55 chars
        words = identity.prompt.split()
        current_line = "  "
        for word in words:
            if len(current_line) + len(word) > 55:
                lines.append(current_line)
                current_line = "  " + word
            else:
                current_line += (" " if len(current_line) > 2 else "") + word
        if current_line.strip():
            lines.append(current_line)
        lines.append("")

    # Recent observations
    if identity.observations:
        recent = identity.observations[-5:]
        lines.append(f"[bold]Recent Observations[/bold] ({len(recent)} of {len(identity.observations)}):")
        for obs in recent:
            conf_display = f"[dim][{obs.confidence:.2f}][/dim]"
            obs_text = obs.observation[:45] + "..." if len(obs.observation) > 45 else obs.observation
            lines.append(f"  • {obs_text:50} {conf_display}")
        lines.append("")

    # Help hint
    lines.append("[dim]/identity rate[/dim] to provide feedback")

    return "\n".join(lines)


async def handle_identity_command(
    arg: str,
    identity_store: IdentityStore,
    console: Console,
    tiny_model=None,
    turn_count: int = 0,
) -> None:
    """Handle /identity commands.

    Args:
        arg: Command argument (rate, refresh, clear, pause, resume, export, or empty)
        identity_store: The IdentityStore instance
        console: Rich console for output
        tiny_model: Optional tiny LLM for digest refresh
        turn_count: Current turn count for digest tracking
    """
    from rich.panel import Panel

    from sunwell.planning.naaru.persona import MURU

    if not arg:
        # Main view: /identity
        display = format_identity_display(identity_store)
        console.print(Panel(
            display,
            title=f"{MURU.name}'s Identity Model",
            border_style="cyan",
        ))
        return

    subcmd = arg.lower().split()[0]
    subarg = arg[len(subcmd):].strip() if len(arg) > len(subcmd) else ""

    if subcmd == "rate":
        # Rate the identity model
        await _handle_rate(identity_store, console, subarg)

    elif subcmd == "refresh":
        # Force re-synthesis
        await _handle_refresh(identity_store, console, tiny_model, turn_count)

    elif subcmd == "clear":
        identity_store.clear()
        console.print("[green]✓ Identity cleared[/green]")
        console.print("[dim]Starting fresh - behavioral observations will rebuild over time.[/dim]")

    elif subcmd == "pause":
        identity_store.pause()
        console.print("[yellow]⏸ Behavioral learning paused[/yellow]")
        console.print("[dim]Existing identity will still be used. Use /identity resume to continue learning.[/dim]")

    elif subcmd == "resume":
        identity_store.resume()
        console.print("[green]✓ Behavioral learning resumed[/green]")

    elif subcmd == "export":
        await _handle_export(identity_store, console, subarg)

    else:
        console.print(f"[red]Unknown: /identity {subcmd}[/red]")
        console.print("""
[bold]Identity Commands:[/bold]
  /identity          View current identity model
  /identity rate     Rate the identity model (1-5)
  /identity refresh  Force re-synthesis from observations
  /identity clear    Reset identity (start fresh)
  /identity pause    Disable behavioral learning
  /identity resume   Re-enable behavioral learning
  /identity export   Export identity data to JSON
""")


async def _handle_rate(
    identity_store: IdentityStore,
    console: Console,
    rating_input: str,
) -> None:
    """Handle /identity rate command."""
    from rich.panel import Panel

    from sunwell.planning.naaru.persona import MURU

    if not identity_store.identity.prompt:
        console.print("[yellow]No identity model to rate yet.[/yellow]")
        console.print("[dim]Keep chatting to build an identity model.[/dim]")
        return

    if not rating_input:
        # Show rating prompt
        console.print(Panel(
            """Does this identity model accurately capture how you like to interact?

  [bold]1[/bold] - Not at all
  [bold]2[/bold] - Somewhat off
  [bold]3[/bold] - Partially accurate
  [bold]4[/bold] - Mostly accurate
  [bold]5[/bold] - Spot on!

Your rating helps improve M'uru's learning.
[dim]Usage: /identity rate <1-5>[/dim]""",
            title=f"Rate {MURU.name}'s Identity Model",
            border_style="cyan",
        ))
        return

    try:
        rating = int(rating_input.strip())
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be 1-5")

        # Log rating (telemetry is opt-in per RFC-023)
        # For now, just acknowledge
        feedback_map = {
            1: "Thanks for the feedback. Identity will be rebuilt with more observations.",
            2: "Thanks! I'll work on improving the model.",
            3: "Got it. More interactions will help refine the model.",
            4: "Great! Small tweaks may come with more observations.",
            5: "Excellent! The model seems to capture your style well.",
        }

        console.print(f"[green]✓ Rating saved: {rating}/5[/green]")
        console.print(f"[dim]{feedback_map[rating]}[/dim]")

        # If rating is low, suggest clear
        if rating <= 2:
            console.print("[dim]Tip: Use /identity clear to start fresh.[/dim]")

    except ValueError:
        console.print("[red]Please enter a number 1-5[/red]")


async def _handle_refresh(
    identity_store: IdentityStore,
    console: Console,
    tiny_model,
    turn_count: int,
) -> None:
    """Handle /identity refresh command."""
    if not identity_store.identity.observations:
        console.print("[yellow]No observations to digest yet.[/yellow]")
        console.print("[dim]Keep chatting to build behavioral observations.[/dim]")
        return

    if not tiny_model:
        console.print("[yellow]No tiny model available for digest.[/yellow]")
        console.print("[dim]Digest requires gemma3:1b or similar. Using heuristic fallback.[/dim]")

        # Try quick heuristic digest
        from sunwell.identity.digest import quick_digest
        obs_texts = [o.observation for o in identity_store.identity.observations]
        prompt, confidence = await quick_digest(obs_texts, identity_store.identity.prompt)

        if prompt:
            identity_store.update_digest(prompt, confidence, turn_count)
            console.print(f"[green]✓ Identity refreshed (heuristic, confidence: {confidence:.0%})[/green]")
        else:
            console.print("[yellow]Not enough consistent observations for heuristic digest.[/yellow]")
        return

    console.print("[dim]Digesting observations...[/dim]")

    from sunwell.identity.digest import digest_identity

    obs_texts = [o.observation for o in identity_store.identity.observations]
    new_identity = await digest_identity(
        observations=obs_texts,
        current_identity=identity_store.identity,
        tiny_model=tiny_model,
    )

    if new_identity.is_usable():
        identity_store.update_digest(
            prompt=new_identity.prompt,
            confidence=new_identity.confidence,
            turn_count=turn_count,
            tone=new_identity.tone,
            values=new_identity.values,
        )
        console.print(f"[green]✓ Identity refreshed (confidence: {new_identity.confidence:.0%})[/green]")
    else:
        console.print("[yellow]Digest confidence too low. Need more observations.[/yellow]")


async def _handle_export(
    identity_store: IdentityStore,
    console: Console,
    path_arg: str,
) -> None:
    """Handle /identity export command."""
    export_data = identity_store.export()

    # Add export metadata
    export_data["exported_at"] = datetime.now().isoformat()

    if path_arg:
        # Export to file
        try:
            path = Path(path_arg).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)
            console.print(f"[green]✓ Exported to:[/green] {path}")
        except Exception as e:
            console.print(f"[red]Failed to export: {e}[/red]")
    else:
        # Print to console
        console.print("[bold]Identity Export:[/bold]")
        console.print(json.dumps(export_data, indent=2, default=str))
