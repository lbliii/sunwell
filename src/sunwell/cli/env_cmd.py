"""Environment command for User Environment Model (RFC-104).

Commands:
    sunwell env scan            - Discover and catalog projects
    sunwell env list            - List known projects
    sunwell env patterns        - Show learned patterns
    sunwell env references      - List reference projects
    sunwell env reference add   - Mark a project as reference
    sunwell env reference remove - Remove a reference
    sunwell env similar         - Find similar projects
"""

from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group("env")
def env() -> None:
    """Manage your development environment.

    \b
    The environment model tracks:
    • Where you keep projects (roots)
    • What projects exist (catalog)
    • Patterns across projects
    • Gold standard references

    \b
    Get started:
        sunwell env scan        Discover your projects
        sunwell env list        See what was found
        sunwell env patterns    View learned patterns
    """


# =============================================================================
# env scan
# =============================================================================


@env.command("scan")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--reset",
    is_flag=True,
    help="Reset environment before scanning",
)
def env_scan(path: str, reset: bool) -> None:
    """Add a project directory to your environment.

    \b
    Projects are added as you work with them (like IDE recent projects).
    This command adds the current or specified directory.

    \b
    Examples:
        sunwell env scan              # Add current directory
        sunwell env scan ~/myproject  # Add specific project
        sunwell env scan --reset .    # Reset and add current
    """
    from sunwell.environment import (
        create_project_entry_from_path,
        extract_patterns,
        load_environment,
        reset_environment,
        save_environment,
    )

    # Reset if requested
    if reset:
        reset_environment()
        console.print("[yellow]Environment reset[/yellow]")

    # Load existing environment
    env = load_environment()

    # Add the specified project
    project_path = Path(path).resolve()
    entry = create_project_entry_from_path(project_path)

    if entry:
        env.add_project(entry)
        console.print(f"[green]Added: {entry.name} ({entry.project_type})[/green]")
    else:
        console.print(f"[yellow]Not a recognized project: {project_path}[/yellow]")
        return

    # Quick pattern update (only if we have multiple projects)
    if len(env.projects) >= 3:
        env.patterns = extract_patterns(env.projects)

    # Save
    save_environment(env)
    console.print(f"[dim]Environment: {len(env.projects)} projects[/dim]")


# =============================================================================
# env list
# =============================================================================


@env.command("list")
@click.option(
    "--type", "-t",
    type=str,
    default=None,
    help="Filter by project type (python, docs, go, node)",
)
@click.option(
    "--sort",
    type=click.Choice(["name", "health", "scanned", "type"]),
    default="name",
    help="Sort order",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show all details",
)
def env_list(type: str | None, sort: str, verbose: bool) -> None:
    """List known projects in your environment.

    \b
    Examples:
        sunwell env list                  # List all
        sunwell env list --type python    # Only Python projects
        sunwell env list --sort health    # Sort by health score
    """
    from sunwell.environment import load_environment

    env = load_environment()

    if not env.projects:
        console.print("[yellow]No projects found. Run: sunwell env scan[/yellow]")
        return

    # Filter
    projects = env.projects
    if type:
        projects = [p for p in projects if p.project_type == type.lower()]

    # Sort
    if sort == "name":
        projects = sorted(projects, key=lambda p: p.name.lower())
    elif sort == "health":
        projects = sorted(projects, key=lambda p: p.health_score or 0, reverse=True)
    elif sort == "scanned":
        projects = sorted(
            projects,
            key=lambda p: p.last_scanned or datetime.min,
            reverse=True,
        )
    elif sort == "type":
        projects = sorted(projects, key=lambda p: (p.project_type, p.name.lower()))

    # Display
    table = Table(show_header=True, header_style="bold")
    table.add_column("Project", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Health", justify="right")
    table.add_column("Last Scanned", style="dim")
    if verbose:
        table.add_column("Path", style="dim")

    for project in projects:
        # Health indicator
        if project.health_score is not None:
            score = project.health_score * 100
            if score >= 90:
                health = f"🟢 {score:.0f}%"
            elif score >= 70:
                health = f"🟡 {score:.0f}%"
            elif score >= 50:
                health = f"🟠 {score:.0f}%"
            else:
                health = f"🔴 {score:.0f}%"
        else:
            health = "[dim]—[/dim]"

        # Last scanned
        if project.last_scanned:
            age = datetime.now() - project.last_scanned
            if age < timedelta(hours=1):
                scanned = "just now"
            elif age < timedelta(days=1):
                scanned = f"{age.seconds // 3600}h ago"
            elif age < timedelta(days=7):
                scanned = f"{age.days}d ago"
            else:
                scanned = project.last_scanned.strftime("%Y-%m-%d")
        else:
            scanned = "[dim]never[/dim]"

        # Name with reference indicator
        name = project.name
        if project.is_reference:
            name = f"⭐ {name}"

        row = [name, project.project_type, health, scanned]
        if verbose:
            row.append(str(project.path))

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]{len(projects)} projects[/dim]")


