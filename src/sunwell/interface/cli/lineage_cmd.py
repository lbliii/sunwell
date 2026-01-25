"""Lineage command group - Artifact lineage tracking (RFC-121).

Provides commands to query artifact provenance:
- Show lineage for a file
- Query artifacts by goal
- View dependency graph
- Impact analysis
- Initialize/sync lineage
"""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


@click.group()
def lineage() -> None:
    """Artifact lineage and provenance tracking.

    Track the complete lineage of every artifact: which goal spawned it,
    which model wrote it, what edits were made, and how it relates to other files.

    \b
    Examples:
        sunwell lineage show src/auth.py
        sunwell lineage goal abc123
        sunwell lineage deps src/api.py
        sunwell lineage impact src/base.py
        sunwell lineage sync
    """
    pass


@lineage.command("show")
@click.argument("path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_show(path: str, json_output: bool, workspace: str) -> None:
    """Show lineage for a file.

    Displays creation info, edit history, model attribution, and dependencies.

    \b
    Examples:
        sunwell lineage show src/auth/oauth.py
        sunwell lineage show src/api/routes.py --json
    """
    import json

    from sunwell.memory.lineage import LineageStore

    store = LineageStore(Path(workspace))
    artifact = store.get_by_path(path)

    if not artifact:
        console.print(f"[yellow]No lineage found for {path}[/yellow]")
        console.print("[dim]This file was not created/tracked by Sunwell.[/dim]")
        return

    if json_output:
        print(json.dumps(artifact.to_dict(), indent=2, default=str))
        return

    # Rich display
    _display_lineage(artifact, path)


def _display_lineage(artifact, path: str) -> None:
    """Display artifact lineage in rich format."""
    from datetime import datetime

    # Header
    header_parts = [f"📜 {path}"]
    if artifact.human_edited:
        header_parts.append("[yellow](Human Edited)[/yellow]")

    console.print(Panel(" ".join(header_parts), border_style="blue"))

    # Creation info
    console.print("\n[bold]Created:[/bold]")
    if artifact.created_by_goal:
        console.print(f"  Goal: {artifact.created_by_goal}")
    else:
        console.print("  [dim]Pre-existing file (not created by Sunwell)[/dim]")

    console.print(f"  Reason: {artifact.created_reason}")
    console.print(f"  Time: {artifact.created_at.strftime('%Y-%m-%d %H:%M')}")
    if artifact.model:
        console.print(f"  Model: {artifact.model}")

    # Edit history
    if artifact.edits:
        console.print(f"\n[bold]History:[/bold] ({len(artifact.edits)} edits)")

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=4)
        table.add_column("Time", style="dim", width=16)
        table.add_column("Type", width=8)
        table.add_column("Change", width=12)
        table.add_column("Source", width=10)
        table.add_column("Goal", style="dim")

        for i, edit in enumerate(artifact.edits, 1):
            time_str = edit.timestamp.strftime("%m-%d %H:%M")
            change = f"+{edit.lines_added}/-{edit.lines_removed}"

            source_icon = "🤖" if edit.source == "sunwell" else "👤" if edit.source == "human" else "❓"
            source_str = f"{source_icon} {edit.source}"

            goal_str = edit.goal_id[:8] if edit.goal_id else "-"

            table.add_row(
                f"v{i}",
                time_str,
                edit.edit_type,
                change,
                source_str,
                goal_str,
            )

        console.print(table)

    # Dependencies
    if artifact.imports or artifact.imported_by:
        console.print("\n[bold]Dependencies:[/bold]")

        if artifact.imports:
            console.print(f"  imports ({len(artifact.imports)}):")
            for imp in artifact.imports[:10]:
                console.print(f"    → {imp}")
            if len(artifact.imports) > 10:
                console.print(f"    [dim]... and {len(artifact.imports) - 10} more[/dim]")

        if artifact.imported_by:
            console.print(f"  imported by ({len(artifact.imported_by)}):")
            for imp in artifact.imported_by[:10]:
                console.print(f"    ← {imp}")
            if len(artifact.imported_by) > 10:
                console.print(f"    [dim]... and {len(artifact.imported_by) - 10} more[/dim]")


