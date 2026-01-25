"""CLI commands for skill management (RFC-111 Phase 5).

Provides commands for:
- sunwell skills learn: Extract skills from successful sessions
- sunwell skills list: List skills in the local library
- sunwell skills show: Show details of a specific skill
- sunwell skills delete: Remove a skill from the library
- sunwell skills import: Import skills from external sources
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group(name="skills")
def skills_group() -> None:
    """Manage the local skill library.

    Skills can be learned from successful sessions, composed from existing
    skills, or imported from external sources.
    """
    pass


@skills_group.command(name="learn")
@click.argument("session_id")
@click.option(
    "--criteria",
    "-c",
    default="Task completed successfully",
    help="Success criteria that describes what made this session successful",
)
@click.option(
    "--name",
    "-n",
    help="Override the skill name (otherwise auto-generated)",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def learn_skill(
    session_id: str,
    criteria: str,
    name: str | None,
    project: Path,
) -> None:
    """Learn a skill from a successful session.

    Analyzes the execution trace from SESSION_ID and extracts a reusable
    skill pattern. The skill is saved to .sunwell/skills/learned/.

    Example:
        sunwell skills learn 20260123_143022 --criteria "Built REST API"
    """
    import asyncio

    from sunwell.foundation.config import Config, load_config
    from sunwell.planning.skills.learner import SkillLearner
    from sunwell.planning.skills.library import SkillLibrary
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    # Load config and initialize components
    config = load_config(project)
    simulacrum_path = project / ".sunwell" / "simulacrum"

    if not simulacrum_path.exists():
        console.print("[red]No simulacrum found in this project.[/red]")
        console.print("Run some sessions first, then try again.")
        raise SystemExit(1)

    store = SimulacrumStore(base_path=simulacrum_path)
    library = SkillLibrary(project / ".sunwell" / "skills")

    # Try to get a model if available
    model = None
    try:
        from sunwell.interface.cli.helpers.models import create_model

        model = create_model(config.default_model)
    except Exception:
        console.print("[dim]No model available, using heuristic extraction.[/dim]")

    learner = SkillLearner(model=model)

    console.print(f"[bold]Learning skill from session:[/bold] {session_id}")
    console.print(f"[dim]Success criteria:[/dim] {criteria}")

    async def _learn() -> None:
        skill = await learner.extract_skill_from_session(
            store=store,
            session_id=session_id,
            success_criteria=criteria,
        )

        if not skill:
            console.print("[red]Could not extract a skill from this session.[/red]")
            console.print("The session may not have enough tool usage or turns.")
            raise SystemExit(1)

        # Override name if provided
        if name:
            from sunwell.planning.skills.types import Skill

            skill = Skill(
                name=name,
                description=skill.description,
                skill_type=skill.skill_type,
                instructions=skill.instructions,
                depends_on=skill.depends_on,
                produces=skill.produces,
                requires=skill.requires,
                triggers=skill.triggers,
                allowed_tools=skill.allowed_tools,
            )

        # Save to library
        path = library.save_skill(skill, source="learned", session_id=session_id)

        console.print()
        console.print(f"[green]✓ Skill learned:[/green] [bold]{skill.name}[/bold]")
        console.print(f"  [dim]Description:[/dim] {skill.description[:80]}")
        console.print(f"  [dim]Saved to:[/dim] {path}")

        if skill.produces:
            console.print(f"  [dim]Produces:[/dim] {', '.join(skill.produces)}")
        if skill.triggers:
            console.print(f"  [dim]Triggers:[/dim] {', '.join(skill.triggers)}")

    asyncio.run(_learn())


@skills_group.command(name="list")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["learned", "composed", "imported", "all"]),
    default="all",
    help="Filter by skill source",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def list_skills(source: str, project: Path) -> None:
    """List skills in the local library.

    Shows all skills organized by how they were created (learned, composed,
    or imported).

    Example:
        sunwell skills list
        sunwell skills list --source learned
    """
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")

    source_filter = None if source == "all" else source
    skills = library.list_skills(source_filter=source_filter)

    if not skills:
        console.print("[dim]No skills in library.[/dim]")
        console.print("Learn skills from sessions with: sunwell skills learn <session_id>")
        return

    # Group by source
    by_source: dict[str, list[dict]] = {}
    for skill in skills:
        src = skill.get("source", "unknown")
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(skill)

    for src, src_skills in sorted(by_source.items()):
        console.print()
        console.print(f"[bold cyan]{src.upper()}[/bold cyan] ({len(src_skills)} skills)")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Name", style="green")
        table.add_column("Description", max_width=50)
        table.add_column("Version")
        table.add_column("Created")

        for skill in src_skills:
            created = skill.get("created_at", "")[:10] if skill.get("created_at") else ""
            desc = skill.get("description", "")[:50]
            if len(skill.get("description", "")) > 50:
                desc += "..."

            table.add_row(
                skill.get("name", ""),
                desc,
                skill.get("version", "1.0.0"),
                created,
            )

        console.print(table)

    # Summary
    stats = library.stats()
    console.print()
    console.print(f"[dim]Total skills: {stats['total_skills']}[/dim]")


@skills_group.command(name="show")
@click.argument("name")
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def show_skill(name: str, project: Path) -> None:
    """Show details of a specific skill.

    Displays the full skill definition including instructions,
    dependencies, and provenance information.

    Example:
        sunwell skills show audit-api-docs
    """
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")
    skill = library.load_skill(name)

    if not skill:
        console.print(f"[red]Skill not found:[/red] {name}")
        raise SystemExit(1)

    provenance = library.get_provenance(name)

    console.print(f"[bold cyan]Skill:[/bold cyan] {skill.name}")
    console.print(f"[dim]Description:[/dim] {skill.description}")
    console.print()

    if provenance:
        console.print("[bold]Provenance[/bold]")
        console.print(f"  Source: {provenance.source}")
        console.print(f"  Created: {provenance.created_at[:19]}")
        console.print(f"  Version: {provenance.version}")
        if provenance.session_id:
            console.print(f"  Session: {provenance.session_id}")
        if provenance.parent_skills:
            console.print(f"  Parents: {', '.join(provenance.parent_skills)}")
        console.print()

    if skill.depends_on:
        console.print("[bold]Dependencies[/bold]")
        for dep in skill.depends_on:
            console.print(f"  - {dep.source}")
        console.print()

    if skill.produces or skill.requires:
        console.print("[bold]Data Flow[/bold]")
        if skill.requires:
            console.print(f"  Requires: {', '.join(skill.requires)}")
        if skill.produces:
            console.print(f"  Produces: {', '.join(skill.produces)}")
        console.print()

    if skill.triggers:
        console.print("[bold]Triggers[/bold]")
        console.print(f"  {', '.join(skill.triggers)}")
        console.print()

    if skill.allowed_tools:
        console.print("[bold]Tools[/bold]")
        console.print(f"  {', '.join(skill.allowed_tools)}")
        console.print()

    if skill.instructions:
        console.print("[bold]Instructions[/bold]")
        console.print()
        # Truncate if too long
        instructions = skill.instructions
        if len(instructions) > 2000:
            instructions = instructions[:2000] + "\n\n... (truncated)"
        console.print(instructions)


@skills_group.command(name="delete")
@click.argument("name")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def delete_skill(name: str, yes: bool, project: Path) -> None:
    """Delete a skill from the library.

    Permanently removes the skill and its provenance data.

    Example:
        sunwell skills delete audit-api-docs
    """
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")

    # Check if skill exists
    skill = library.load_skill(name)
    if not skill:
        console.print(f"[red]Skill not found:[/red] {name}")
        raise SystemExit(1)

    # Confirm deletion
    if not yes:
        if not click.confirm(f"Delete skill '{name}'?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    if library.delete_skill(name):
        console.print(f"[green]✓ Deleted skill:[/green] {name}")
    else:
        console.print(f"[red]Failed to delete:[/red] {name}")
        raise SystemExit(1)


@skills_group.command(name="import")
@click.argument(
    "source",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--name",
    "-n",
    help="Override the skill name",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def import_skill(source: Path, name: str | None, project: Path) -> None:
    """Import a skill from an external source.

    Can import from:
    - SKILL.yaml files
    - SKILL.md files (Anthropic format)
    - Directories containing SKILL.yaml

    Example:
        sunwell skills import ~/shared-skills/audit-skill/
        sunwell skills import ./external-skill/SKILL.yaml --name my-skill
    """
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")

    skill = library.import_skill(source, name=name)

    if not skill:
        console.print(f"[red]Could not import skill from:[/red] {source}")
        console.print("Ensure the path contains a valid SKILL.yaml or SKILL.md file.")
        raise SystemExit(1)

    console.print(f"[green]✓ Imported skill:[/green] [bold]{skill.name}[/bold]")
    console.print(f"  [dim]Description:[/dim] {skill.description[:80]}")
    console.print(f"  [dim]From:[/dim] {source}")


@skills_group.command(name="sessions")
@click.option(
    "--limit",
    "-l",
    default=10,
    help="Number of sessions to show",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def list_sessions(limit: int, project: Path) -> None:
    """List recent sessions that can be used for learning.

    Shows sessions from the simulacrum store that can be analyzed
    to extract reusable skills.

    Example:
        sunwell skills sessions
        sunwell skills sessions --limit 20
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    simulacrum_path = project / ".sunwell" / "simulacrum"

    if not simulacrum_path.exists():
        console.print("[dim]No simulacrum found in this project.[/dim]")
        console.print("Sessions will be recorded as you use Sunwell.")
        return

    store = SimulacrumStore(base_path=simulacrum_path)
    sessions = store.list_sessions()[:limit]

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    console.print("[bold]Recent Sessions[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Session ID", style="green")
    table.add_column("Project")
    table.add_column("Turns")
    table.add_column("Created")

    for session in sessions:
        created = session.get("created", "")[:16] if session.get("created") else ""
        table.add_row(
            session.get("id", ""),
            session.get("project", "default"),
            str(session.get("turns", 0)),
            created,
        )

    console.print(table)
    console.print()
    console.print("[dim]Learn from a session: sunwell skills learn <session_id>[/dim]")


