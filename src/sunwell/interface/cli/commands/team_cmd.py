"""Team Intelligence CLI - RFC-052.

Commands for managing team-shared knowledge:
- status: Show team knowledge summary
- decisions: List/manage team decisions
- failures: List team failure patterns
- patterns: Show/edit enforced patterns
- ownership: Show/edit ownership map
- sync: Synchronize with remote
- onboard: Show onboarding summary

Example usage:
    sunwell team status
    sunwell team decisions --category auth
    sunwell team sync
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def team() -> None:
    """Team Intelligence — shared knowledge across developers.

    \b
    Commands:
        status      Show team knowledge summary
        decisions   List/manage team decisions
        failures    List team failure patterns
        patterns    Show enforced patterns
        ownership   Show ownership map
        sync        Synchronize with remote
        onboard     Show onboarding summary

    \b
    Examples:
        sunwell team status
        sunwell team decisions --category auth
        sunwell team sync
    """


@team.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status(as_json: bool) -> None:
    """Show team knowledge summary."""
    asyncio.run(_show_status(as_json))


async def _show_status(as_json: bool) -> None:
    """Show team knowledge summary."""
    from sunwell.features.team import TeamKnowledgeStore, UnifiedIntelligence

    store = TeamKnowledgeStore(Path.cwd())
    unified = UnifiedIntelligence(team_store=store)

    summary = await unified.get_team_summary()

    if as_json:
        import json

        console.print(json.dumps(summary, indent=2))
        return

    # Header
    console.print(
        Panel(
            "[bold cyan]📊 Team Intelligence Status[/bold cyan]",
            expand=False,
        )
    )

    # Decisions
    decisions_info = summary["decisions"]
    console.print(f"\n[bold]📋 Decisions:[/bold] {decisions_info['total']} recorded")
    for category, count in decisions_info["by_category"].items():
        console.print(f"   - {category}: {count} decisions")

    # Failures
    failures_info = summary["failures"]
    console.print(f"\n[bold]⚠️ Failures:[/bold] {failures_info['total']} patterns recorded")
    for desc in failures_info["top"]:
        console.print(f"   - {desc[:60]}...")

    # Patterns
    patterns_info = summary["patterns"]
    console.print("\n[bold]📝 Patterns:[/bold]")
    console.print(f"   - Enforcement: {patterns_info['enforcement_level']}")
    console.print(f"   - Docstrings: {patterns_info['docstring_style']}")
    console.print(f"   - Type hints: {patterns_info['type_annotations']}")

    # Ownership
    ownership_info = summary["ownership"]
    console.print("\n[bold]👤 Ownership:[/bold]")
    console.print(f"   - Paths mapped: {ownership_info['paths_mapped']}")
    console.print(f"   - Experts: {ownership_info['experts_registered']}")

    # Contributors
    console.print("\n[bold]👥 Top Contributors:[/bold]")
    for contrib in summary["contributors"]:
        console.print(f"   - {contrib['author']}: {contrib['decisions']} decisions")


@team.command()
@click.option("--category", "-c", help="Filter by category")
@click.option("--author", "-a", help="Filter by author")
@click.option("--limit", "-n", default=20, help="Maximum decisions to show")
def decisions(category: str | None, author: str | None, limit: int) -> None:
    """List team decisions."""
    asyncio.run(_list_decisions(category, author, limit))


async def _list_decisions(
    category: str | None,
    author: str | None,
    limit: int,
) -> None:
    """List team decisions."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    all_decisions = await store.get_decisions(category=category)

    # Filter by author if specified
    if author:
        all_decisions = [d for d in all_decisions if author.lower() in d.author.lower()]

    if not all_decisions:
        console.print("[yellow]No team decisions found.[/yellow]")
        return

    table = Table(title=f"Team Decisions ({len(all_decisions)} total)")
    table.add_column("Category", style="cyan")
    table.add_column("Question")
    table.add_column("Choice", style="green")
    table.add_column("Author")
    table.add_column("Endorsements", justify="right")

    for d in all_decisions[:limit]:
        table.add_row(
            d.category,
            d.question[:50] + ("..." if len(d.question) > 50 else ""),
            d.choice[:30] + ("..." if len(d.choice) > 30 else ""),
            d.author,
            str(len(d.endorsements)),
        )

    console.print(table)

    if len(all_decisions) > limit:
        console.print(f"\n[dim]Showing {limit} of {len(all_decisions)}. Use --limit to see more.[/dim]")


