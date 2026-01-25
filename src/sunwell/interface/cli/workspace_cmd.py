"""Workspace CLI commands for auto-detecting and linking source code (RFC-103).

Commands:
- sunwell workspace detect ~/my-docs  # Find related projects
- sunwell workspace link ~/my-docs --target ~/acme-api  # Link explicitly
- sunwell workspace unlink ~/my-docs --target ~/acme-api  # Remove link
- sunwell workspace show ~/my-docs  # Show current workspace config
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.group("workspace")
def workspace() -> None:
    """Manage workspace links for cross-reference features.

    \b
    Workspaces link documentation projects to their source code,
    enabling drift detection, API verification, and code example validation.

    \b
    Common patterns:
      Monorepo:   ~/acme/docs → ~/acme (parent)
      Polyrepo:   ~/acme-docs → ~/acme-api (sibling)
      Multi-repo: ~/docs → [~/backend, ~/frontend]
    """
    pass


@workspace.command("detect")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def detect(path: str, json_output: bool) -> None:
    """Detect related source code projects.

    \b
    Detection strategies:
      1. Parent directory (monorepo)
      2. Config file references (Sphinx conf.py, etc.)
      3. Git remote matching (same org)
      4. Sibling name matching

    \b
    Examples:
        sunwell workspace detect ~/my-docs
        sunwell workspace detect . --json
    """
    asyncio.run(_detect_async(path, json_output))


async def _detect_async(path: str, json_output: bool) -> None:
    """Async implementation of detect command."""
    import json

    from sunwell.analysis.workspace import WorkspaceDetector

    root = Path(path).expanduser().resolve()
    detector = WorkspaceDetector()

    if not json_output:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Detecting related projects...", total=None)
            links = await detector.detect(root)
    else:
        links = await detector.detect(root)

    if json_output:
        output = {"links": [link.to_dict() for link in links]}
        click.echo(json.dumps(output, indent=2))
        return

    if not links:
        console.print(
            Panel(
                "[yellow]No related projects detected.[/yellow]\n\n"
                "Try linking explicitly:\n"
                f"  sunwell workspace link {root} --target /path/to/source",
                title="Workspace Detection",
            )
        )
        return

    # Display results
    console.print(f"\n[bold]Found {len(links)} potential source code links:[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Confidence", justify="right", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Language", style="yellow")
    table.add_column("Evidence")

    for link in links:
        conf_pct = int(link.confidence * 100)
        conf_emoji = "🟢" if conf_pct >= 90 else "🟡" if conf_pct >= 70 else "🟠"
        table.add_row(
            f"{conf_emoji} {conf_pct}%",
            str(link.target.relative_to(root.parent))
            if link.target.is_relative_to(root.parent)
            else str(link.target),
            link.language or "unknown",
            link.evidence,
        )

    console.print(table)
    console.print("\n[bold]💡 To link a project:[/bold]")
    console.print(f"  sunwell workspace link {root} --target <path>")


@workspace.command("link")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--target",
    "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to source code to link",
)
def link(path: str, target: str) -> None:
    """Link a source code project to this documentation.

    \b
    Linking enables:
      - Drift detection (docs vs source)
      - API accuracy verification
      - Code example validation

    \b
    Examples:
        sunwell workspace link ~/my-docs --target ~/acme-api
        sunwell workspace link . -t ../
    """
    asyncio.run(_link_async(path, target))


async def _link_async(path: str, target: str) -> None:
    """Async implementation of link command."""
    from sunwell.analysis.workspace import (
        WorkspaceConfig,
        add_link,
        load_or_detect_workspace,
    )

    root = Path(path).expanduser().resolve()
    target_path = Path(target).expanduser().resolve()

    # Load or create workspace
    workspace, is_new = await load_or_detect_workspace(root, auto_detect=False)

    # Add the link
    workspace = add_link(workspace, target_path)

    # Save
    config = WorkspaceConfig(root)
    config.save(workspace)

    console.print(f"[green]✓[/green] Linked [cyan]{target_path}[/cyan] to workspace")
    console.print(f"[dim]Config saved to: {config.config_file}[/dim]")

    # Show next steps
    console.print("\n[bold]💡 Next steps:[/bold]")
    console.print(f"  sunwell scan {root}  [dim]# Scan with drift detection enabled[/dim]")
    console.print(f"  sunwell workspace show {root}  [dim]# View workspace config[/dim]")


@workspace.command("unlink")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--target",
    "-t",
    type=click.Path(),
    required=True,
    help="Path to source code to unlink",
)
def unlink(path: str, target: str) -> None:
    """Remove a linked source code project.

    \b
    Example:
        sunwell workspace unlink ~/my-docs --target ~/acme-api
    """
    asyncio.run(_unlink_async(path, target))


async def _unlink_async(path: str, target: str) -> None:
    """Async implementation of unlink command."""
    from sunwell.analysis.workspace import WorkspaceConfig, remove_link

    root = Path(path).expanduser().resolve()
    target_path = Path(target).expanduser().resolve()

    config = WorkspaceConfig(root)
    workspace = config.load()

    if not workspace:
        console.print(
            f"[yellow]No workspace config found at {root}[/yellow]\n"
            "Nothing to unlink."
        )
        return

    # Check if link exists
    if not any(lnk.target == target_path for lnk in workspace.links):
        console.print(
            f"[yellow]No link to {target_path} found in workspace.[/yellow]\n"
            "Use `sunwell workspace show` to see current links."
        )
        return

    # Remove the link
    workspace = remove_link(workspace, target_path)
    config.save(workspace)

    console.print(f"[green]✓[/green] Unlinked [cyan]{target_path}[/cyan] from workspace")


@workspace.command("show")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def show(path: str, json_output: bool) -> None:
    """Show current workspace configuration.

    \b
    Example:
        sunwell workspace show ~/my-docs
        sunwell workspace show . --json
    """
    asyncio.run(_show_async(path, json_output))


async def _show_async(path: str, json_output: bool) -> None:
    """Async implementation of show command."""
    import json

    from sunwell.analysis.workspace import WorkspaceConfig

    root = Path(path).expanduser().resolve()
    config = WorkspaceConfig(root)
    workspace = config.load()

    if json_output:
        if workspace:
            click.echo(json.dumps(workspace.to_dict(), indent=2))
        else:
            click.echo(json.dumps({"error": "No workspace config found"}, indent=2))
        return

    if not workspace:
        console.print(
            Panel(
                f"[yellow]No workspace config found at {root}[/yellow]\n\n"
                "Run detection first:\n"
                f"  sunwell workspace detect {root}",
                title="Workspace",
            )
        )
        return

    # Display workspace info
    topology_emoji = {
        "monorepo": "📦",
        "polyrepo": "🔗",
        "hybrid": "🌐",
    }

    summary = f"""[bold]Workspace:[/bold] {workspace.primary}
