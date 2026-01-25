"""Scan command for building State DAGs from existing projects (RFC-100).

The scan command enables brownfield workflows:
1. Scan existing project: `sunwell scan ~/my-docs`
2. View health in Studio or CLI
3. Click red nodes to give intent and spawn Execution DAGs

This covers ~95% of real-world work (improving existing projects).
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

console = Console()


@click.command("scan")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--lens", "-l",
    type=str,
    default=None,
    help="Lens to use for scanning (auto-detected if not specified)",
)
@click.option(
    "--json", "json_output",
    is_flag=True,
    help="Output as JSON (for CI/scripting)",
)
@click.option(
    "--open", "open_studio",
    is_flag=True,
    help="Open results in Studio",
)
@click.option(
    "--save", "-s",
    type=click.Path(),
    default=None,
    help="Save State DAG to file",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output including all nodes",
)
@click.option(
    "--link",
    type=click.Path(exists=True),
    multiple=True,
    help="Link source code path for drift detection (RFC-103). Can be used multiple times.",
)
@click.option(
    "--no-detect",
    is_flag=True,
    help="Disable workspace auto-detection (RFC-103)",
)
def scan(
    path: str,
    lens: str | None,
    json_output: bool,
    open_studio: bool,
    save: str | None,
    verbose: bool,
    link: tuple[str, ...],
    no_detect: bool,
) -> None:
    """Scan an existing project and build a State DAG.

    \b
    The State DAG shows "what exists and its health":
    - 🟢 Healthy (90-100%)
    - 🟡 Needs review (70-89%)
    - 🟠 Issues found (50-69%)
    - 🔴 Critical (< 50%)

    \b
    Examples:
        sunwell scan                    # Scan current directory
        sunwell scan ~/my-docs          # Scan specific path
        sunwell scan . --lens tech-writer.lens  # Use specific lens
        sunwell scan . --json           # Output as JSON
        sunwell scan . --open           # Open in Studio

    \b
    RFC-103 Workspace-aware scanning:
        sunwell scan ~/my-docs --link ~/my-code    # Link source for drift detection
        sunwell scan . --no-detect                 # Skip auto-detection

    \b
    The scan auto-detects project type:
        - conf.py, mkdocs.yml → Documentation project
        - pyproject.toml, package.json → Code project
    """
    asyncio.run(_scan_async(
        path=path,
        lens_name=lens,
        json_output=json_output,
        open_studio=open_studio,
        save=save,
        verbose=verbose,
        link_paths=link,
        no_detect=no_detect,
    ))


async def _scan_async(
    path: str,
    lens_name: str | None,
    json_output: bool,
    open_studio: bool,
    save: str | None,
    verbose: bool,
    link_paths: tuple[str, ...] = (),
    no_detect: bool = False,
) -> None:
    """Async implementation of scan command."""
    from sunwell.analysis import scan_project
    from sunwell.analysis.source_context import SourceContext
    from sunwell.analysis.workspace import (
        WorkspaceConfig,
        WorkspaceDetector,
    )

    root = Path(path).expanduser().resolve()

    if not root.exists():
        console.print(f"[red]Error: Path does not exist: {root}[/red]")
        return

    # Load lens if specified
    lens = None
    if lens_name:
        try:
            from sunwell.lens.loader import load_lens
            lens = await load_lens(lens_name)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load lens '{lens_name}': {e}[/yellow]")

    # RFC-103: Build source contexts from workspace links
    source_contexts = []

    # Check for explicit links first
    if link_paths:
        for link_path in link_paths:
            link_root = Path(link_path).expanduser().resolve()
            if not json_output:
                console.print(f"[dim]Indexing source: {link_root}[/dim]")
            try:
                ctx = await SourceContext.build(link_root)
                source_contexts.append(ctx)
                if not json_output:
                    console.print(f"[dim]  → {ctx.symbol_count} symbols indexed[/dim]")
            except Exception as e:
                if not json_output:
                    console.print(f"[yellow]Warning: Could not index {link_root}: {e}[/yellow]")

    # Try to load existing workspace config
    workspace_config = WorkspaceConfig(root)
    existing_workspace = workspace_config.load()

    if existing_workspace and existing_workspace.confirmed_links and not link_paths:
        # Use confirmed links from workspace config
        if not json_output and verbose:
            link_count = len(existing_workspace.confirmed_links)
            console.print(f"[dim]Using workspace config with {link_count} links[/dim]")
        for link in existing_workspace.confirmed_links:
            try:
                ctx = await SourceContext.build(link.target)
                source_contexts.append(ctx)
            except Exception as e:
                if not json_output:
                    console.print(f"[yellow]Warning: Could not index {link.target}: {e}[/yellow]")

    # Auto-detect workspace if no explicit links and not disabled
    elif not link_paths and not no_detect and not existing_workspace:
        detector = WorkspaceDetector()
        detected = await detector.detect(root)
        high_confidence = [lnk for lnk in detected if lnk.confidence >= 0.90]

        if high_confidence and not json_output:
            console.print(
                "\n[cyan]💡 Found related projects "
                "(use --link to enable drift detection):[/cyan]"
            )
            for link in high_confidence[:3]:
                console.print(f"   {link.confidence*100:.0f}% {link.target.name} ({link.language})")
            console.print(f"   [dim]Run: sunwell workspace link {root} --target <path>[/dim]\n")

    # Build State DAG with progress indicator
    if not json_output:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            desc = "Scanning project..."
            if source_contexts:
                desc = f"Scanning project (drift detection: {len(source_contexts)} sources)..."
            progress.add_task(description=desc, total=None)
            dag = await scan_project(root, lens, source_contexts)
    else:
        dag = await scan_project(root, lens, source_contexts)

    # RFC-104: Update environment with scan results
    _update_environment_from_dag(root, dag, json_output)

    # JSON output
    if json_output:
        click.echo(dag.to_json())
        return

    # Save to file if requested
    if save:
        save_path = Path(save)
        save_path.write_text(dag.to_json())
        console.print(f"[green]Saved State DAG to {save_path}[/green]")

    # Display results
    _display_results(dag, verbose)

    # Open in Studio if requested
    if open_studio:
        _open_in_studio(dag, root)


def _display_results(dag, verbose: bool) -> None:
    """Display scan results in a rich format."""

    # Summary panel
    overall = dag.overall_health * 100
    if overall >= 90:
        health_emoji = "🟢"
        health_color = "green"
    elif overall >= 70:
        health_emoji = "🟡"
        health_color = "yellow"
    elif overall >= 50:
        health_emoji = "🟠"
        health_color = "orange1"
    else:
        health_emoji = "🔴"
        health_color = "red"

    unhealthy = len(dag.unhealthy_nodes)
    critical = len(dag.critical_nodes)
    summary = f"""[bold]Project:[/bold] {dag.root}