@team.command()
@click.argument("decision_id")
def show(decision_id: str) -> None:
    """Show details of a specific decision."""
    asyncio.run(_show_decision(decision_id))


async def _show_decision(decision_id: str) -> None:
    """Show decision details."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    decisions = await store.get_decisions()

    # Find matching decision
    decision = None
    for d in decisions:
        if d.id.startswith(decision_id):
            decision = d
            break

    if not decision:
        console.print(f"[red]Decision not found: {decision_id}[/red]")
        return

    console.print(Panel(f"[bold]{decision.question}[/bold]", title="Decision"))
    console.print(f"\n[bold]ID:[/bold] {decision.id}")
    console.print(f"[bold]Category:[/bold] {decision.category}")
    console.print(f"[bold]Choice:[/bold] {decision.choice}")
    console.print(f"[bold]Author:[/bold] {decision.author}")
    console.print(f"[bold]Timestamp:[/bold] {decision.timestamp}")
    console.print(f"[bold]Confidence:[/bold] {decision.confidence:.0%}")

    if decision.rationale:
        console.print(f"\n[bold]Rationale:[/bold]\n{decision.rationale}")

    if decision.rejected:
        console.print("\n[bold]Rejected Alternatives:[/bold]")
        for r in decision.rejected:
            console.print(f"  - {r.option}: {r.reason}")

    if decision.endorsements:
        console.print(f"\n[bold]Endorsements:[/bold] {', '.join(decision.endorsements)}")

    if decision.tags:
        console.print(f"\n[bold]Tags:[/bold] {', '.join(decision.tags)}")


@team.command()
@click.option("--limit", "-n", default=10, help="Maximum failures to show")
def failures(limit: int) -> None:
    """List team failure patterns."""
    asyncio.run(_list_failures(limit))


async def _list_failures(limit: int) -> None:
    """List team failure patterns."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    all_failures = await store.get_failures()

    if not all_failures:
        console.print("[yellow]No team failure patterns recorded.[/yellow]")
        return

    table = Table(title=f"Team Failure Patterns ({len(all_failures)} total)")
    table.add_column("Description")
    table.add_column("Type", style="magenta")
    table.add_column("Occurrences", justify="right", style="red")
    table.add_column("Prevention", style="green")

    for f in all_failures[:limit]:
        table.add_row(
            f.description[:40] + ("..." if len(f.description) > 40 else ""),
            f.error_type,
            str(f.occurrences),
            f.prevention[:40] + ("..." if len(f.prevention) > 40 else ""),
        )

    console.print(table)


@team.command()
def patterns() -> None:
    """Show enforced team patterns."""
    asyncio.run(_show_patterns())


async def _show_patterns() -> None:
    """Show team patterns."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    patterns = await store.get_patterns()

    console.print(Panel("[bold]📝 Team Code Patterns[/bold]", expand=False))

    console.print(f"\n[bold]Enforcement Level:[/bold] {patterns.enforcement_level}")
    console.print("\n[bold]Naming Conventions:[/bold]")
    if patterns.naming_conventions:
        for k, v in patterns.naming_conventions.items():
            console.print(f"   - {k}: {v}")
    else:
        console.print("   [dim]Not specified[/dim]")

    console.print(f"\n[bold]Import Style:[/bold] {patterns.import_style}")
    console.print(f"[bold]Type Annotations:[/bold] {patterns.type_annotation_level}")
    console.print(f"[bold]Docstring Style:[/bold] {patterns.docstring_style}")

    if patterns.test_requirements:
        console.print("\n[bold]Test Requirements:[/bold]")
        for k, v in patterns.test_requirements.items():
            console.print(f"   - {k}: {v}")

    if patterns.exceptions:
        console.print("\n[bold]Exceptions:[/bold]")
        for path, reason in patterns.exceptions.items():
            console.print(f"   - {path}: {reason}")


@team.command()
def ownership() -> None:
    """Show code ownership map."""
    asyncio.run(_show_ownership())


async def _show_ownership() -> None:
    """Show ownership map."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    ownership = await store.get_ownership()

    console.print(Panel("[bold]👤 Code Ownership Map[/bold]", expand=False))

    if ownership.owners:
        console.print("\n[bold]File Owners:[/bold]")
        table = Table()
        table.add_column("Path Pattern")
        table.add_column("Owners")

        for path, owners in ownership.owners.items():
            table.add_row(path, ", ".join(owners))

        console.print(table)
    else:
        console.print("\n[dim]No ownership mappings defined.[/dim]")

    if ownership.expertise:
        console.print("\n[bold]Expertise Areas:[/bold]")
        for person, areas in ownership.expertise.items():
            console.print(f"   - {person}: {', '.join(areas)}")

    if ownership.required_reviewers:
        console.print("\n[bold]Required Reviewers:[/bold]")
        for path, reviewers in ownership.required_reviewers.items():
            console.print(f"   - {path}: {', '.join(reviewers)}")