# =============================================================================
# env patterns
# =============================================================================


@env.command("patterns")
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show example projects for each pattern",
)
def env_patterns(verbose: bool) -> None:
    """Show learned patterns across your projects.

    Patterns are conventions detected across your projects,
    like directory structure, tooling, and configurations.
    """
    from sunwell.environment import load_environment

    env = load_environment()

    if not env.patterns:
        console.print("[yellow]No patterns found. Run: sunwell env scan[/yellow]")
        return

    # Sort by confidence
    patterns = sorted(env.patterns, key=lambda p: p.confidence, reverse=True)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Pattern", style="cyan")
    table.add_column("Description")
    table.add_column("Frequency", justify="right")
    table.add_column("Confidence", justify="right")

    for pattern in patterns:
        conf_pct = pattern.confidence * 100
        if conf_pct >= 80:
            conf_str = f"[green]{conf_pct:.0f}%[/green]"
        elif conf_pct >= 60:
            conf_str = f"[yellow]{conf_pct:.0f}%[/yellow]"
        else:
            conf_str = f"[dim]{conf_pct:.0f}%[/dim]"

        table.add_row(
            pattern.name,
            pattern.description,
            f"{pattern.frequency}",
            conf_str,
        )

    console.print(table)

    if verbose:
        console.print("\n[bold]Examples:[/bold]")
        for pattern in patterns[:5]:  # Top 5
            console.print(f"\n[cyan]{pattern.name}[/cyan]:")
            for example in pattern.examples[:3]:
                console.print(f"  • {example.name}")


# =============================================================================
# env references
# =============================================================================


@env.command("references")
def env_references() -> None:
    """List reference (gold standard) projects.

    Reference projects are used as templates when planning
    new projects of the same type.
    """
    from sunwell.environment import (
        check_reference_health,
        list_references,
        load_environment,
        suggest_references,
    )

    env = load_environment()
    refs = list_references(env)

    if not refs:
        # Check for suggestions
        suggested = suggest_references(env.projects)
        if suggested:
            console.print("[yellow]No references set, but suggestions available:[/yellow]\n")
            for category, ref_path in suggested.items():
                project = env.get_project(ref_path)
                if project and project.health_score:
                    health = f"{project.health_score * 100:.0f}%"
                else:
                    health = "—"
                console.print(f"  {category}: {ref_path.name} ({health})")
            console.print("\n[dim]sunwell env reference add <path> --category <type>[/dim]")
        else:
            console.print("[yellow]No references set. Run: sunwell env reference add[/yellow]")
        return

    # Show current references
    table = Table(show_header=True, header_style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Project")
    table.add_column("Health", justify="right")
    table.add_column("Status")

    for ref in refs:
        # Health
        if ref["health_score"] is not None:
            score = ref["health_score"] * 100
            if score >= 90:
                health = f"🟢 {score:.0f}%"
            elif score >= 70:
                health = f"🟡 {score:.0f}%"
            else:
                health = f"🟠 {score:.0f}%"
        else:
            health = "[dim]—[/dim]"

        # Status
        if not ref["exists"]:
            status = "[red]Not found[/red]"
        elif ref["healthy"]:
            status = "[green]OK[/green]"
        else:
            status = "[yellow]Degraded[/yellow]"

        table.add_row(ref["category"], ref["name"], health, status)

    console.print(table)

    # Show warnings
    warnings = check_reference_health(env)
    if warnings:
        console.print("\n[yellow]⚠️ Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")


# =============================================================================
# env reference add/remove
# =============================================================================


@env.group("reference")
def env_reference() -> None:
    """Manage reference projects."""


@env_reference.command("add")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--category", "-c",
    type=str,
    required=True,
    help="Category for this reference (e.g., docs, python)",
)
def env_reference_add(path: str, category: str) -> None:
    """Mark a project as a reference for a category.

    \b
    Examples:
        sunwell env reference add ~/prompt-library --category docs
        sunwell env reference add ~/sunwell --category python
    """
    from sunwell.environment import (
        add_reference,
        load_environment,
        save_environment,
    )

    env = load_environment()
    success, message = add_reference(env, category, Path(path))

    if success:
        save_environment(env)
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")


