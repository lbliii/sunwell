"""Project Analysis CLI (RFC-079).

CLI commands for universal project understanding.
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group(name="project")
def project() -> None:
    """Project analysis and management (RFC-079)."""
    pass


@project.command(name="analyze")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--fresh", is_flag=True, help="Force fresh analysis (skip cache)")
@click.option("--model", "-m", default=None, help="Model to use for LLM classification")
def analyze_cmd(
    path: str,
    output_json: bool,
    fresh: bool,
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
    asyncio.run(_analyze(Path(path), output_json, fresh, model))


async def _analyze(
    path: Path,
    output_json: bool,
    fresh: bool,
    model_name: str | None,
) -> None:
    """Run project analysis."""
    from sunwell.models.ollama import OllamaModel
    from sunwell.project import analyze_project

    # Get model
    model = OllamaModel(model_name or "qwen2.5-coder:7b")

    try:
        analysis = await analyze_project(path.resolve(), model, force_refresh=fresh)
    except Exception as e:
        if output_json:
            console.print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    if output_json:
        console.print(json.dumps(analysis.to_cache_dict(), indent=2))
        return

    # Rich output
    _display_analysis(analysis)


def _display_analysis(analysis) -> None:
    """Display analysis in rich format."""
    from sunwell.project import ProjectType

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
    from sunwell.project import gather_project_signals

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
    from sunwell.project import detect_sub_projects, is_monorepo

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
    from sunwell.project import invalidate_cache, load_cached_analysis

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
