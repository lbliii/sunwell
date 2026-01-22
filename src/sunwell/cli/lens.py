"""Lens commands — List, inspect, and manage lenses (RFC-064, RFC-070)."""

import asyncio
import json as json_module
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def lens() -> None:
    """Lens management commands (RFC-064)."""
    pass


@lens.command("list")
@click.option("--path", "-p", type=click.Path(exists=True), help="Path to search for lenses")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def lens_list(path: str | None, json_output: bool) -> None:
    """List all available lenses.

    By default, searches current directory and ~/.sunwell/lenses/

    Examples:

        sunwell lens list

        sunwell lens list --path ./my-lenses/

        sunwell lens list --json
    """
    asyncio.run(_list_lenses(path, json_output))


async def _list_lenses(path: str | None, json_output: bool) -> None:
    """List available lenses."""
    from pathlib import Path

    from sunwell.core.errors import SunwellError
    from sunwell.naaru.expertise.discovery import LensDiscovery
    from sunwell.schema.loader import LensLoader

    discovery = LensDiscovery()

    # Override search paths if specified
    if path:
        discovery.search_paths = [Path(path)]

    lenses_data: list[dict[str, object]] = []
    loader = LensLoader()

    for search_path in discovery.search_paths:
        if not search_path.exists():
            continue

        for lens_path in search_path.glob("*.lens"):
            try:
                lens_obj = loader.load(lens_path)
                version = lens_obj.metadata.version
                lenses_data.append(
                    {
                        "name": lens_obj.metadata.name,
                        "domain": lens_obj.metadata.domain,
                        "version": str(version) if version else "0.1.0",
                        "description": lens_obj.metadata.description,
                        "path": str(lens_path),
                        "heuristics_count": len(lens_obj.heuristics),
                        "skills_count": len(lens_obj.skills),
                    }
                )
            except SunwellError:
                pass  # Skip invalid lenses
            except Exception:
                pass

        # Also check .yaml files
        for lens_path in search_path.glob("*.lens.yaml"):
            try:
                lens_obj = loader.load(lens_path)
                version = lens_obj.metadata.version
                lenses_data.append(
                    {
                        "name": lens_obj.metadata.name,
                        "domain": lens_obj.metadata.domain,
                        "version": str(version) if version else "0.1.0",
                        "description": lens_obj.metadata.description,
                        "path": str(lens_path),
                        "heuristics_count": len(lens_obj.heuristics),
                        "skills_count": len(lens_obj.skills),
                    }
                )
            except SunwellError:
                pass
            except Exception:
                pass

    # Sort by name
    lenses_data.sort(key=lambda x: x["name"])

    if json_output:
        print(json_module.dumps(lenses_data, indent=2))
        return

    if not lenses_data:
        console.print("[yellow]No lenses found.[/yellow]")
        console.print(f"Searched: {', '.join(str(p) for p in discovery.search_paths)}")
        return

    table = Table(title="Available Lenses")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Domain", style="yellow")
    table.add_column("Heuristics", justify="right")
    table.add_column("Path", style="dim")

    for lens_info in lenses_data:
        table.add_row(
            lens_info["name"],
            lens_info["version"],
            lens_info["domain"] or "-",
            str(lens_info["heuristics_count"]),
            lens_info["path"],
        )

    console.print(table)