[bold]Overall Health:[/bold] {health_emoji} {overall:.0f}%
[bold]Nodes:[/bold] {len(dag.nodes)} | [bold]Edges:[/bold] {len(dag.edges)}
[bold]Unhealthy:[/bold] {unhealthy} | [bold]Critical:[/bold] {critical}"""

    if dag.lens_name:
        summary += f"\n[bold]Lens:[/bold] {dag.lens_name}"

    console.print(Panel(summary, title="[bold]State DAG Scan[/bold]", border_style=health_color))

    # Show critical nodes first
    if dag.critical_nodes:
        console.print("\n[bold red]🔴 Critical Issues[/bold red]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Health", justify="right")
        table.add_column("Issues", style="red")

        for node in sorted(dag.critical_nodes, key=lambda n: n.health_score)[:10]:
            issues = [p.issues[0] for p in node.health_probes if p.issues][:2]
            issues_str = "; ".join(issues) if issues else "-"
            table.add_row(
                str(node.path.relative_to(dag.root)),
                f"{node.health_score * 100:.0f}%",
                issues_str[:60] + ("..." if len(issues_str) > 60 else ""),
            )

        console.print(table)

    # Show unhealthy nodes (but not critical)
    unhealthy_not_critical = [n for n in dag.unhealthy_nodes if n not in dag.critical_nodes]
    if unhealthy_not_critical:
        console.print("\n[bold yellow]🟡 Needs Attention[/bold yellow]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Health", justify="right")
        table.add_column("Issues", style="yellow")

        for node in sorted(unhealthy_not_critical, key=lambda n: n.health_score)[:10]:
            issues = [p.issues[0] for p in node.health_probes if p.issues][:2]
            issues_str = "; ".join(issues) if issues else "-"
            table.add_row(
                str(node.path.relative_to(dag.root)),
                f"{node.health_score * 100:.0f}%",
                issues_str[:60] + ("..." if len(issues_str) > 60 else ""),
            )

        console.print(table)
        if len(unhealthy_not_critical) > 10:
            console.print(f"[dim]... and {len(unhealthy_not_critical) - 10} more[/dim]")

    # Show all nodes in verbose mode
    if verbose:
        console.print("\n[bold]All Nodes[/bold]")
        tree = Tree(f"📁 {dag.root.name}")
        _build_tree(tree, dag, dag.root)
        console.print(tree)

    # Next steps
    console.print("\n[bold]💡 Next steps:[/bold]")
    if dag.critical_nodes:
        console.print(f"  • Fix {len(dag.critical_nodes)} critical issues")
    if dag.unhealthy_nodes:
        console.print(f"  • Review {len(dag.unhealthy_nodes)} unhealthy nodes")
    console.print(f'  • sunwell scan {dag.root} --open [dim]View in Studio[/dim]')
    console.print(f'  • sunwell "Fix issues in {dag.root.name}" [dim]Auto-fix with agent[/dim]')


def _build_tree(parent, dag, root: Path) -> None:
    """Build a rich Tree from the State DAG."""
    # Group nodes by directory
    by_dir: dict[Path, list] = {}
    for node in dag.nodes:
        if node.artifact_type == "directory" or node.artifact_type == "package":
            continue
        parent_dir = node.path.parent
        if parent_dir not in by_dir:
            by_dir[parent_dir] = []
        by_dir[parent_dir].append(node)

    # Build tree structure
    for dir_path in sorted(by_dir.keys()):
        try:
            rel_dir = dir_path.relative_to(root)
            dir_branch = parent if str(rel_dir) == "." else parent.add(f"📁 {rel_dir}")
        except ValueError:
            continue

        for node in sorted(by_dir[dir_path], key=lambda n: n.path.name):
            health = node.health_score * 100
            if health >= 90:
                emoji = "🟢"
            elif health >= 70:
                emoji = "🟡"
            elif health >= 50:
                emoji = "🟠"
            else:
                emoji = "🔴"

            dir_branch.add(f"{emoji} {node.path.name} ({health:.0f}%)")


def _open_in_studio(dag, root: Path) -> None:
    """Open the State DAG in Studio."""

    from sunwell.cli.open_cmd import launch_studio

    # Save State DAG for Studio to load
    sunwell_dir = root / ".sunwell"
    sunwell_dir.mkdir(exist_ok=True)

    dag_file = sunwell_dir / "state-dag.json"
    dag_file.write_text(dag.to_json())

    console.print("\n[cyan]Opening State DAG in Studio...[/cyan]")

    # Launch Studio with state DAG mode
    launch_studio(
        project=str(root),
        lens="auto",
        mode="state-dag",
        plan_file=str(dag_file),
    )


def _update_environment_from_dag(root: Path, dag, json_output: bool) -> None:
    """Update user environment with scan results (RFC-104).

    Automatically adds/updates the scanned project in the user's
    environment catalog with health score and scan timestamp.

    Args:
        root: Project root path.
        dag: The StateDag from the scan.
        json_output: If True, suppress non-JSON output.
    """
    try:
        from sunwell.environment import (
            create_project_entry_from_path,
            load_environment,
            save_environment,
        )

        env = load_environment()
        existing = env.get_project(root)

        if existing:
            # Update existing project with new health info
            updated = existing.with_health(dag.overall_health, dag.scanned_at)
            env.add_project(updated)
        else:
            # Create new entry
            entry = create_project_entry_from_path(root)
            if entry:
                updated = entry.with_health(dag.overall_health, dag.scanned_at)
                env.add_project(updated)

        save_environment(env)

        if not json_output:
            health_pct = dag.overall_health * 100
            console.print(
                f"[dim]Environment updated: {root.name} "
                f"({health_pct:.0f}% health)[/dim]"
            )

    except Exception as e:
        # Don't fail the scan if environment update fails
        if not json_output:
            console.print(f"[dim]Could not update environment: {e}[/dim]")