@lineage.command("goal")
@click.argument("goal_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_goal(goal_id: str, json_output: bool, workspace: str) -> None:
    """Show all artifacts from a goal.

    Lists files created and modified by a specific goal.

    \b
    Examples:
        sunwell lineage goal abc123
        sunwell lineage goal goal-xyz --json
    """
    import json

    from sunwell.memory.lineage import LineageStore

    store = LineageStore(Path(workspace))
    artifacts = store.get_by_goal(goal_id)

    if not artifacts:
        console.print(f"[yellow]No artifacts found for goal {goal_id}[/yellow]")
        return

    if json_output:
        data = {
            "goal_id": goal_id,
            "artifacts": [a.to_dict() for a in artifacts],
        }
        print(json.dumps(data, indent=2, default=str))
        return

    # Separate created vs modified
    created = [a for a in artifacts if a.created_by_goal == goal_id]
    modified = [a for a in artifacts if a.created_by_goal != goal_id]

    console.print(Panel(f"Goal: {goal_id}", border_style="blue"))
    console.print(f"Artifacts: {len(artifacts)} files\n")

    if created:
        console.print(f"[bold]Created ({len(created)}):[/bold]")
        for a in created:
            console.print(f"  ✓ {a.path}")

    if modified:
        console.print(f"\n[bold]Modified ({len(modified)}):[/bold]")
        for a in modified:
            edits = [e for e in a.edits if e.goal_id == goal_id]
            total_added = sum(e.lines_added for e in edits)
            total_removed = sum(e.lines_removed for e in edits)
            console.print(f"  ✓ {a.path} (+{total_added}/-{total_removed})")


@lineage.command("deps")
@click.argument("path")
@click.option("--direction", type=click.Choice(["imports", "imported_by", "both"]),
              default="both", help="Which direction to show")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_deps(path: str, direction: str, json_output: bool, workspace: str) -> None:
    """Show dependency graph for a file.

    Displays what this file imports and what imports it.

    \b
    Examples:
        sunwell lineage deps src/api/routes.py
        sunwell lineage deps src/base.py --direction imports
    """
    import json

    from sunwell.memory.lineage import LineageStore

    store = LineageStore(Path(workspace))
    artifact = store.get_by_path(path)

    if not artifact:
        console.print(f"[yellow]No lineage found for {path}[/yellow]")
        return

    imports = list(artifact.imports) if direction in ("imports", "both") else []
    imported_by = list(artifact.imported_by) if direction in ("imported_by", "both") else []

    if json_output:
        data = {
            "path": path,
            "imports": imports,
            "imported_by": imported_by,
        }
        print(json.dumps(data, indent=2))
        return

    # Tree view
    tree = Tree(f"📄 {path}")

    if imports:
        imports_branch = tree.add("[cyan]imports[/cyan]")
        for imp in imports:
            imports_branch.add(imp)

    if imported_by:
        imported_branch = tree.add("[green]imported by[/green]")
        for imp in imported_by:
            imported_branch.add(imp)

    console.print(tree)


@lineage.command("impact")
@click.argument("path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_impact(path: str, json_output: bool, workspace: str) -> None:
    """Analyze impact of modifying/deleting a file.

    Shows all files that depend on this file (directly or transitively)
    and the goals that created those dependencies.

    \b
    Examples:
        sunwell lineage impact src/base.py
        sunwell lineage impact src/auth/base.py --json
    """
    import json

    from sunwell.memory.lineage import LineageStore, get_impact_analysis

    store = LineageStore(Path(workspace))
    impact = get_impact_analysis(store, path)

    if json_output:
        # Convert set to list for JSON serialization
        impact["affected_goals"] = list(impact["affected_goals"])
        print(json.dumps(impact, indent=2))
        return

    affected = impact["affected_files"]
    goals = impact["affected_goals"]

    if not affected:
        console.print(f"[green]No files depend on {path}[/green]")
        console.print("[dim]Safe to modify or delete.[/dim]")
        return

    console.print(Panel(f"Impact Analysis: {path}", border_style="yellow"))

    console.print(f"\n[bold]If you modify/delete this file:[/bold]")
    console.print(f"  • {len(affected)} files will be affected")
    console.print(f"  • Max dependency depth: {impact['max_depth']}")

    console.print(f"\n[bold]Affected files ({len(affected)}):[/bold]")
    for f in affected[:20]:
        console.print(f"  ⚠️  {f}")
    if len(affected) > 20:
        console.print(f"  [dim]... and {len(affected) - 20} more[/dim]")

    if goals:
        console.print(f"\n[bold]Related goals ({len(goals)}):[/bold]")
        for g in list(goals)[:10]:
            console.print(f"  • {g}")
        if len(goals) > 10:
            console.print(f"  [dim]... and {len(goals) - 10} more[/dim]")


@lineage.command("init")
@click.option("--scan", "scan_existing", is_flag=True, help="Scan existing files")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_init(scan_existing: bool, workspace: str) -> None:
    """Initialize lineage tracking for a project.

    Creates the .sunwell/lineage/ directory and optionally scans
    existing files to build dependency graph.

    \b
    Examples:
        sunwell lineage init
        sunwell lineage init --scan
    """
    from sunwell.memory.lineage import LineageStore

    ws_path = Path(workspace)
    store = LineageStore(ws_path)

    console.print("[green]✓ Lineage tracking initialized[/green]")
    console.print(f"  Storage: {store.store_path}")

    if scan_existing:
        console.print("\n[cyan]Scanning existing files...[/cyan]")
        stats = store.init_project(scan_existing=True)
        console.print(f"  • Scanned: {stats['files_scanned']} files")
        console.print(f"  • Created: {stats['artifacts_created']} lineage records")
    else:
        console.print("\n[dim]Tip: Use --scan to analyze existing files[/dim]")


@lineage.command("sync")
@click.option("--mark-human", is_flag=True, default=True,
              help="Mark detected changes as human edits")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_sync(mark_human: bool, json_output: bool, workspace: str) -> None:
    """Detect and sync untracked changes.

    Finds files that were modified outside of Sunwell and optionally
    marks them as human edits in the lineage.

    \b
    Examples:
        sunwell lineage sync
        sunwell lineage sync --json
    """
    import json

    from sunwell.memory.lineage import HumanEditDetector, LineageStore

    store = LineageStore(Path(workspace))
    detector = HumanEditDetector(store)

    untracked = detector.detect_untracked_changes(Path(workspace))

    if json_output:
        print(json.dumps({"untracked": untracked}, indent=2))
        return

    if not untracked:
        console.print("[green]✓ All tracked files are in sync[/green]")
        return

    console.print(f"[yellow]Found {len(untracked)} files with untracked changes:[/yellow]")
    for change in untracked[:20]:
        console.print(f"  ⚠️  {change['path']}")
    if len(untracked) > 20:
        console.print(f"  [dim]... and {len(untracked) - 20} more[/dim]")

    if mark_human:
        synced = detector.sync_untracked(Path(workspace), mark_as_human=True)
        console.print(f"\n[green]✓ Marked {len(synced)} files as human-edited[/green]")


@lineage.command("stats")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".",
              help="Project workspace root")
def lineage_stats(json_output: bool, workspace: str) -> None:
    """Show lineage statistics.

    Displays counts of tracked artifacts, edits, and dependency relationships.

    \b
    Examples:
        sunwell lineage stats
        sunwell lineage stats --json
    """
    import json

    from sunwell.memory.lineage import LineageStore

    store = LineageStore(Path(workspace))

    # Count artifacts
    artifact_count = len(store._index)
    deleted_count = len(store._deleted)

    # Count edits and sources
    total_edits = 0
    sunwell_edits = 0
    human_edits = 0
    human_edited_files = 0
    total_imports = 0
    total_imported_by = 0

    for artifact_id in store._list_artifact_ids():
        artifact = store._load_artifact(artifact_id)
        if artifact:
            total_edits += len(artifact.edits)
            sunwell_edits += sum(1 for e in artifact.edits if e.source == "sunwell")
            human_edits += sum(1 for e in artifact.edits if e.source == "human")
            if artifact.human_edited:
                human_edited_files += 1
            total_imports += len(artifact.imports)
            total_imported_by += len(artifact.imported_by)

    stats = {
        "tracked_files": artifact_count,
        "deleted_files": deleted_count,
        "total_edits": total_edits,
        "sunwell_edits": sunwell_edits,
        "human_edits": human_edits,
        "human_edited_files": human_edited_files,
        "dependency_edges": total_imports,
    }

    if json_output:
        print(json.dumps(stats, indent=2))
        return

    console.print(Panel("Lineage Statistics", border_style="blue"))

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Tracked files", str(artifact_count))
    table.add_row("Deleted files", str(deleted_count))
    table.add_row("Total edits", str(total_edits))
    table.add_row("  Sunwell edits", str(sunwell_edits))
    table.add_row("  Human edits", str(human_edits))
    table.add_row("Human-edited files", str(human_edited_files))
    table.add_row("Dependency edges", str(total_imports))

    console.print(table)