[bold]Topology:[/bold] {topology_emoji.get(workspace.topology, '❓')} {workspace.topology}
[bold]ID:[/bold] {workspace.id}
[bold]Created:[/bold] {workspace.created_at.strftime('%Y-%m-%d %H:%M')}
[bold]Updated:[/bold] {workspace.updated_at.strftime('%Y-%m-%d %H:%M')}"""

    console.print(Panel(summary, title="[bold]Workspace Configuration[/bold]"))

    if workspace.links:
        console.print(f"\n[bold]Links ({len(workspace.links)}):[/bold]\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Target", style="cyan")
        table.add_column("Language", style="yellow")
        table.add_column("Confidence", justify="right")
        table.add_column("Evidence")

        for link in workspace.links:
            status = "✓" if link.confirmed else "?"
            status_color = "green" if link.confirmed else "yellow"
            conf_pct = int(link.confidence * 100)

            table.add_row(
                f"[{status_color}]{status}[/{status_color}]",
                str(link.target),
                link.language or "unknown",
                f"{conf_pct}%",
                link.evidence[:40] + ("..." if len(link.evidence) > 40 else ""),
            )

        console.print(table)

        # Show source symbols if available
        confirmed_count = len([lnk for lnk in workspace.links if lnk.confirmed])
        if confirmed_count > 0:
            console.print(
                f"\n[dim]✓ {confirmed_count} confirmed link(s) - drift detection enabled[/dim]"
            )
        else:
            console.print(
                "\n[yellow]⚠ No confirmed links - drift detection disabled[/yellow]\n"
                "Confirm a link with:\n"
                f"  sunwell workspace link {root} --target <path>"
            )
    else:
        console.print("\n[yellow]No links configured.[/yellow]")
        console.print(
            "\nRun detection to find related projects:\n"
            f"  sunwell workspace detect {root}"
        )


@workspace.command("clear")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def clear(path: str, yes: bool) -> None:
    """Clear workspace configuration.

    \b
    Example:
        sunwell workspace clear ~/my-docs
    """
    from sunwell.analysis.workspace import WorkspaceConfig

    root = Path(path).expanduser().resolve()
    config = WorkspaceConfig(root)

    if not config.exists():
        console.print(f"[yellow]No workspace config to clear at {root}[/yellow]")
        return

    if not yes and not click.confirm(f"Clear workspace config for {root}?"):
        console.print("[dim]Cancelled[/dim]")
        return

    config.delete()
    console.print("[green]✓[/green] Workspace config cleared")
