"""Project Analysis and Management CLI (RFC-079, RFC-117).

CLI commands for universal project understanding and workspace isolation.

RFC-079: Project analysis (analyze, signals, monorepo, cache)
RFC-117: Workspace management (init, list, default, remove)
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# =============================================================================
# RFC-117: Workspace Management Commands
# =============================================================================


@click.group(name="project")
def project() -> None:
    """Project analysis and workspace management (RFC-079, RFC-117)."""
    pass


@project.command(name="init")
@click.argument("path", type=click.Path(), default=".")
@click.option("--id", "project_id", help="Project identifier (default: directory name)")
@click.option("--name", "project_name", help="Human-readable name (default: same as id)")
@click.option("--trust", type=click.Choice(["discovery", "read_only", "workspace", "full"]),
              default="workspace", help="Default trust level for agent")
@click.option("--no-register", is_flag=True, help="Don't add to global registry")
def init_cmd(
    path: str,
    project_id: str | None,
    project_name: str | None,
    trust: str,
    no_register: bool,
) -> None:
    """Initialize a new project workspace (RFC-117).

    Creates .sunwell/project.toml and registers in global registry.

    Examples:
        sunwell project init
        sunwell project init ~/projects/my-app
        sunwell project init . --id my-app --name "My Application"
    """
    from sunwell.knowledge.project import (
        ProjectValidationError,
        RegistryError,
        init_project,
    )

    project_path = Path(path).resolve()

    # Ensure directory exists
    if not project_path.exists():
        project_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[dim]Created directory: {project_path}[/dim]")

    try:
        proj = init_project(
            root=project_path,
            project_id=project_id,
            name=project_name,
            trust=trust,
            register=not no_register,
        )
    except ProjectValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None
    except RegistryError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    console.print()
    console.print(f"[green]✓[/green] Initialized project: [bold]{proj.id}[/bold]")
    console.print(f"  Root: {proj.root}")
    console.print(f"  Manifest: {proj.manifest_path}")
    if not no_register:
        console.print("  Registered: ~/.sunwell/projects.json")
    console.print()

    # Check if bindings are set up
    from sunwell.foundation.binding import BindingManager

    manager = BindingManager()
    default_binding = manager.get_default()

    if default_binding:
        console.print("[dim]You can now run:[/dim]")
        console.print("  [cyan]sunwell \"your goal here\"[/cyan]")
        console.print("  [cyan]sunwell chat[/cyan]")
    else:
        console.print("[yellow]No default binding configured.[/yellow]")
        console.print("[dim]Run setup to create bindings:[/dim]")
        console.print("  [cyan]sunwell setup[/cyan]")
        console.print()
        console.print("[dim]Or run directly with a goal:[/dim]")
        console.print("  [cyan]sunwell \"your goal here\"[/cyan]")


@project.command(name="list")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_cmd(output_json: bool) -> None:
    """List registered projects (RFC-117).

    Shows all projects in the global registry with their paths
    and last used timestamps.
    """
    from sunwell.knowledge.project import ProjectRegistry

    registry = ProjectRegistry()
    projects = registry.list_projects()
    default_id = registry.default_project_id

    if output_json:
        result = {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "root": str(p.root),
                    "workspace_type": p.workspace_type.value,
                    "is_default": p.id == default_id,
                }
                for p in projects
            ],
            "default_project": default_id,
        }
        console.print(json.dumps(result, indent=2))
        return

    if not projects:
        console.print("[yellow]No projects registered.[/yellow]")
        console.print()
        console.print("Initialize a project with:")
        console.print("  [cyan]sunwell project init .[/cyan]")
        return

    console.print()
    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Root")
    table.add_column("Default", justify="center")

    for p in sorted(projects, key=lambda x: x.id):
        is_default = "✓" if p.id == default_id else ""
        table.add_row(p.id, p.name, str(p.root), is_default)

    console.print(table)
    console.print()


@project.command(name="default")
@click.argument("project_id", required=False)
def default_cmd(project_id: str | None) -> None:
    """Get or set the default project (RFC-117).

    Without argument, shows current default.
    With argument, sets the default project.

    Examples:
        sunwell project default          # Show default
        sunwell project default my-app   # Set default
    """
    from sunwell.knowledge.project import ProjectRegistry, RegistryError

    registry = ProjectRegistry()

    if project_id is None:
        # Show current default
        default = registry.get_default()
        if default:
            console.print(f"Default project: [cyan]{default.id}[/cyan]")
            console.print(f"  Root: {default.root}")
        else:
            console.print("[yellow]No default project set.[/yellow]")
            console.print()
            console.print("Set one with:")
            console.print("  [cyan]sunwell project default <project-id>[/cyan]")
        return

    # Set default
    try:
        registry.set_default(project_id)
        console.print(f"[green]✓[/green] Default project set to: [cyan]{project_id}[/cyan]")
    except RegistryError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None


@project.command(name="current")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def current_cmd(json_output: bool) -> None:
    """Show current project/workspace (RFC-140).

    Shows the current workspace context, falling back to default project.

    Examples:
        sunwell project current
        sunwell project current --json
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()
    current = manager.get_current()

    if json_output:
        import json

        if current and current.project:
            output = {
                "id": current.project.id,
                "name": current.project.name,
                "root": str(current.project.root),
            }
        else:
            # Fallback to default
            from sunwell.knowledge import ProjectRegistry

            registry = ProjectRegistry()
            default = registry.get_default()
            if default:
                output = {
                    "id": default.id,
                    "name": default.name,
                    "root": str(default.root),
                }
            else:
                output = None
        console.print(json.dumps(output, indent=2))
        return

    if current and current.project:
        console.print(f"Current project: [cyan]{current.project.name}[/cyan]")
        console.print(f"  ID: {current.project.id}")
        console.print(f"  Root: {current.project.root}")
        return

    # Fallback to default
    from sunwell.knowledge import ProjectRegistry

    registry = ProjectRegistry()
    default = registry.get_default()

    if default:
        console.print(f"Current project: [cyan]{default.id}[/cyan]")
        console.print(f"  Root: {default.root}")
        console.print("[dim](Using default project - no workspace context set)[/dim]")
    else:
        console.print("[yellow]No current project or default set.[/yellow]")
        console.print()
        console.print("Set one with:")
        console.print("  [cyan]sunwell project switch <project-id>[/cyan]")
        console.print("  [cyan]sunwell project default <project-id>[/cyan]")


