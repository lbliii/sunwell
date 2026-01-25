"""Workspace CLI commands for auto-detecting and linking source code (RFC-103).

Also includes workspace management commands (RFC-140):
- sunwell workspace list          # List all workspaces
- sunwell workspace current       # Show current workspace
- sunwell workspace switch <id>   # Switch to workspace
- sunwell workspace discover      # Scan filesystem for workspaces
- sunwell workspace status        # Show workspace health/status
- sunwell workspace info <id>     # Detailed workspace info

Legacy commands (RFC-103):
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
    """Manage workspaces and workspace links (RFC-103, RFC-140).

    \b
    Workspace Management (RFC-140):
      - List, discover, and switch between workspaces
      - Track current workspace context
      - View workspace status and health

    \b
    Workspace Linking (RFC-103):
      - Link documentation projects to source code
      - Enable drift detection and API verification

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

    from sunwell.knowledge import WorkspaceDetector

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
    from sunwell.knowledge import (
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
    from sunwell.knowledge import WorkspaceConfig, remove_link

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

    from sunwell.knowledge import WorkspaceConfig

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
    from sunwell.knowledge import WorkspaceConfig

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


# ═══════════════════════════════════════════════════════════════
# RFC-140: Workspace Management Commands
# ═══════════════════════════════════════════════════════════════


@workspace.command("list")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def list_workspaces(json_output: bool) -> None:
    """List all workspaces (registered + discovered) (RFC-140).

    Shows workspaces sorted by: current first, then registered, then by last_used.

    \b
    Examples:
        sunwell workspace list
        sunwell workspace list --json
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    workspaces = manager.discover_workspaces()
    current = manager.get_current()

    if json_output:
        import json

        output = {
            "workspaces": [
                {
                    "id": w.id,
                    "name": w.name,
                    "path": str(w.path),
                    "is_registered": w.is_registered,
                    "is_current": w.is_current,
                    "status": w.status.value,
                    "workspace_type": w.workspace_type,
                    "last_used": w.last_used,
                }
                for w in workspaces
            ],
            "current": {
                "id": current.id,
                "name": current.name,
                "path": str(current.path),
                "is_registered": current.is_registered,
                "status": current.status.value,
                "workspace_type": current.workspace_type,
            }
            if current
            else None,
        }
        click.echo(json.dumps(output, indent=2))
        return

    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        console.print("\nDiscover workspaces with:")
        console.print("  [cyan]sunwell workspace discover[/cyan]")
        return

    console.print()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Current", justify="center", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("Name")
    table.add_column("Path", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Type", style="yellow")

    for w in workspaces:
        current_marker = "●" if w.is_current else ""
        status_emoji = {
            "valid": "✓",
            "invalid": "✗",
            "not_found": "?",
            "unregistered": "○",
        }.get(w.status.value, "?")

        table.add_row(
            current_marker,
            w.id,
            w.name,
            str(w.path),
            status_emoji,
            w.workspace_type,
        )

    console.print(table)
    if current:
        console.print(f"\n[bold]Current workspace:[/bold] [cyan]{current.name}[/cyan] ({current.id})")


@workspace.command("current")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def current_workspace(json_output: bool) -> None:
    """Show current workspace (RFC-140).

    \b
    Examples:
        sunwell workspace current
        sunwell workspace current --json
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    current = manager.get_current()

    if json_output:
        import json

        if current:
            output = {
                "id": current.id,
                "name": current.name,
                "path": str(current.path),
                "is_registered": current.is_registered,
                "status": current.status.value,
                "workspace_type": current.workspace_type,
                "last_used": current.last_used,
            }
        else:
            output = None
        click.echo(json.dumps(output, indent=2))
        return

    if not current:
        console.print("[yellow]No current workspace set.[/yellow]")
        console.print("\nSet a workspace with:")
        console.print("  [cyan]sunwell workspace switch <id>[/cyan]")
        return

    console.print()
    console.print(f"[bold]Current Workspace:[/bold] [cyan]{current.name}[/cyan]")
    console.print(f"  ID: {current.id}")
    console.print(f"  Path: {current.path}")
    console.print(f"  Status: {current.status.value}")
    console.print(f"  Type: {current.workspace_type}")
    console.print(f"  Registered: {'Yes' if current.is_registered else 'No'}")
    if current.last_used:
        console.print(f"  Last used: {current.last_used}")


@workspace.command("switch")
@click.argument("workspace_id")
def switch_workspace(workspace_id: str) -> None:
    """Switch to a workspace (RFC-140).

    Sets the workspace as current and updates last_used if registered.

    \b
    Examples:
        sunwell workspace switch my-app
        sunwell workspace switch /path/to/workspace
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()

    try:
        workspace_info = manager.switch_workspace(workspace_id)
        console.print(f"[green]✓[/green] Switched to workspace: [cyan]{workspace_info.name}[/cyan]")
        console.print(f"  Path: {workspace_info.path}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None


@workspace.command("discover")
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False),
    help="Root directory to scan (defaults to common locations)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def discover_workspaces(root: str | None, json_output: bool) -> None:
    """Scan filesystem for workspaces (RFC-140).

    Scans common locations and project markers to find workspaces.

    \b
    Examples:
        sunwell workspace discover
        sunwell workspace discover --root ~/Projects
        sunwell workspace discover --json
    """
    from pathlib import Path

    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    scan_root = Path(root).resolve() if root else None

    if not json_output:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Discovering workspaces...", total=None)
            workspaces = manager.discover_workspaces(scan_root)
    else:
        workspaces = manager.discover_workspaces(scan_root)

    if json_output:
        import json

        output = {
            "workspaces": [
                {
                    "id": w.id,
                    "name": w.name,
                    "path": str(w.path),
                    "is_registered": w.is_registered,
                    "is_current": w.is_current,
                    "status": w.status.value,
                    "workspace_type": w.workspace_type,
                    "last_used": w.last_used,
                }
                for w in workspaces
            ]
        }
        click.echo(json.dumps(output, indent=2))
        return

    if not workspaces:
        console.print("[yellow]No workspaces discovered.[/yellow]")
        return

    console.print(f"\n[bold]Discovered {len(workspaces)} workspace(s):[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Current", justify="center", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("Name")
    table.add_column("Path", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Registered", justify="center")

    for w in workspaces:
        current_marker = "●" if w.is_current else ""
        status_emoji = {
            "valid": "✓",
            "invalid": "✗",
            "not_found": "?",
            "unregistered": "○",
        }.get(w.status.value, "?")

        table.add_row(
            current_marker,
            w.id,
            w.name,
            str(w.path),
            status_emoji,
            "Yes" if w.is_registered else "No",
        )

    console.print(table)


@workspace.command("status")
@click.argument("path", type=click.Path(exists=True), default=".")
def workspace_status(path: str) -> None:
    """Show workspace health/status (RFC-140).

    \b
    Examples:
        sunwell workspace status
        sunwell workspace status /path/to/workspace
    """
    from pathlib import Path

    from sunwell.knowledge.workspace import WorkspaceManager, WorkspaceStatus

    workspace_path = Path(path).expanduser().resolve()
    manager = WorkspaceManager()
    status = manager.get_status(workspace_path)

    status_emoji = {
        "valid": "✓",
        "invalid": "✗",
        "not_found": "?",
        "unregistered": "○",
    }.get(status.value, "?")

    console.print()
    console.print(f"[bold]Workspace Status:[/bold] {status_emoji} [cyan]{status.value}[/cyan]")
    console.print(f"  Path: {workspace_path}")

    if status == WorkspaceStatus.VALID:
        console.print("[green]Workspace is valid and ready to use.[/green]")
    elif status == WorkspaceStatus.INVALID:
        console.print("[yellow]Workspace exists but is invalid.[/yellow]")
        console.print("  Run validation to see details:")
        console.print(f"  [cyan]sunwell project validate {workspace_path}[/cyan]")
    elif status == WorkspaceStatus.NOT_FOUND:
        console.print("[red]Workspace path does not exist.[/red]")
    else:
        console.print("[yellow]Workspace is not registered.[/yellow]")
        console.print("  Register it with:")
        console.print(f"  [cyan]sunwell project init {workspace_path}[/cyan]")


@workspace.command("info")
@click.argument("workspace_id")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def workspace_info(workspace_id: str, json_output: bool) -> None:
    """Show detailed workspace information (RFC-140).

    \b
    Examples:
        sunwell workspace info my-app
        sunwell workspace info /path/to/workspace
        sunwell workspace info my-app --json
    """
    from pathlib import Path

    from sunwell.knowledge.workspace import WorkspaceInfo, WorkspaceManager

    manager = WorkspaceManager()

    # Try to find workspace
    workspaces = manager.discover_workspaces()
    matching = [w for w in workspaces if w.id == workspace_id or str(w.path) == workspace_id]

    if not matching:
        # Try as path
        try:
            workspace_path = Path(workspace_id).resolve()
            if workspace_path.exists():
                from sunwell.knowledge.project import ProjectRegistry

                registry = ProjectRegistry()
                project = registry.find_by_root(workspace_path)

                if project:
                    current = manager.get_current()
                    is_current = current is not None and current.path.resolve() == workspace_path.resolve()
                    status = manager.get_status(workspace_path)
                    last_used = registry.projects.get(project.id, {}).get("last_used")

                    info = WorkspaceInfo(
                        id=project.id,
                        name=project.name,
                        path=project.root,
                        is_registered=True,
                        is_current=is_current,
                        status=status,
                        workspace_type=project.workspace_type.value,
                        last_used=last_used,
                        project=project,
                    )
                else:
                    current = manager.get_current()
                    is_current = current is not None and current.path.resolve() == workspace_path.resolve()
                    status = manager.get_status(workspace_path)

                    info = WorkspaceInfo(
                        id=workspace_path.name.lower().replace(" ", "-"),
                        name=workspace_path.name,
                        path=workspace_path,
                        is_registered=False,
                        is_current=is_current,
                        status=status,
                        workspace_type="discovered",
                    )
                matching = [info]
        except Exception:
            pass

    if not matching:
        console.print(f"[red]Workspace not found:[/red] {workspace_id}")
        raise SystemExit(1)

    info = matching[0]

    if json_output:
        import json

        output = {
            "id": info.id,
            "name": info.name,
            "path": str(info.path),
            "is_registered": info.is_registered,
            "is_current": info.is_current,
            "status": info.status.value,
            "workspace_type": info.workspace_type,
            "last_used": info.last_used,
        }
        if info.project:
            output["project"] = {
                "id": info.project.id,
                "name": info.project.name,
                "root": str(info.project.root),
                "trust_level": info.project.trust_level,
            }
        click.echo(json.dumps(output, indent=2))
        return

    console.print()
    console.print(f"[bold]Workspace Information:[/bold] [cyan]{info.name}[/cyan]")
    console.print(f"  ID: {info.id}")
    console.print(f"  Path: {info.path}")
    console.print(f"  Status: {info.status.value}")
    console.print(f"  Type: {info.workspace_type}")
    console.print(f"  Registered: {'Yes' if info.is_registered else 'No'}")
    console.print(f"  Current: {'Yes' if info.is_current else 'No'}")
    if info.last_used:
        console.print(f"  Last used: {info.last_used}")

    if info.project:
        console.print()
        console.print("[bold]Project Details:[/bold]")
        console.print(f"  Trust level: {info.project.trust_level}")
        console.print(f"  Protected paths: {', '.join(info.project.protected_paths) or 'None'}")

