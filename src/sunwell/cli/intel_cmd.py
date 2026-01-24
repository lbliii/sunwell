"""Intelligence commands - RFC-045 Project Intelligence CLI.

View and manage project intelligence: decisions, failures, patterns, codebase graph.
"""


import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sunwell.intelligence import ProjectIntelligence

console = Console()


@click.group(name="intel")
def intel() -> None:
    """Project Intelligence - View and manage persistent codebase knowledge.

    RFC-045: The Persistent Codebase Mind

    Commands:
    - status: Show intelligence status summary
    - decisions: View architectural decisions
    - failures: View failed approaches
    - patterns: View learned patterns
    - scan: Force full codebase scan
    """
    pass


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
def status(project_root: str) -> None:
    """Show project intelligence status summary."""
    project_path = Path(project_root)
    intel_path = project_path / ".sunwell" / "intelligence"

    if not intel_path.exists():
        console.print("[yellow]No intelligence data found. Run 'sunwell intel scan' to initialize.[/yellow]")
        return

    # Load intelligence
    async def _show_status():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        # Count decisions
        decisions = await context.decisions.get_decisions(active_only=True)
        decision_count = len(decisions)
        recent_decisions = [d for d in decisions if d.timestamp][:5]

        # Count failures
        failures = list(context.failures._failures.values())
        failure_count = len(failures)
        recent_failures = failures[-5:] if failures else []

        # Get patterns
        patterns = context.patterns

        # Build status table
        table = Table(title="📊 Project Intelligence Status", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Details", style="yellow")

        table.add_row("Decisions", str(decision_count), f"{len(recent_decisions)} recent")
        table.add_row("Failures", str(failure_count), f"{len(recent_failures)} recent")
        table.add_row("Patterns", "Learned" if patterns.confidence else "None", f"{len(patterns.confidence)} patterns")
        table.add_row("Codebase Graph", "Loaded" if context.codebase.call_graph else "Not scanned", f"{len(context.codebase.call_graph)} functions")

        console.print(table)

        # Show recent decisions
        if recent_decisions:
            console.print("\n[bold]Recent Decisions:[/bold]")
            for decision in recent_decisions[:3]:
                console.print(f"  • {decision.category}: {decision.choice}")

        # Show recent failures
        if recent_failures:
            console.print("\n[bold]Recent Failures:[/bold]")
            for failure in recent_failures[:3]:
                console.print(f"  • {failure.error_type}: {failure.description[:50]}...")

    asyncio.run(_show_status())


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
@click.option("--category", help="Filter by category")
@click.option("--query", help="Search query")
@click.option("--limit", default=10, help="Maximum results")
def decisions(project_root: str, category: str | None, query: str | None, limit: int) -> None:
    """View architectural decisions."""
    project_path = Path(project_root)

    async def _show_decisions():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        if query:
            decisions_list = await context.decisions.find_relevant_decisions(query, top_k=limit)
        else:
            decisions_list = await context.decisions.get_decisions(
                category=category,
                active_only=True,
            )[:limit]

        if not decisions_list:
            console.print("[yellow]No decisions found.[/yellow]")
            return

        table = Table(title="📋 Architectural Decisions", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Question", style="white")
        table.add_column("Choice", style="green")
        table.add_column("Date", style="yellow")

        for decision in decisions_list:
            date_str = decision.timestamp.strftime("%Y-%m-%d") if decision.timestamp else "Unknown"
            table.add_row(
                decision.category,
                decision.question[:50] + "..." if len(decision.question) > 50 else decision.question,
                decision.choice[:40] + "..." if len(decision.choice) > 40 else decision.choice,
                date_str,
            )

        console.print(table)

        # Show details for first decision
        if decisions_list:
            decision = decisions_list[0]
            console.print("\n[bold]Details:[/bold]")
            console.print(Panel(
                f"[bold]Question:[/bold] {decision.question}\n"
                f"[bold]Choice:[/bold] {decision.choice}\n"
                f"[bold]Rationale:[/bold] {decision.rationale}\n"
                + (f"[bold]Rejected:[/bold] {', '.join(r.option for r in decision.rejected)}\n" if decision.rejected else "")
                + f"[bold]Confidence:[/bold] {decision.confidence:.0%}",
                title=f"Decision: {decision.category}",
                border_style="blue",
            ))

    asyncio.run(_show_decisions())


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
@click.option("--query", help="Search query")
@click.option("--limit", default=10, help="Maximum results")
@click.option("--recent", type=int, help="Show only recent N failures")
def failures(project_root: str, query: str | None, limit: int, recent: int | None) -> None:
    """View failed approaches."""
    project_path = Path(project_root)

    async def _show_failures():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        if query:
            failures_list = await context.failures.check_similar_failures(query, top_k=limit)
        else:
            failures_list = list(context.failures._failures.values())
            if recent:
                failures_list = failures_list[-recent:]
            failures_list = failures_list[:limit]

        if not failures_list:
            console.print("[yellow]No failures recorded.[/yellow]")
            return

        table = Table(title="🔴 Failed Approaches", show_header=True, header_style="bold magenta")
        table.add_column("Type", style="red")
        table.add_column("Description", style="white")
        table.add_column("Error", style="yellow")
        table.add_column("Date", style="cyan")

        for failure in failures_list:
            date_str = failure.timestamp.strftime("%Y-%m-%d") if failure.timestamp else "Unknown"
            error_preview = failure.error_message[:40] + "..." if len(failure.error_message) > 40 else failure.error_message
            table.add_row(
                failure.error_type,
                failure.description[:40] + "..." if len(failure.description) > 40 else failure.description,
                error_preview,
                date_str,
            )

        console.print(table)

        # Show patterns
        patterns = await context.failures.get_failure_patterns()
        if patterns:
            console.print("\n[bold]Recurring Patterns:[/bold]")
            for pattern in patterns[:5]:
                console.print(f"  • {pattern['pattern']}: {pattern['count']} occurrences")

    asyncio.run(_show_failures())


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
def patterns(project_root: str) -> None:
    """View learned patterns."""
    project_path = Path(project_root)

    async def _show_patterns():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        patterns = context.patterns

        if not patterns.confidence:
            console.print("[yellow]No patterns learned yet.[/yellow]")
            console.print("[dim]Patterns are learned automatically from your edits and preferences.[/dim]")
            return

        console.print("[bold]📝 Learned Patterns[/bold]\n")

        # Code style
        if patterns.naming_conventions:
            console.print("[bold cyan]Naming Conventions:[/bold cyan]")
            for key, value in patterns.naming_conventions.items():
                confidence = patterns.confidence.get(f"naming_{key}", 0.0)
                console.print(f"  • {key}: {value} ({confidence:.0%} confidence)")

        # Type annotations
        if patterns.type_annotation_level != "public":
            confidence = patterns.confidence.get("type_annotations", 0.0)
            console.print(f"\n[bold cyan]Type Annotations:[/bold cyan] {patterns.type_annotation_level} ({confidence:.0%} confidence)")

        # Docstring style
        if patterns.docstring_style != "google":
            confidence = patterns.confidence.get("docstring_style", 0.0)
            console.print(f"\n[bold cyan]Docstring Style:[/bold cyan] {patterns.docstring_style} ({confidence:.0%} confidence)")

        # Communication preferences
        console.print("\n[bold cyan]Communication:[/bold cyan]")
        console.print(f"  • Explanation verbosity: {patterns.explanation_verbosity:.0%}")
        console.print(f"  • Code comment level: {patterns.code_comment_level:.0%}")
        console.print(f"  • Prefers questions: {patterns.prefers_questions}")

    asyncio.run(_show_patterns())


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
@click.option("--force", is_flag=True, help="Force full scan even if graph exists")
def scan(project_root: str, force: bool) -> None:
    """Force full codebase scan to rebuild codebase graph."""
    project_path = Path(project_root)

    async def _scan():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        graph_path = context.decisions.base_path / "codebase" / "graph.pickle"
        if graph_path.exists() and not force:
            console.print("[yellow]Codebase graph already exists. Use --force to rebuild.[/yellow]")
            return

        console.print("[bold]Scanning codebase...[/bold]")
        from sunwell.intelligence.codebase import CodebaseAnalyzer

        analyzer = CodebaseAnalyzer()
        graph = await analyzer.full_scan(project_path)

        # Save graph
        graph.save(base_path=context.decisions.base_path)

        console.print("[green]✓[/green] Scan complete!")
        console.print(f"  • Functions: {len(graph.call_graph)}")
        console.print(f"  • Modules: {len(graph.import_graph)}")
        console.print(f"  • Classes: {len(graph.class_hierarchy)}")

    asyncio.run(_scan())


@intel.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
@click.argument("category")
@click.argument("question")
@click.argument("choice")
@click.option("--rejected", multiple=True, help="Rejected options (format: option:reason)")
@click.option("--rationale", required=True, help="Why this choice was made")
def record_decision(
    project_root: str,
    category: str,
    question: str,
    choice: str,
    rejected: tuple[str, ...],
    rationale: str,
) -> None:
    """Manually record an architectural decision."""
    project_path = Path(project_root)

    async def _record():
        intelligence = ProjectIntelligence(project_root=project_path)
        context = await intelligence.load()

        rejected_list = []
        for item in rejected:
            if ":" in item:
                opt, reason = item.split(":", 1)
                rejected_list.append((opt.strip(), reason.strip()))
            else:
                rejected_list.append((item.strip(), ""))

        decision = await context.decisions.record_decision(
            category=category,
            question=question,
            choice=choice,
            rejected=rejected_list,
            rationale=rationale,
        )

        console.print(f"[green]✓[/green] Decision recorded: {decision.id}")
        console.print(f"  Category: {category}")
        console.print(f"  Choice: {choice}")

    asyncio.run(_record())
