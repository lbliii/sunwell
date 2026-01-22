"""Briefing command group — Manage rolling handoff notes (RFC-071).

The briefing provides instant orientation at session start, acting as
"Twitter for LLMs" where the character constraint enforces salience.
"""


import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from sunwell.memory.briefing import Briefing, BriefingStatus

console = Console()


@click.group()
def briefing() -> None:
    """Manage rolling handoff notes for agent continuity.

    The briefing is a compressed "where are we now" that provides instant
    orientation at session start. Unlike accumulated learnings (which grow
    over time), the briefing is OVERWRITTEN each session.

    \b
    Commands:
      show   - Display current briefing
      clear  - Remove briefing to start fresh
      create - Manually create a briefing
      json   - Output briefing as JSON
    """
    pass


@briefing.command("show")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Project path (default: current directory)",
)
def briefing_show(path: str) -> None:
    """Display the current briefing for a project.

    Shows the rolling handoff note including mission, status, progress,
    momentum (last/next action), hazards, and focus files.

    \b
    Examples:
        sunwell briefing show
        sunwell briefing show --path ~/projects/my-app
    """
    project_path = Path(path)
    briefing_obj = Briefing.load(project_path)

    if not briefing_obj:
        console.print("[yellow]No briefing found.[/yellow]")
        console.print(f"[dim]Looking in: {project_path / '.sunwell' / 'memory' / 'briefing.json'}[/dim]")
        console.print("\n[dim]Tip: A briefing is created automatically when you run a goal.[/dim]")
        return

    # Status colors
    status_colors = {
        BriefingStatus.NOT_STARTED: "gray",
        BriefingStatus.IN_PROGRESS: "blue",
        BriefingStatus.BLOCKED: "red",
        BriefingStatus.COMPLETE: "green",
    }
    status_color = status_colors.get(briefing_obj.status, "white")

    # Build content
    lines = []
    lines.append(f"[bold]Mission:[/bold] {briefing_obj.mission}")
    lines.append(f"[bold]Status:[/bold] [{status_color}]{briefing_obj.status.value.replace('_', ' ').title()}[/{status_color}]")
    lines.append(f"[bold]Progress:[/bold] {briefing_obj.progress}")
    lines.append("")
    lines.append(f"[bold]Last Action:[/bold] {briefing_obj.last_action}")
    if briefing_obj.next_action:
        lines.append(f"[bold]Next Action:[/bold] [cyan]{briefing_obj.next_action}[/cyan]")

    if briefing_obj.hazards:
        lines.append("")
        lines.append("[bold yellow]⚠️ Hazards:[/bold yellow]")
        for h in briefing_obj.hazards:
            lines.append(f"  • {h}")

    if briefing_obj.blockers:
        lines.append("")
        lines.append("[bold red]🚫 Blockers:[/bold red]")
        for b in briefing_obj.blockers:
            lines.append(f"  • {b}")

    if briefing_obj.hot_files:
        lines.append("")
        lines.append(f"[bold]Focus Files:[/bold] {', '.join(f'[cyan]{f}[/cyan]' for f in briefing_obj.hot_files)}")

    # Dispatch hints
    if briefing_obj.predicted_skills or briefing_obj.suggested_lens:
        lines.append("")
        lines.append("[bold]🎯 Dispatch Hints:[/bold]")
        if briefing_obj.suggested_lens:
            lines.append(f"  • Lens: [magenta]{briefing_obj.suggested_lens}[/magenta]")
        if briefing_obj.predicted_skills:
            lines.append(f"  • Skills: {', '.join(briefing_obj.predicted_skills)}")
        if briefing_obj.complexity_estimate:
            lines.append(f"  • Complexity: {briefing_obj.complexity_estimate}")

    # Footer
    lines.append("")
    lines.append(f"[dim]Updated: {briefing_obj.updated_at[:19].replace('T', ' ')}[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold]Current Briefing[/bold]",
        border_style="blue",
    )
    console.print(panel)


@briefing.command("clear")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Project path (default: current directory)",
)
@click.confirmation_option(prompt="Are you sure you want to clear the briefing?")
def briefing_clear(path: str) -> None:
    """Remove the briefing to start fresh.

    This deletes the briefing.json file. A new briefing will be created
    automatically on the next agent run.

    \b
    Examples:
        sunwell briefing clear
        sunwell briefing clear --path ~/projects/my-app
    """
    project_path = Path(path)
    briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"

    if not briefing_path.exists():
        console.print("[yellow]No briefing found to clear.[/yellow]")
        return

    briefing_path.unlink()
    console.print("[green]✓ Briefing cleared.[/green]")
    console.print("[dim]A new briefing will be created on the next agent run.[/dim]")


@briefing.command("create")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Project path (default: current directory)",
)
@click.option("--mission", "-m", required=True, help="What you're trying to accomplish")
@click.option("--progress", default="Starting fresh.", help="Brief progress summary")
@click.option("--next-action", "-n", help="What should happen next")
@click.option("--hazard", "-h", multiple=True, help="Things to avoid (can specify multiple)")
@click.option("--hot-file", "-f", multiple=True, help="Files currently relevant (can specify multiple)")
def briefing_create(
    path: str,
    mission: str,
    progress: str,
    next_action: str | None,
    hazard: tuple[str, ...],
    hot_file: tuple[str, ...],
) -> None:
    """Manually create a briefing.

    This creates or overwrites the current briefing with the provided values.
    Useful for setting up orientation before starting work.

    \b
    Examples:
        sunwell briefing create -m "Build user authentication"

        sunwell briefing create \\
          -m "Build REST API" \\
          -n "Add POST /users endpoint" \\
          -h "Don't use deprecated auth library" \\
          -f "src/api.py" -f "src/models.py"
    """
    project_path = Path(path)

    briefing_obj = Briefing(
        mission=mission,
        status=BriefingStatus.NOT_STARTED if progress == "Starting fresh." else BriefingStatus.IN_PROGRESS,
        progress=progress,
        last_action="Briefing created manually.",
        next_action=next_action or "Begin planning.",
        hazards=tuple(hazard) if hazard else (),
        hot_files=tuple(hot_file) if hot_file else (),
    )

    briefing_obj.save(project_path)
    console.print("[green]✓ Briefing created.[/green]")
    console.print(f"[dim]Saved to: {project_path / '.sunwell' / 'memory' / 'briefing.json'}[/dim]")


@briefing.command("json")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Project path (default: current directory)",
)
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output")
def briefing_json(path: str, pretty: bool) -> None:
    """Output the briefing as JSON.

    Useful for scripting and integration with other tools.

    \b
    Examples:
        sunwell briefing json
        sunwell briefing json --pretty
        sunwell briefing json | jq .mission
    """
    project_path = Path(path)
    briefing_obj = Briefing.load(project_path)

    if not briefing_obj:
        # Output empty object for scripting compatibility
        click.echo("{}")
        return

    output = briefing_obj.to_dict()
    if pretty:
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(json.dumps(output))


@briefing.command("prompt")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Project path (default: current directory)",
)
def briefing_prompt(path: str) -> None:
    """Output the briefing in prompt format.

    Shows the briefing formatted for injection into an LLM prompt.
    This is what the agent sees at session start.

    \b
    Examples:
        sunwell briefing prompt
        sunwell briefing prompt --path ~/projects/my-app
    """
    project_path = Path(path)
    briefing_obj = Briefing.load(project_path)

    if not briefing_obj:
        console.print("[yellow]No briefing found.[/yellow]")
        return

    click.echo(briefing_obj.to_prompt())