@project.command(name="switch")
@click.argument("project_id")
def switch_cmd(project_id: str) -> None:
    """Switch project context (RFC-140).

    Alias for `sunwell workspace switch`. Sets the project as current workspace.

    Examples:
        sunwell project switch my-app
        sunwell project switch /path/to/project
    """
    from sunwell.knowledge.workspace import WorkspaceManager

    manager = WorkspaceManager()

    try:
        workspace_info = manager.switch_workspace(project_id)
        console.print(f"[green]✓[/green] Switched to project: [cyan]{workspace_info.name}[/cyan]")
        console.print(f"  Path: {workspace_info.path}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None


@project.command(name="remove")
@click.argument("project_id")
@click.option("--force", "-f", is_flag=True, help="Remove without confirmation")
def remove_cmd(project_id: str, force: bool) -> None:
    """Remove a project from the registry (RFC-117).

    This only removes from the registry, not the actual files.

    Examples:
        sunwell project remove my-app
        sunwell project remove my-app --force
    """
    from sunwell.knowledge.project import ProjectRegistry

    registry = ProjectRegistry()

    # Check if exists
    project = registry.get(project_id)
    if not project:
        console.print(f"[yellow]Project not found:[/yellow] {project_id}")
        raise SystemExit(1)

    # Confirm unless forced
    if not force:
        console.print(f"Remove project [cyan]{project_id}[/cyan] from registry?")
        console.print(f"  Root: {project.root}")
        console.print()
        console.print("[dim]This will NOT delete any files.[/dim]")
        if not click.confirm("Continue?"):
            console.print("[dim]Aborted.[/dim]")
            return

    if registry.unregister(project_id):
        console.print(f"[green]✓[/green] Removed project: [cyan]{project_id}[/cyan]")
    else:
        console.print("[red]Failed to remove project[/red]")


@project.command(name="info")
@click.argument("project_id", required=False)
def info_cmd(project_id: str | None) -> None:
    """Show detailed project information (RFC-117).

    Without argument, shows info for cwd project or default.
    With argument, shows info for specified project.

    Examples:
        sunwell project info            # Current project
        sunwell project info my-app     # Specific project
    """
    from sunwell.knowledge.project import (
        ProjectRegistry,
        ProjectResolutionError,
        resolve_project,
    )

    try:
        if project_id:
            project = resolve_project(project_id=project_id)
        else:
            project = resolve_project(cwd=Path.cwd())
    except ProjectResolutionError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    console.print()
    console.print(Panel(
        f"[bold]{project.name}[/bold]",
        subtitle=project.id,
    ))

    console.print(f"  [dim]Root:[/dim] {project.root}")
    console.print(f"  [dim]Type:[/dim] {project.workspace_type.value}")
    console.print(f"  [dim]Created:[/dim] {project.created_at.isoformat()}")

    if project.manifest:
        console.print()
        console.print("[bold]Manifest[/bold]")
        console.print(f"  [dim]Trust:[/dim] {project.manifest.agent.trust}")
        console.print(f"  [dim]Protected:[/dim] {', '.join(project.manifest.agent.protected)}")

    # Check if default
    registry = ProjectRegistry()
    if registry.default_project_id == project.id:
        console.print()
        console.print("[green]✓[/green] This is the default project")

    console.print()


# =============================================================================
# RFC-079: Project Analysis Commands (existing)
# =============================================================================


@project.command(name="analyze")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--fresh", is_flag=True, help="Force fresh analysis (skip cache)")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama"]),
              default=None, help="Model provider (default: from config)")