@skills_group.command(name="export")
@click.argument("name")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["anthropic", "sunwell", "yaml"]),
    default="anthropic",
    help="Export format (anthropic = SKILL.md, sunwell = SKILL.yaml with DAG)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: ./exported-skills/)",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def export_skill(
    name: str,
    format: str,
    output: Path | None,
    project: Path,
) -> None:
    """Export a skill to external format.

    Supports exporting to:
    - anthropic: Anthropic Agent Skills format (SKILL.md with frontmatter)
    - sunwell: Full Sunwell format with DAG metadata (SKILL.yaml)
    - yaml: Simple YAML format

    Examples:
        sunwell skills export my-skill --format anthropic
        sunwell skills export audit-skill --format sunwell -o ~/shared-skills/
    """
    from sunwell.planning.skills.interop import SkillExporter
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")
    skill = library.load_skill(name)

    if not skill:
        console.print(f"[red]Skill not found:[/red] {name}")
        console.print("Use 'sunwell skills list' to see available skills.")
        raise SystemExit(1)

    output_dir = output or Path("exported-skills")
    exporter = SkillExporter()

    path = exporter.export(skill, output_dir, format=format)

    console.print(f"[green]✓ Exported skill:[/green] [bold]{name}[/bold]")
    console.print(f"  [dim]Format:[/dim] {format}")
    console.print(f"  [dim]Path:[/dim] {path}")

    if format == "anthropic":
        console.print()
        console.print("[dim]This skill is now compatible with Claude Code and Claude.ai.[/dim]")
        console.print("[dim]Note: DAG features (depends_on, produces) are preserved as comments.[/dim]")