@team.command()
@click.option("--push", is_flag=True, help="Push after pulling")
def sync(push: bool) -> None:
    """Synchronize team knowledge with remote."""
    asyncio.run(_sync_team(push))


async def _sync_team(push: bool) -> None:
    """Sync team knowledge."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())

    console.print("[cyan]Syncing team knowledge...[/cyan]")

    result = await store.sync()

    if not result.success:
        console.print(f"[red]Sync failed: {result.error}[/red]")
        if result.conflicts:
            console.print("\n[yellow]Conflicts detected in:[/yellow]")
            for conflict in result.conflicts:
                console.print(f"   - {conflict}")
            console.print("\n[dim]Run `sunwell team conflicts` to resolve.[/dim]")
        return

    console.print("[green]✓ Sync complete[/green]")

    if result.new_decisions:
        console.print(f"\n[bold]New decisions from team ({len(result.new_decisions)}):[/bold]")
        for d in result.new_decisions[:5]:
            console.print(f"   - [{d.category}] {d.question} (by {d.author})")

    if result.new_failures:
        console.print(f"\n[bold]New failure patterns ({len(result.new_failures)}):[/bold]")
        for f in result.new_failures[:5]:
            console.print(f"   - {f.description} (by {f.author})")

    if push:
        console.print("\n[cyan]Pushing changes...[/cyan]")
        success = await store.push()
        if success:
            console.print("[green]✓ Push complete[/green]")
        else:
            console.print("[yellow]Push failed (you may need to pull first)[/yellow]")


@team.command()
def conflicts() -> None:
    """Show and resolve knowledge conflicts."""
    asyncio.run(_show_conflicts())


async def _show_conflicts() -> None:
    """Show conflicts."""
    from sunwell.features.team import ConflictResolver, TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    resolver = ConflictResolver(store)

    # Check for git merge conflicts
    conflicts = await store._detect_conflicts()
    if conflicts:
        console.print("[yellow]Git merge conflicts detected:[/yellow]")
        for conflict in conflicts:
            console.print(f"   - {conflict}")
        console.print("\n[dim]Resolve these manually or use `git mergetool`.[/dim]")
        return

    # Check for decision contradictions
    decisions = await store.get_decisions()
    contradictions = await resolver.detect_contradictions(decisions)

    if not contradictions:
        console.print("[green]No conflicts detected.[/green]")
        return

    console.print(f"[yellow]Found {len(contradictions)} potential contradictions:[/yellow]\n")
    for c in contradictions:
        console.print(Panel(
            f"[bold]Type:[/bold] {c.type}\n"
            f"[bold]Local:[/bold] {c.local_version}\n"
            f"[bold]Remote:[/bold] {c.remote_version}\n\n"
            f"[bold]Suggestion:[/bold]\n{c.suggested_resolution}",
            title="Conflict",
        ))


@team.command()
@click.option("--detailed", "-d", is_flag=True, help="Show detailed summary")
def onboard(detailed: bool) -> None:
    """Show onboarding summary for new team members."""
    asyncio.run(_show_onboarding(detailed))


async def _show_onboarding(detailed: bool) -> None:
    """Show onboarding summary."""
    from sunwell.features.team import TeamKnowledgeStore, TeamOnboarding

    store = TeamKnowledgeStore(Path.cwd())
    onboarding = TeamOnboarding(store)

    summary = await onboarding.generate_onboarding_summary()

    if detailed:
        console.print(summary.format_detailed_summary())
    else:
        console.print(summary.format_welcome_message())

    # Quick tips
    tips = await onboarding.get_quick_tips()
    if tips:
        console.print("\n[bold]💡 Quick Tips:[/bold]")
        for tip in tips:
            console.print(f"   {tip}")


@team.command()
def contributors() -> None:
    """List team knowledge contributors."""
    asyncio.run(_list_contributors())


async def _list_contributors() -> None:
    """List contributors."""
    from collections import Counter

    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    decisions = await store.get_decisions()
    failures = await store.get_failures()

    # Count contributions
    decision_counts = Counter(d.author for d in decisions)
    failure_counts = Counter(f.author for f in failures)

    # Combine
    all_authors = set(decision_counts.keys()) | set(failure_counts.keys())

    table = Table(title="Team Knowledge Contributors")
    table.add_column("Author")
    table.add_column("Decisions", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Total", justify="right", style="bold")

    # Sort by total contributions
    contributions = [
        (
            author,
            decision_counts.get(author, 0),
            failure_counts.get(author, 0),
        )
        for author in all_authors
    ]
    contributions.sort(key=lambda x: x[1] + x[2], reverse=True)

    for author, d_count, f_count in contributions:
        table.add_row(author, str(d_count), str(f_count), str(d_count + f_count))

    console.print(table)


@team.command()
@click.argument("category")
@click.argument("question")
@click.argument("choice")
@click.option("--rationale", "-r", required=True, help="Why this choice was made")
@click.option("--tag", "-t", multiple=True, help="Tags for categorization")
def add_decision(
    category: str,
    question: str,
    choice: str,
    rationale: str,
    tag: tuple[str, ...],
) -> None:
    """Add a new team decision.

    \b
    Example:
        sunwell team add-decision database "Which database?" "PostgreSQL" \\
            --rationale "Better scalability" \\
            --tag database --tag infrastructure
    """
    asyncio.run(_add_decision(category, question, choice, rationale, list(tag)))


async def _add_decision(
    category: str,
    question: str,
    choice: str,
    rationale: str,
    tags: list[str],
) -> None:
    """Add a team decision."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    author = await store.get_git_user()

    decision = await store.create_decision(
        category=category,
        question=question,
        choice=choice,
        rationale=rationale,
        author=author,
        tags=tags,
    )

    console.print(f"[green]✓ Decision recorded: {decision.id}[/green]")
    console.print(f"   Question: {question}")
    console.print(f"   Choice: {choice}")
    console.print(f"   Author: {author}")