@click.option("--model", "-m", default=None, help="Model to use for LLM classification")
def analyze_cmd(
    path: str,
    output_json: bool,
    fresh: bool,
    provider: str | None,
    model: str | None,
) -> None:
    """Analyze a project to understand its intent and state.

    Detects project type, infers goals, suggests next actions,
    and recommends appropriate workspace.

    Examples:
        sunwell project analyze
        sunwell project analyze ~/projects/myapp --json
        sunwell project analyze . --fresh
    """
    asyncio.run(_analyze(Path(path), output_json, fresh, provider, model))


async def _analyze(
    path: Path,
    output_json: bool,
    fresh: bool,
    provider_override: str | None,
    model_name: str | None,
) -> None:
    """Run project analysis."""
    from sunwell.interface.cli.helpers import resolve_model
    from sunwell.knowledge.project import analyze_project

    # Load model using resolve_model()
    model = resolve_model(provider_override, model_name)

    try:
        analysis = await analyze_project(path.resolve(), model, force_refresh=fresh)
    except Exception as e:
        if output_json:
            console.print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    if output_json:
        # Output raw JSON to stdout (bypass Rich to avoid ANSI codes)
        import sys

        output = json.dumps(analysis.to_cache_dict(), indent=2, ensure_ascii=False)
        # Sanitize: remove control characters except newlines/tabs
        sanitized = "".join(
            c for c in output if not (ord(c) < 32 and c not in "\n\r\t")
        )
        sys.stdout.write(sanitized)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return

    # Rich output
    _display_analysis(analysis)