@lens.command("show")
@click.argument("lens_name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def lens_show(lens_name: str, json_output: bool) -> None:
    """Show details of a specific lens.

    Examples:

        sunwell lens show coder

        sunwell lens show tech-writer --json
    """
    asyncio.run(_show_lens(lens_name, json_output))


async def _show_lens(lens_name: str, json_output: bool) -> None:
    """Show lens details."""
    from sunwell.adaptive.lens_resolver import _load_lens
    from sunwell.naaru.expertise.discovery import LensDiscovery

    discovery = LensDiscovery()
    lens_obj = await _load_lens(lens_name, discovery)

    if not lens_obj:
        if json_output:
            print(json_module.dumps({"error": f"Lens not found: {lens_name}"}))
        else:
            console.print(f"[red]Lens not found: {lens_name}[/red]")
        return

    # Build detail dict
    detail = {
        "name": lens_obj.metadata.name,
        "domain": lens_obj.metadata.domain,
        "version": str(lens_obj.metadata.version) if lens_obj.metadata.version else "0.1.0",
        "description": lens_obj.metadata.description,
        "author": lens_obj.metadata.author,
        "heuristics": [
            {
                "name": h.name,
                "rule": h.rule,
                "priority": h.priority,
            }
            for h in lens_obj.heuristics
        ],
        "communication_style": (
            ", ".join(lens_obj.communication.tone) if lens_obj.communication else None
        ),
        "skills": [s.name for s in lens_obj.skills],
    }

    if json_output:
        print(json_module.dumps(detail, indent=2))
        return

    # Rich output
    console.print(f"[bold]Lens: {lens_obj.metadata.name}[/bold]")
    console.print(f"Version: {detail['version']}")
    console.print(f"Domain: {lens_obj.metadata.domain or 'general'}")
    if lens_obj.metadata.author:
        console.print(f"Author: {lens_obj.metadata.author}")
    if lens_obj.metadata.description:
        console.print(f"\n{lens_obj.metadata.description}")

    if lens_obj.heuristics:
        console.print(f"\n[bold]Heuristics ({len(lens_obj.heuristics)}):[/bold]")
        for h in lens_obj.heuristics[:5]:  # Show first 5
            rule_preview = h.rule[:60] + "..." if len(h.rule) > 60 else h.rule
            console.print(f"  • [cyan]{h.name}[/cyan]: {rule_preview}")
        if len(lens_obj.heuristics) > 5:
            console.print(f"  ... and {len(lens_obj.heuristics) - 5} more")

    if lens_obj.communication:
        tone_str = ", ".join(lens_obj.communication.tone)
        console.print(f"\n[bold]Communication Style:[/bold] {tone_str}")

    if lens_obj.skills:
        console.print(f"\n[bold]Skills ({len(lens_obj.skills)}):[/bold]")
        for s in lens_obj.skills[:5]:
            console.print(f"  • {s.name}")
        if len(lens_obj.skills) > 5:
            console.print(f"  ... and {len(lens_obj.skills) - 5} more")


@lens.command("resolve")
@click.argument("goal")
@click.option("--explicit", "-e", default=None, help="Explicit lens to use")
@click.option("--no-auto", is_flag=True, help="Disable auto-selection")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def lens_resolve(goal: str, explicit: str | None, no_auto: bool, json_output: bool) -> None:
    """Resolve which lens would be used for a goal.

    Useful for debugging lens selection without running the agent.

    Examples:

        sunwell lens resolve "Build a REST API"

        sunwell lens resolve "Write documentation" --json
    """
    asyncio.run(_resolve_lens(goal, explicit, not no_auto, json_output))


async def _resolve_lens(
    goal: str, explicit: str | None, auto_select: bool, json_output: bool
) -> None:
    """Resolve lens for a goal."""
    from sunwell.adaptive.lens_resolver import resolve_lens_for_goal

    resolution = await resolve_lens_for_goal(
        goal=goal,
        explicit_lens=explicit,
        project_path=Path.cwd(),
        auto_select=auto_select,
    )

    result = {
        "lens": resolution.lens.metadata.name if resolution.lens else None,
        "source": resolution.source,
        "confidence": resolution.confidence,
        "reason": resolution.reason,
    }

    if json_output:
        print(json_module.dumps(result, indent=2))
        return

    if resolution.lens:
        console.print(f"[green]Lens:[/green] {resolution.lens.metadata.name}")
        console.print(f"[dim]Source: {resolution.source}[/dim]")
        console.print(f"[dim]Confidence: {resolution.confidence:.0%}[/dim]")
        console.print(f"[dim]Reason: {resolution.reason}[/dim]")
    else:
        console.print("[yellow]No lens selected[/yellow]")
        console.print(f"[dim]Reason: {resolution.reason}[/dim]")


# =============================================================================
# RFC-070: Lens Library Management Commands
# =============================================================================


@lens.command("library")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--filter", "filter_by", help="Filter by: builtin, user, or domain name")
def library(json_output: bool, filter_by: str | None) -> None:
    """Browse the lens library with full metadata.

    Lists all available lenses with library metadata including
    heuristics count, skills count, use cases, and tags.

    Examples:

        sunwell lens library

        sunwell lens library --filter user

        sunwell lens library --filter documentation --json
    """
    asyncio.run(_library(json_output, filter_by))


async def _library(json_output: bool, filter_by: str | None) -> None:
    """List all lenses in the library."""
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    entries = await manager.list_library()

    if filter_by:
        if filter_by in ("builtin", "user"):
            entries = [e for e in entries if e.source == filter_by]
        else:
            entries = [e for e in entries if e.lens.metadata.domain == filter_by]

    if json_output:
        data = [
            {
                "name": e.lens.metadata.name,
                "domain": e.lens.metadata.domain,
                "version": str(e.lens.metadata.version),
                "description": e.lens.metadata.description,
                "source": e.source,
                "path": str(e.path),
                "is_default": e.is_default,
                "is_editable": e.is_editable,
                "version_count": e.version_count,
                "heuristics_count": len(e.lens.heuristics),
                "skills_count": len(e.lens.skills),
                "use_cases": list(e.lens.metadata.use_cases),
                "tags": list(e.lens.metadata.tags),
                "last_modified": e.last_modified,
            }
            for e in entries
        ]
        print(json_module.dumps(data, indent=2))
        return

    if not entries:
        console.print("[yellow]No lenses found.[/yellow]")
        return

    table = Table(title="Lens Library")
    table.add_column("", style="dim")  # Default indicator
    table.add_column("Name", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Source")
    table.add_column("Description")
    table.add_column("Version")

    for entry in entries:
        default_mark = "★" if entry.is_default else ""
        source_style = "green" if entry.source == "user" else "dim"
        table.add_row(
            default_mark,
            entry.lens.metadata.name,
            entry.lens.metadata.domain or "-",
            f"[{source_style}]{entry.source}[/]",
            (entry.lens.metadata.description or "-")[:40],
            str(entry.lens.metadata.version),
        )

    console.print(table)


@lens.command("fork")
@click.argument("source_name")
@click.argument("new_name")
@click.option("--message", "-m", help="Version message")
def fork(source_name: str, new_name: str, message: str | None) -> None:
    """Fork a lens to create an editable copy.

    Creates a new lens in ~/.sunwell/lenses/ based on an existing lens.
    The forked lens gets its own version history.

    Examples:

        sunwell lens fork coder my-team-coder

        sunwell lens fork tech-writer my-docs -m "Forked for team standards"
    """
    asyncio.run(_fork(source_name, new_name, message))


async def _fork(source_name: str, new_name: str, message: str | None) -> None:
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    try:
        path = await manager.fork_lens(source_name, new_name, message)
        console.print(f"[green]✓[/green] Forked to: {path}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command("save")
@click.argument("name")
@click.option(
    "--file", "-f", type=click.Path(exists=True), required=True, help="Path to edited lens file"
)
@click.option("--message", "-m", help="Version message")
@click.option(
    "--bump",
    type=click.Choice(["major", "minor", "patch"]),
    default="patch",
    help="Version bump type",
)
def save(name: str, file: str, message: str | None, bump: str) -> None:
    """Save changes to a user lens with version tracking.

    Reads content from the specified file and saves it to the lens,
    bumping the version number and creating a version snapshot.

    Examples:

        sunwell lens save my-coder --file edited.lens -m "Added heuristic"

        sunwell lens save my-coder --file edited.lens --bump minor
    """
    asyncio.run(_save(name, file, message, bump))


async def _save(name: str, file: str, message: str | None, bump: str) -> None:
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    content = Path(file).read_text()

    try:
        new_version = await manager.save_lens(
            name=name,
            content=content,
            message=message,
            bump=bump,
        )
        console.print(f"[green]✓[/green] Saved {name} v{new_version}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command("delete")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.option("--keep-versions", is_flag=True, default=True, help="Keep version history")
def delete(name: str, yes: bool, keep_versions: bool) -> None:
    """Delete a user lens.

    Only user lenses (in ~/.sunwell/lenses/) can be deleted.
    Built-in lenses cannot be deleted.

    Examples:

        sunwell lens delete my-old-lens

        sunwell lens delete my-old-lens --yes
    """
    if not yes and not click.confirm(f"Delete lens '{name}'?"):
        return

    asyncio.run(_delete(name, keep_versions))


async def _delete(name: str, keep_versions: bool) -> None:
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    try:
        await manager.delete_lens(name, keep_versions=keep_versions)
        console.print(f"[green]✓[/green] Deleted: {name}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command("versions")
@click.argument("name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def versions(name: str, json_output: bool) -> None:
    """Show version history for a lens.

    Displays the version history including timestamps and messages.

    Examples:

        sunwell lens versions my-team-coder

        sunwell lens versions my-team-coder --json
    """
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    version_list = manager.get_versions(name)

    if json_output:
        data = [
            {
                "version": str(v.version),
                "created_at": v.created_at,
                "message": v.message,
                "checksum": v.checksum,
            }
            for v in version_list
        ]
        print(json_module.dumps(data, indent=2))
        return

    if not version_list:
        console.print(f"No version history for: {name}")
        return

    console.print(f"[bold]Version History: {name}[/bold]\n")
    for v in reversed(version_list):  # Most recent first
        marker = "→" if v == version_list[-1] else " "
        console.print(f" {marker} [cyan]v{v.version}[/cyan] ({v.created_at[:10]})")
        if v.message:
            console.print(f"   {v.message}")


@lens.command("rollback")
@click.argument("name")
@click.argument("version")
def rollback(name: str, version: str) -> None:
    """Rollback a lens to a previous version.

    Restores the content from a previous version and creates
    a new version entry with a rollback message.

    Examples:

        sunwell lens rollback my-team-coder 1.0.0
    """
    asyncio.run(_rollback(name, version))


async def _rollback(name: str, version: str) -> None:
    from sunwell.lens.manager import LensManager

    manager = LensManager()
    try:
        await manager.rollback(name, version)
        console.print(f"[green]✓[/green] Rolled back {name} to v{version}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command("set-default")
@click.argument("name", required=False)
@click.option("--clear", is_flag=True, help="Clear the default lens")
def set_default(name: str | None, clear: bool) -> None:
    """Set or clear the global default lens.

    When no name is provided, shows the current default.
    Use --clear to remove the default and return to auto-select.

    Examples:

        sunwell lens set-default my-team-coder

        sunwell lens set-default

        sunwell lens set-default --clear
    """
    from sunwell.lens.manager import LensManager

    manager = LensManager()

    if clear:
        manager.set_global_default(None)
        console.print("[green]✓[/green] Cleared default lens")
    elif name:
        manager.set_global_default(name)
        console.print(f"[green]✓[/green] Default lens set to: {name}")
    else:
        current = manager.get_global_default()
        if current:
            console.print(f"Current default: [cyan]{current}[/cyan]")
        else:
            console.print("No default lens set (auto-select enabled)")


# =============================================================================
# RFC-087: Skill Graph Commands
# =============================================================================


@lens.command("skill-graph")
@click.argument("lens_name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--mermaid", is_flag=True, help="Output as Mermaid diagram")
def skill_graph(lens_name: str, json_output: bool, mermaid: bool) -> None:
    """Show the skill dependency graph for a lens (RFC-087).

    Displays skills and their dependencies as a DAG, with execution
    waves showing which skills can run in parallel.

    Examples:

        sunwell lens skill-graph tech-writer

        sunwell lens skill-graph tech-writer --json

        sunwell lens skill-graph coder --mermaid
    """
    asyncio.run(_skill_graph(lens_name, json_output, mermaid))


async def _skill_graph(lens_name: str, json_output: bool, mermaid: bool) -> None:
    """Show skill graph for a lens."""
    from sunwell.adaptive.lens_resolver import _load_lens
    from sunwell.naaru.expertise.discovery import LensDiscovery
    from sunwell.skills.graph import SkillGraph

    discovery = LensDiscovery()
    lens_obj = await _load_lens(lens_name, discovery)

    if not lens_obj:
        if json_output:
            print(json_module.dumps({"error": f"Lens not found: {lens_name}"}))
        else:
            console.print(f"[red]Lens not found: {lens_name}[/red]")
        return

    if not lens_obj.skills:
        if json_output:
            print(json_module.dumps({
                "lensName": lens_name,
                "skills": {},
                "waves": [],
                "contentHash": "",
            }))
        else:
            console.print(f"[yellow]Lens '{lens_name}' has no skills.[/yellow]")
        return

    # Build skill graph
    graph = SkillGraph.from_skills(lens_obj.skills)

    if mermaid:
        print(graph.to_mermaid())
        return

    if json_output:
        data = {
            "lensName": lens_name,
            "skills": {
                skill.name: {
                    "id": skill.name,
                    "name": skill.name,
                    "shortcut": "",
                    "description": skill.description,
                    "category": skill.skill_type.value,
                    "dependsOn": [
                        {
                            "source": dep.source,
                            "skillName": dep.skill_name,
                            "isLocal": dep.is_local,
                        }
                        for dep in skill.depends_on
                    ],
                    "produces": list(skill.produces),
                    "requires": list(skill.requires),
                }
                for skill in lens_obj.skills
            },
            "waves": [
                {"waveIndex": i, "skills": wave}
                for i, wave in enumerate(graph.execution_waves())
            ],
            "contentHash": graph.content_hash(),
        }
        print(json_module.dumps(data, indent=2))
        return

    # Rich output
    console.print(f"[bold]Skill Graph: {lens_name}[/bold]")
    console.print(f"Skills: {len(lens_obj.skills)} | Hash: {graph.content_hash()[:12]}...")
    console.print()

    waves = graph.execution_waves()
    for i, wave in enumerate(waves):
        console.print(f"[cyan]Wave {i + 1}:[/cyan] {', '.join(wave)}")

    console.print()
    for skill in lens_obj.skills:
        deps = [d.skill_name for d in skill.depends_on]
        deps_str = f" ← {', '.join(deps)}" if deps else ""
        produces_str = f" → {', '.join(skill.produces)}" if skill.produces else ""
        console.print(f"  • [green]{skill.name}[/green]{deps_str}{produces_str}")


@lens.command("skill-plan")
@click.argument("lens_name")
@click.option("--context-hash", help="Context hash for cache key computation")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def skill_plan(lens_name: str, context_hash: str | None, json_output: bool) -> None:
    """Show execution plan with cache predictions (RFC-087).

    Predicts which skills will execute vs skip based on cache state.

    Examples:

        sunwell lens skill-plan tech-writer --json

        sunwell lens skill-plan coder --context-hash abc123
    """
    asyncio.run(_skill_plan(lens_name, context_hash, json_output))


async def _skill_plan(lens_name: str, context_hash: str | None, json_output: bool) -> None:
    """Show execution plan for a lens."""
    from sunwell.adaptive.lens_resolver import _load_lens
    from sunwell.naaru.expertise.discovery import LensDiscovery
    from sunwell.skills.graph import SkillGraph

    discovery = LensDiscovery()
    lens_obj = await _load_lens(lens_name, discovery)

    if not lens_obj:
        if json_output:
            print(json_module.dumps({"error": f"Lens not found: {lens_name}"}))
        else:
            console.print(f"[red]Lens not found: {lens_name}[/red]")
        return

    if not lens_obj.skills:
        if json_output:
            print(json_module.dumps({
                "graph": {"lensName": lens_name, "skills": {}, "waves": [], "contentHash": ""},
                "toExecute": [],
                "toSkip": [],
                "skipPercentage": 0.0,
            }))
        else:
            console.print(f"[yellow]Lens '{lens_name}' has no skills.[/yellow]")
        return

    # Build skill graph
    graph = SkillGraph.from_skills(lens_obj.skills)

    # For now, all skills will execute (no cache integration without runtime context)
    # In a real execution, this would check the cache
    all_skills = [s.name for s in lens_obj.skills]

    graph_data = {
        "lensName": lens_name,
        "skills": {
            skill.name: {
                "id": skill.name,
                "name": skill.name,
                "shortcut": "",
                "description": skill.description,
                "category": skill.skill_type.value,
                "dependsOn": [
                    {
                        "source": dep.source,
                        "skillName": dep.skill_name,
                        "isLocal": dep.is_local,
                    }
                    for dep in skill.depends_on
                ],
                "produces": list(skill.produces),
                "requires": list(skill.requires),
            }
            for skill in lens_obj.skills
        },
        "waves": [
            {"waveIndex": i, "skills": wave}
            for i, wave in enumerate(graph.execution_waves())
        ],
        "contentHash": graph.content_hash(),
    }

    data = {
        "graph": graph_data,
        "toExecute": all_skills,
        "toSkip": [],
        "skipPercentage": 0.0,
    }

    if json_output:
        print(json_module.dumps(data, indent=2))
        return

    console.print(f"[bold]Execution Plan: {lens_name}[/bold]")
    console.print(f"To Execute: {len(all_skills)} skills")
    console.print(f"To Skip: 0 skills (0%)")
    console.print()
    console.print("[dim]Note: Cache predictions require runtime context.[/dim]")


@lens.command("skills")
@click.argument("lens_name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def lens_skills(lens_name: str, json_output: bool) -> None:
    """List skills for a lens with DAG information (RFC-087).

    Shows skills with their dependencies, produces, and requires.
    Used by Studio UI for skill panel.

    Examples:

        sunwell lens skills tech-writer

        sunwell lens skills tech-writer --json
    """
    asyncio.run(_lens_skills(lens_name, json_output))


async def _lens_skills(lens_name: str, json_output: bool) -> None:
    """List skills for a lens."""
    from sunwell.adaptive.lens_resolver import _load_lens
    from sunwell.naaru.expertise.discovery import LensDiscovery

    discovery = LensDiscovery()
    lens_obj = await _load_lens(lens_name, discovery)

    if not lens_obj:
        if json_output:
            print(json_module.dumps([]))
        else:
            console.print(f"[red]Lens not found: {lens_name}[/red]")
        return

    if not lens_obj.skills:
        if json_output:
            print(json_module.dumps([]))
        else:
            console.print(f"[yellow]Lens '{lens_name}' has no skills.[/yellow]")
        return

    # Get router shortcuts if available
    shortcuts: dict[str, str] = {}
    if lens_obj.router and lens_obj.router.shortcuts:
        shortcuts = {v: k for k, v in lens_obj.router.shortcuts.items()}

    skills_data = [
        {
            "id": skill.name,
            "name": skill.name,
            "shortcut": shortcuts.get(skill.name, ""),
            "description": skill.description,
            "category": skill.skill_type.value,
            "dependsOn": [
                {
                    "source": dep.source,
                    "skillName": dep.skill_name,
                    "isLocal": dep.is_local,
                }
                for dep in skill.depends_on
            ],
            "produces": list(skill.produces),
            "requires": list(skill.requires),
        }
        for skill in lens_obj.skills
    ]

    if json_output:
        print(json_module.dumps(skills_data, indent=2))
        return

    table = Table(title=f"Skills: {lens_name}")
    table.add_column("Name", style="cyan")
    table.add_column("Shortcut", style="yellow")
    table.add_column("Type", style="dim")
    table.add_column("Deps", justify="right")
    table.add_column("Produces")

    for skill in lens_obj.skills:
        shortcut = shortcuts.get(skill.name, "-")
        deps = len(skill.depends_on)
        produces = ", ".join(skill.produces) if skill.produces else "-"
        table.add_row(
            skill.name,
            shortcut,
            skill.skill_type.value,
            str(deps),
            produces[:30] + "..." if len(produces) > 30 else produces,
        )

    console.print(table)