@team.command()
@click.argument("decision_id")
def endorse(decision_id: str) -> None:
    """Endorse an existing team decision."""
    asyncio.run(_endorse_decision(decision_id))


async def _endorse_decision(decision_id: str) -> None:
    """Endorse a decision."""
    from sunwell.features.team import TeamKnowledgeStore

    store = TeamKnowledgeStore(Path.cwd())
    author = await store.get_git_user()

    # Find decision
    decisions = await store.get_decisions()
    matching = [d for d in decisions if d.id.startswith(decision_id)]

    if not matching:
        console.print(f"[red]Decision not found: {decision_id}[/red]")
        return

    decision = matching[0]
    updated = await store.endorse_decision(decision.id, author)

    if updated:
        console.print(f"[green]✓ Endorsed decision: {decision.question}[/green]")
        console.print(f"   Total endorsements: {len(updated.endorsements)}")
    else:
        console.print("[yellow]Could not endorse decision[/yellow]")


@team.command()
@click.option("--dry-run", is_flag=True, help="Show what would be migrated")
@click.option("--all", "migrate_all", is_flag=True, help="Migrate all personal decisions")
def migrate(dry_run: bool, migrate_all: bool) -> None:
    """Migrate personal decisions to team knowledge.

    \b
    This promotes RFC-045 personal decisions to RFC-052 team decisions.

    \b
    Example:
        sunwell team migrate --dry-run     # Preview what would be migrated
        sunwell team migrate --all         # Migrate all personal decisions
    """
    asyncio.run(_migrate_decisions(dry_run, migrate_all))