def _display_analysis(analysis) -> None:
    """Display analysis in rich format."""
    from sunwell.knowledge.project import ProjectType

    # Header
    type_emoji = {
        ProjectType.CODE: "💻",
        ProjectType.DOCUMENTATION: "📚",
        ProjectType.DATA: "📊",
        ProjectType.PLANNING: "📋",
        ProjectType.CREATIVE: "✍️",
        ProjectType.MIXED: "🔀",
    }

    conf_color = {
        "high": "green",
        "medium": "yellow",
        "low": "red",
    }

    emoji = type_emoji.get(analysis.project_type, "📁")
    conf = analysis.confidence_level
    color = conf_color.get(conf, "white")

    console.print()
    console.print(
        Panel(
            f"[bold]{emoji} {analysis.project_type.value.title()} Project[/bold]"
            + (f" ({analysis.project_subtype})" if analysis.project_subtype else "")
            + f"\n[{color}]{int(analysis.confidence * 100)}% confident[/{color}]"
            + f" • Classification: {analysis.classification_source}",
            title=f"[bold blue]{analysis.name}[/bold blue]",
            subtitle=str(analysis.path),
        )
    )

    # Detection signals
    if analysis.detection_signals:
        signals = ", ".join(analysis.detection_signals[:5])
        if len(analysis.detection_signals) > 5:
            signals += f" (+{len(analysis.detection_signals) - 5} more)"
        console.print(f"[dim]Signals: {signals}[/dim]")

    # Pipeline
    if analysis.pipeline:
        console.print()
        console.print("[bold]📋 Pipeline[/bold]")
        for step in analysis.pipeline:
            if step.status == "completed":
                icon = "✅"
            elif step.status == "in_progress":
                icon = "🔄"
            else:
                icon = "⏳"
            current = " ← current" if step.id == analysis.current_step else ""
            console.print(f"  {icon} {step.title}[dim]{current}[/dim]")

        console.print(f"[dim]Completion: {int(analysis.completion_percent * 100)}%[/dim]")

    # Goals
    if analysis.goals:
        console.print()
        console.print("[bold]🎯 Goals[/bold]")
        for goal in analysis.goals[:5]:
            status_icon = "💡" if goal.status == "inferred" else "✓"
            console.print(f"  {status_icon} {goal.title} [{goal.priority}]")
        if len(analysis.goals) > 5:
            console.print(f"  [dim]...and {len(analysis.goals) - 5} more[/dim]")

    # Suggested action
    if analysis.suggested_action:
        console.print()
        action = analysis.suggested_action
        console.print(
            Panel(
                f"[bold]{action.description}[/bold]"
                + (f"\n[dim]Command: {action.command}[/dim]" if action.command else ""),
                title="💡 Suggested Next Action",
                border_style="green",
            )
        )

    # Dev command
    if analysis.dev_command:
        console.print()
        cmd = analysis.dev_command
        console.print("[bold]🖥️ Dev Server[/bold]")
        console.print(f"  Command: [cyan]{cmd.command}[/cyan]")
        if cmd.expected_url:
            console.print(f"  URL: {cmd.expected_url}")
        if cmd.prerequisites:
            console.print("  Prerequisites:")
            for prereq in cmd.prerequisites:
                console.print(f"    • {prereq.description}")

    # Workspace suggestion
    console.print()
    console.print(
        f"[dim]Suggested workspace: {analysis.suggested_workspace_primary}[/dim]"
    )
    console.print()


