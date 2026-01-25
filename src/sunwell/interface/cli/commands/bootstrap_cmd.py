"""Bootstrap CLI commands — RFC-050.

Commands for initializing and managing bootstrap intelligence.
"""


import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def bootstrap() -> None:
    """Bootstrap intelligence from project artifacts.

    Fast Bootstrap mines existing project artifacts to provide
    immediate intelligence before Sunwell has learned anything
    from conversations.

    \b
    Example:
        sunwell bootstrap          # Run full bootstrap
        sunwell bootstrap --report # Show what would be bootstrapped
        sunwell bootstrap status   # Show bootstrap status
    """


@bootstrap.command(name="run")
@click.option("--no-llm", is_flag=True, help="Skip LLM for fully deterministic scan")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
@click.option("--report", is_flag=True, help="Show what would be bootstrapped without saving")
@click.option("--max-commits", default=1000, help="Maximum commits to scan")
@click.option("--max-age-days", default=365, help="Ignore commits older than this")
def bootstrap_run(
    no_llm: bool,
    verbose: bool,
    report: bool,
    max_commits: int,
    max_age_days: int,
) -> None:
    """Run bootstrap scan on current project.

    Scans git history, code patterns, documentation, and configuration
    to populate intelligence stores.

    \b
    Example:
        sunwell bootstrap run              # Full bootstrap
        sunwell bootstrap run --no-llm     # Skip LLM (faster, deterministic)
        sunwell bootstrap run --report     # Preview without saving
    """
    asyncio.run(_run_bootstrap(
        no_llm=no_llm,
        verbose=verbose,
        report_only=report,
        max_commits=max_commits,
        max_age_days=max_age_days,
    ))


@bootstrap.command(name="status")
def bootstrap_status() -> None:
    """Show current bootstrap status.

    Displays when bootstrap was last run, what was found,
    and whether an update is available.
    """
    asyncio.run(_show_status())


@bootstrap.command(name="update")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
def bootstrap_update(verbose: bool) -> None:
    """Update bootstrap intelligence incrementally.

    Only processes new commits since last bootstrap.
    Much faster than full re-bootstrap.
    """
    asyncio.run(_run_incremental(verbose=verbose))


@bootstrap.command(name="ownership")
@click.argument("path", required=False)
def bootstrap_ownership(path: str | None) -> None:
    """Show code ownership information.

    \b
    Example:
        sunwell bootstrap ownership           # Show all domains
        sunwell bootstrap ownership src/auth  # Show owner of specific path
    """
    asyncio.run(_show_ownership(path))


async def _run_bootstrap(
    no_llm: bool,
    verbose: bool,
    report_only: bool,
    max_commits: int,
    max_age_days: int,
) -> None:
    """Run bootstrap scan."""
    from sunwell.knowledge.bootstrap import BootstrapOrchestrator
    from sunwell.knowledge.codebase.context import ProjectContext

    project_root = Path.cwd()

    # Check for existing .sunwell
    sunwell_dir = project_root / ".sunwell"
    if not sunwell_dir.exists() and not report_only:
        sunwell_dir.mkdir(parents=True)

    console.print(f"🔍 [bold]Scanning project:[/bold] {project_root.name}\n")

    # Load or create context
    context = await ProjectContext.load(project_root)

    # Create orchestrator
    orchestrator = BootstrapOrchestrator(
        root=project_root,
        context=context,
        use_llm=not no_llm,
        verbose=verbose,
        max_commits=max_commits,
        max_age_days=max_age_days,
    )

    # Run bootstrap
    result = await orchestrator.bootstrap()

    # Display results
    _display_result(result, report_only)

    if not report_only:
        # Save bootstrap state
        _save_bootstrap_state(project_root, result)

        console.print("\n[green]✅ Bootstrap complete[/green]")
        console.print(
            "\nRun [cyan]sunwell chat[/cyan] to start. "
            "Your patterns and decisions are ready."
        )
    else:
        console.print("\n[yellow]Report only — no changes saved[/yellow]")


def _display_result(result, report_only: bool) -> None:
    """Display bootstrap result."""

    console.print("[bold]Scan Results:[/bold]")
    console.print(f"  Duration: {result.duration.total_seconds():.1f}s")
    console.print()

    # Git evidence
    if result.git_evidence:
        git = result.git_evidence
        console.print(f"  [cyan]Git history:[/cyan] {len(git.commits)} commits, "
                      f"{len(git.contributor_stats)} contributors")

    # Code evidence
    if result.code_evidence:
        code = result.code_evidence
        funcs = len(code.module_structure.functions)
        classes = len(code.module_structure.classes)
        console.print(f"  [cyan]Code analysis:[/cyan] {funcs} functions, {classes} classes")

        # Naming patterns
        naming = code.naming_patterns
        console.print(
            f"    • Functions: {naming.function_style} ({naming.function_samples} samples)"
        )
        console.print(f"    • Classes: {naming.class_style} ({naming.class_samples} samples)")

        # Type hints
        hints = code.type_hint_usage
        console.print(f"    • Type hints: {hints.level} "
                      f"({hints.functions_with_hints}/{hints.functions_total} functions)")

        # Docstrings
        docs = code.docstring_style
        console.print(f"    • Docstrings: {docs.style} ({docs.consistency:.0%} consistency)")

    # Config evidence
    if result.config_evidence:
        config = result.config_evidence
        tools = []
        if config.formatter:
            tools.append(f"formatter={config.formatter}")
        if config.linter:
            tools.append(f"linter={config.linter}")
        if config.type_checker:
            tools.append(f"type_checker={config.type_checker}")
        if tools:
            console.print(f"  [cyan]Configuration:[/cyan] {', '.join(tools)}")

    console.print()

    # Intelligence summary
    console.print("[bold]Intelligence Extracted:[/bold]")
    console.print(f"  • Decisions: {result.decisions_inferred}")
    console.print(f"  • Patterns: {result.patterns_detected}")
    console.print(f"  • Ownership domains: {result.ownership_domains}")
    console.print(f"  • Confidence: {result.average_confidence:.0%} (bootstrap default)")

    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  ⚠️ {warning}")