async def _migrate_decisions(dry_run: bool, migrate_all: bool) -> None:
    """Migrate personal decisions to team."""
    from sunwell.knowledge.codebase.decisions import DecisionMemory
    from sunwell.features.team import KnowledgePropagator, TeamKnowledgeStore

    intelligence_path = Path.cwd() / ".sunwell" / "intelligence"
    if not intelligence_path.exists():
        console.print("[yellow]No personal decisions found (.sunwell/intelligence/ does not exist)[/yellow]")
        return

    personal_store = DecisionMemory(base_path=intelligence_path)
    team_store = TeamKnowledgeStore(Path.cwd())
    propagator = KnowledgePropagator(team_store, personal_store)

    # Get existing team decision IDs
    team_decisions = await team_store.get_decisions()
    team_ids = {d.id for d in team_decisions}

    # Get personal decisions
    personal_decisions = await personal_store.get_decisions(active_only=True)

    # Filter to those not already in team
    candidates = [d for d in personal_decisions if d.id not in team_ids]

    if not candidates:
        console.print("[green]No new decisions to migrate.[/green]")
        return

    # Show candidates
    console.print(f"\n[bold]Found {len(candidates)} personal decisions to migrate:[/bold]\n")

    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Category")
    table.add_column("Question")
    table.add_column("Choice", style="green")
    table.add_column("Confidence")
    table.add_column("Promote?", style="yellow")

    for d in candidates:
        should_promote = await propagator.should_promote(d)
        table.add_row(
            d.id[:8] + "...",
            d.category,
            d.question[:35] + ("..." if len(d.question) > 35 else ""),
            d.choice[:25] + ("..." if len(d.choice) > 25 else ""),
            f"{d.confidence:.0%}",
            "✓" if should_promote else "-",
        )

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made. Remove --dry-run to migrate.[/yellow]")
        return

    if not migrate_all:
        console.print("\n[yellow]Use --all to migrate all decisions.[/yellow]")
        return

    # Perform migration
    console.print("\n[cyan]Migrating decisions to team knowledge...[/cyan]")

    author = await team_store.get_git_user()
    migrated = 0

    for d in candidates:
        try:
            await propagator.promote_to_team(d, author)
            console.print(f"  [green]✓[/green] {d.question[:50]}...")
            migrated += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {d.question[:50]}... ({e})")

    console.print(f"\n[green]✓ Migrated {migrated}/{len(candidates)} decisions to team knowledge[/green]")


@team.command()
def init() -> None:
    """Initialize team intelligence for this project.

    \b
    Creates:
    - .sunwell/team/ directory (git-tracked)
    - .sunwell/.gitignore (proper ignore rules)
    - Shows team onboarding if knowledge exists
    """
    asyncio.run(_init_team())


async def _init_team() -> None:
    """Initialize team intelligence."""
    from sunwell.features.team import TeamKnowledgeStore, TeamOnboarding
    from sunwell.features.team.gitignore_template import ensure_sunwell_structure

    project_root = Path.cwd()

    console.print("[cyan]Initializing team intelligence...[/cyan]")

    # Ensure directory structure
    ensure_sunwell_structure(project_root)
    console.print("  [green]✓[/green] Created .sunwell/ directory structure")
    console.print("  [green]✓[/green] Created .sunwell/.gitignore")

    # Initialize store
    store = TeamKnowledgeStore(project_root)

    # Check for existing team knowledge
    decisions = await store.get_decisions()
    failures = await store.get_failures()

    if decisions or failures:
        console.print("\n[bold]Existing team knowledge found:[/bold]")
        console.print(f"  - {len(decisions)} decisions")
        console.print(f"  - {len(failures)} failure patterns")

        # Show onboarding
        onboarding = TeamOnboarding(store)
        summary = await onboarding.generate_onboarding_summary()
        console.print(summary.format_welcome_message())
    else:
        console.print("\n[dim]No existing team knowledge found. Start adding decisions:[/dim]")
        console.print("  sunwell team add-decision <category> <question> <choice> -r <rationale>")

    console.print("\n[green]✓ Team intelligence initialized[/green]")
    console.print("\n[dim]Remember to commit .sunwell/team/ to share with your team.[/dim]")