@project.command(name="signals")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def signals_cmd(path: str, output_json: bool) -> None:
    """Show raw project signals (for debugging).

    Displays all detected signals from the filesystem
    without classification or inference.
    """
    from sunwell.knowledge.project import gather_project_signals

    signals = gather_project_signals(Path(path).resolve())

    if output_json:
        result = {
            "path": str(signals.path),
            "signals": list(signals.summary),
            "has_package_json": signals.has_package_json,
            "has_pyproject": signals.has_pyproject,
            "has_cargo": signals.has_cargo,
            "has_go_mod": signals.has_go_mod,
            "has_docs_dir": signals.has_docs_dir,
            "has_notebooks": signals.has_notebooks,
            "has_backlog": signals.has_backlog,
            "markdown_count": signals.markdown_count,
            "git_branch": signals.git_status.branch if signals.git_status else None,
            "git_commit_count": (
                signals.git_status.commit_count if signals.git_status else 0
            ),
        }
        console.print(json.dumps(result, indent=2))
        return

    console.print()
    console.print(Panel("[bold]Project Signals[/bold]", subtitle=str(path)))

    table = Table(show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Signal", style="white")
    table.add_column("Value", style="green")

    # Code signals
    table.add_row("Code", "package.json", "✓" if signals.has_package_json else "✗")
    table.add_row("Code", "pyproject.toml", "✓" if signals.has_pyproject else "✗")
    table.add_row("Code", "Cargo.toml", "✓" if signals.has_cargo else "✗")
    table.add_row("Code", "go.mod", "✓" if signals.has_go_mod else "✗")
    table.add_row("Code", "src/ directory", "✓" if signals.has_src_dir else "✗")

    # Docs signals
    table.add_row("Docs", "docs/ directory", "✓" if signals.has_docs_dir else "✗")
    table.add_row("Docs", "Sphinx conf.py", "✓" if signals.has_sphinx_conf else "✗")
    table.add_row("Docs", "mkdocs.yml", "✓" if signals.has_mkdocs else "✗")
    table.add_row("Docs", "Markdown files", str(signals.markdown_count))

    # Data signals
    table.add_row("Data", "Notebooks (.ipynb)", "✓" if signals.has_notebooks else "✗")
    table.add_row("Data", "data/ directory", "✓" if signals.has_data_dir else "✗")
    table.add_row("Data", "CSV files", "✓" if signals.has_csv_files else "✗")

    # Planning signals
    table.add_row("Planning", "Backlog", "✓" if signals.has_backlog else "✗")
    table.add_row("Planning", "RFC directory", "✓" if signals.has_rfc_dir else "✗")
    table.add_row("Planning", "Roadmap", "✓" if signals.has_roadmap else "✗")

    # Creative signals
    table.add_row("Creative", "Prose dirs", "✓" if signals.has_prose else "✗")
    table.add_row("Creative", "Fountain files", "✓" if signals.has_fountain else "✗")

    # Git
    if signals.git_status:
        table.add_row("Git", "Branch", signals.git_status.branch)
        table.add_row("Git", "Commits", str(signals.git_status.commit_count))
        table.add_row(
            "Git", "Uncommitted", "✓" if signals.git_status.uncommitted_changes else "✗"
        )

    console.print(table)
    console.print()


@project.command(name="monorepo")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def monorepo_cmd(path: str, output_json: bool) -> None:
    """Detect sub-projects in a monorepo.

    Shows all detected sub-projects with their types.
    """
    from sunwell.knowledge.project import detect_sub_projects, is_monorepo

    project_path = Path(path).resolve()
    is_mono = is_monorepo(project_path)
    sub_projects = detect_sub_projects(project_path)

    if output_json:
        result = {
            "is_monorepo": is_mono,
            "sub_projects": [
                {
                    "name": sp.name,
                    "path": str(sp.path),
                    "manifest": str(sp.manifest),
                    "project_type": sp.project_type,
                    "description": sp.description,
                }
                for sp in sub_projects
            ],
        }
        console.print(json.dumps(result, indent=2))
        return

    console.print()
    if not is_mono:
        console.print(f"[yellow]Not a monorepo:[/yellow] {path}")
        console.print()
        return

    console.print(Panel(f"[bold]Monorepo[/bold] ({len(sub_projects)} sub-projects)"))

    for sp in sub_projects:
        emoji = "📦" if sp.project_type == "code" else "📄"
        desc = f" — {sp.description}" if sp.description else ""
        console.print(f"  {emoji} [cyan]{sp.name}[/cyan]{desc}")
        console.print(f"     [dim]{sp.path}[/dim]")

    console.print()


@project.command(name="cache")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--clear", is_flag=True, help="Clear the cache")
def cache_cmd(path: str, clear: bool) -> None:
    """Manage project analysis cache.

    View or clear cached analysis for a project.
    """
    from sunwell.knowledge.project import invalidate_cache, load_cached_analysis

    project_path = Path(path).resolve()

    if clear:
        if invalidate_cache(project_path):
            console.print("[green]✓[/green] Cache cleared")
        else:
            console.print("[yellow]No cache to clear[/yellow]")
        return

    analysis = load_cached_analysis(project_path)
    if analysis:
        console.print("[green]✓[/green] Cached analysis found")
        console.print(f"  Type: {analysis.project_type.value}")
        console.print(f"  Analyzed: {analysis.analyzed_at}")
        console.print(f"  Confidence: {int(analysis.confidence * 100)}%")
    else:
        console.print("[yellow]No cached analysis[/yellow]")