@skills_group.command(name="export-all")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["anthropic", "sunwell", "yaml"]),
    default="anthropic",
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: ./exported-skills/)",
)
@click.option(
    "--source",
    "-s",
    type=click.Choice(["learned", "composed", "imported", "all"]),
    default="all",
    help="Filter by skill source",
)
@click.option(
    "--project",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root directory",
)
def export_all_skills(
    format: str,
    output: Path | None,
    source: str,
    project: Path,
) -> None:
    """Export all skills from the library.

    Exports all skills to the specified format, organizing them by source.

    Examples:
        sunwell skills export-all --format anthropic
        sunwell skills export-all --source learned --format sunwell
    """
    from sunwell.planning.skills.interop import SkillExporter
    from sunwell.planning.skills.library import SkillLibrary

    library = SkillLibrary(project / ".sunwell" / "skills")
    exporter = SkillExporter()

    output_dir = output or Path("exported-skills")
    source_filter = None if source == "all" else source

    skills = library.list_skills(source_filter=source_filter)

    if not skills:
        console.print("[dim]No skills to export.[/dim]")
        return

    exported = 0
    for skill_info in skills:
        skill = library.load_skill(skill_info["name"])
        if skill:
            exporter.export(skill, output_dir / skill_info["source"], format=format)
            exported += 1

    console.print(f"[green]✓ Exported {exported} skills[/green]")
    console.print(f"  [dim]Format:[/dim] {format}")
    console.print(f"  [dim]Path:[/dim] {output_dir}")