def _save_bootstrap_state(project_root: Path, result) -> None:
    """Save bootstrap state for incremental updates."""
    import json
    from datetime import datetime

    state_path = project_root / ".sunwell" / "bootstrap_state.json"

    # Get current HEAD commit
    import subprocess
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        head = ""

    state = {
        "last_commit": head,
        "updated_at": datetime.now().isoformat(),
        "decisions_count": result.decisions_inferred,
        "patterns_count": result.patterns_detected,
        "ownership_domains": result.ownership_domains,
        "scan_duration_s": result.duration.total_seconds(),
    }

    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


async def _show_status() -> None:
    """Show bootstrap status."""
    from sunwell.knowledge.codebase.context import ProjectContext

    project_root = Path.cwd()
    context = await ProjectContext.load(project_root)

    if not context.bootstrap_status:
        console.print("[yellow]No bootstrap has been run yet.[/yellow]")
        console.print("\nRun [cyan]sunwell bootstrap run[/cyan] to get started.")
        return

    status = context.bootstrap_status

    console.print("[bold]Bootstrap Status:[/bold]")
    console.print(f"  Last run: {status.last_run.strftime('%Y-%m-%d %H:%M')}")
    last_commit = status.last_commit_scanned[:8] if status.last_commit_scanned else "unknown"
    console.print(f"  Last commit: {last_commit}")
    console.print(f"  Scan duration: {status.scan_duration.total_seconds():.1f}s")
    console.print()
    console.print("[bold]Intelligence:[/bold]")
    console.print(f"  • Decisions: {status.decisions_count}")
    console.print(f"  • Patterns: {status.patterns_count}")
    console.print(f"  • Ownership domains: {status.ownership_domains}")

    # Check if update available
    from sunwell.knowledge.bootstrap.incremental import IncrementalBootstrap
    incremental = IncrementalBootstrap(project_root, context)
    current_head = await incremental._get_head_commit()

    if current_head and current_head != status.last_commit_scanned:
        console.print("\n[yellow]Update available[/yellow]: New commits since last bootstrap.")
        console.print("Run [cyan]sunwell bootstrap update[/cyan] to process new commits.")


async def _run_incremental(verbose: bool) -> None:
    """Run incremental bootstrap update."""
    from sunwell.knowledge.bootstrap.incremental import IncrementalBootstrap
    from sunwell.knowledge.codebase.context import ProjectContext

    project_root = Path.cwd()
    context = await ProjectContext.load(project_root)

    if verbose:
        console.print("Checking for new commits...")

    incremental = IncrementalBootstrap(project_root, context)
    update = await incremental.update_if_needed()

    if not update:
        console.print("[green]✓[/green] No updates needed. Already up to date.")
        return

    console.print("[bold]Incremental Update:[/bold]")
    console.print(f"  • New commits: {update.new_commits}")
    console.print(f"  • New decisions: {update.new_decisions}")
    console.print(f"  • Files updated: {update.files_updated}")
    console.print("\n[green]✅ Update complete[/green]")


async def _show_ownership(path: str | None) -> None:
    """Show ownership information."""
    from sunwell.knowledge.bootstrap.ownership import OwnershipMap

    project_root = Path.cwd()
    intelligence_path = project_root / ".sunwell" / "intelligence"
    ownership = OwnershipMap(intelligence_path)

    if path:
        # Show owner of specific path
        file_path = Path(path)
        owner = ownership.get_owner(file_path)
        experts = ownership.get_experts(file_path)

        if owner:
            console.print(f"[bold]Owner of {path}:[/bold] {owner}")
            if len(experts) > 1:
                console.print(f"[dim]Other experts:[/dim] {', '.join(experts[1:])}")
        else:
            console.print(f"[yellow]No ownership data for {path}[/yellow]")
    else:
        # Show all domains
        domains = ownership.get_all_domains()

        if not domains:
            console.print("[yellow]No ownership data available.[/yellow]")
            console.print("Run [cyan]sunwell bootstrap run[/cyan] first.")
            return

        table = Table(title="Code Ownership Domains")
        table.add_column("Domain", style="cyan")
        table.add_column("Primary Owner")
        table.add_column("Ownership %")
        table.add_column("Files")
        table.add_column("Secondary")

        for domain in sorted(domains, key=lambda d: d.name):
            table.add_row(
                domain.name,
                domain.primary_owner,
                f"{domain.ownership_percentage:.0%}",
                str(len(domain.files)),
                ", ".join(domain.secondary_owners) if domain.secondary_owners else "-",
            )

        console.print(table)


# Allow running as default subcommand
@click.command(name="bootstrap")
@click.option("--no-llm", is_flag=True, help="Skip LLM for fully deterministic scan")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
@click.option("--report", is_flag=True, help="Show what would be bootstrapped without saving")
@click.pass_context
def bootstrap_default(ctx, no_llm: bool, verbose: bool, report: bool) -> None:
    """Run bootstrap scan (shortcut for 'sunwell bootstrap run')."""
    ctx.invoke(bootstrap_run, no_llm=no_llm, verbose=verbose, report=report)