@env_reference.command("remove")
@click.argument("category", type=str)
def env_reference_remove(category: str) -> None:
    """Remove a reference for a category.

    \b
    Examples:
        sunwell env reference remove docs
    """
    from sunwell.environment import (
        load_environment,
        remove_reference,
        save_environment,
    )

    env = load_environment()
    success, message = remove_reference(env, category)

    if success:
        save_environment(env)
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[yellow]![/yellow] {message}")


# =============================================================================
# env similar
# =============================================================================


@env.command("similar")
@click.argument("path", type=click.Path(exists=True))
def env_similar(path: str) -> None:
    """Find projects similar to the given one.

    \b
    Examples:
        sunwell env similar ~/new-docs-project
    """
    from sunwell.environment import load_environment

    env = load_environment()
    project_path = Path(path).resolve()

    # Check if in environment
    project = env.get_project(project_path)
    if not project:
        console.print(f"[yellow]Project not found. Run: sunwell env scan --path {path}[/yellow]")
        return

    similar = env.find_similar(project_path)
    if not similar:
        console.print(f"[yellow]No similar projects found (type: {project.project_type})[/yellow]")
        return

    # Sort by health
    similar = sorted(similar, key=lambda p: p.health_score or 0, reverse=True)

    console.print(f"[bold]Similar to {project.name}[/bold] (type: {project.project_type})\n")

    for p in similar[:10]:
        ref_marker = "⭐ " if p.is_reference else ""
        health = f"{p.health_score * 100:.0f}%" if p.health_score else "—"
        console.print(f"  {ref_marker}{p.name} ({health})")


# =============================================================================
# env info
# =============================================================================


@env.command("info")
def env_info() -> None:
    """Show environment summary and status."""
    from sunwell.environment import (
        get_environment_age,
        get_environment_path,
        load_environment,
    )

    env = load_environment()
    path = get_environment_path()
    age = get_environment_age()

    # Age display
    if age is None:
        age_str = "never saved"
    elif age < 3600:
        age_str = f"{int(age / 60)} minutes ago"
    elif age < 86400:
        age_str = f"{int(age / 3600)} hours ago"
    else:
        age_str = f"{int(age / 86400)} days ago"

    # Project type distribution
    type_counts: dict[str, int] = {}
    for p in env.projects:
        type_counts[p.project_type] = type_counts.get(p.project_type, 0) + 1

    types_str = ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))

    # Health distribution
    scanned = [p for p in env.projects if p.health_score is not None]
    healthy = len([p for p in scanned if p.health_score and p.health_score >= 0.9])
    moderate = len([p for p in scanned if p.health_score and 0.7 <= p.health_score < 0.9])
    unhealthy = len([p for p in scanned if p.health_score and p.health_score < 0.7])

    summary = f"""[bold]Environment Summary[/bold]

📁 [bold]File:[/bold] {path}
📅 [bold]Last Updated:[/bold] {age_str}

[bold]Projects[/bold]
  Total: {len(env.projects)}
  By type: {types_str}
  Scanned: {len(scanned)} ({len(env.projects) - len(scanned)} never scanned)

[bold]Health[/bold]
  🟢 Healthy (90%+): {healthy}
  🟡 Moderate (70-89%): {moderate}
  🟠🔴 Needs attention (<70%): {unhealthy}

[bold]Roots[/bold]: {len(env.roots)}
[bold]Patterns[/bold]: {len(env.patterns)}
[bold]References[/bold]: {len(env.reference_projects)}"""

    console.print(Panel(summary, border_style="blue"))
