"""Memory CLI commands for debugging and observability.

Provides visibility into the memory system:
- What content is retrieved for queries
- Memory system health and integrity
- Manual tier maintenance

Commands:
    sunwell memory inspect <query>  - Debug retrieval for a query
    sunwell memory health           - Check memory system health
    sunwell memory compact          - Manual tier maintenance
    sunwell memory stats            - Memory statistics
"""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


def get_memory_path() -> Path:
    """Get the memory storage path."""
    return Path(".sunwell/memory")


@click.group()
def memory() -> None:
    """Memory system debugging and observability.

    \b
    Debug retrieval:
        sunwell memory inspect "authentication bug"

    \b
    Check health:
        sunwell memory health

    \b
    View stats:
        sunwell memory stats
    """
    pass


# =============================================================================
# Inspect Command
# =============================================================================


@memory.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Number of results to show per category")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def inspect(query: str, limit: int, as_json: bool) -> None:
    """Debug memory retrieval for a query.

    Shows WHY specific results were retrieved:
    - Semantic matches found
    - Focus weights affecting ranking
    - Tier distribution
    - Matching learnings and episodes

    \b
    Examples:
        sunwell memory inspect "authentication bug"
        sunwell memory inspect "API endpoint" --limit 5
        sunwell memory inspect "database query" --json
    """
    asyncio.run(_inspect_async(query, limit, as_json))


async def _inspect_async(query: str, limit: int, as_json: bool) -> None:
    """Async implementation of inspect command."""
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    memory_path = get_memory_path()

    if not memory_path.exists():
        if as_json:
            click.echo(json.dumps({"error": "No memory found"}, indent=2))
        else:
            console.print("[yellow]No memory found. Start a session first.[/yellow]")
        return

    # Initialize store
    store = SimulacrumStore(base_path=memory_path)

    # Try to set up embedder if available
    try:
        from sunwell.knowledge.embedding import create_embedder
        embedder = create_embedder()
        store.set_embedder(embedder)
    except Exception:
        pass  # Embedder optional

    # Get debug info
    debug_info = await store.debug_retrieval(query, limit=limit)

    if as_json:
        click.echo(json.dumps(debug_info, indent=2))
        return

    # Display results
    console.print(f"\n[bold]Memory Retrieval Debug: [cyan]{query}[/cyan][/bold]\n")

    # Query embedding
    emb_info = debug_info.get("query_embedding", {})
    if "error" in emb_info:
        console.print(f"[yellow]⚠ Embedding Error:[/yellow] {emb_info['error']}")
    elif "status" in emb_info:
        console.print(f"[yellow]⚠ Embeddings:[/yellow] {emb_info['status']}")
    else:
        console.print(f"[green]✓ Query Embedding:[/green] {emb_info['dimensions']} dimensions")

    # Semantic matches
    console.print("\n[bold]Semantic Matches:[/bold]")
    matches = debug_info.get("semantic_matches", [])
    if isinstance(matches, dict) and "error" in matches:
        console.print(f"  [yellow]{matches['error']}[/yellow]")
    elif isinstance(matches, dict) and "status" in matches:
        console.print(f"  [yellow]{matches['status']}[/yellow]")
    elif matches:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Chunk ID", style="cyan")
        table.add_column("Tier", style="yellow")
        table.add_column("Turns", justify="right")
        table.add_column("Preview")

        for match in matches:
            table.add_row(
                match["chunk_id"][:8],
                match["tier"],
                str(match["turn_count"]),
                match["preview"],
            )
        console.print(table)
    else:
        console.print("  [dim]No semantic matches found[/dim]")

    # Focus weights
    console.print("\n[bold]Focus Weights:[/bold]")
    focus = debug_info.get("focus_weights", {})
    if "status" in focus:
        console.print(f"  [yellow]{focus['status']}[/yellow]")
    elif "error" in focus:
        console.print(f"  [yellow]{focus['error']}[/yellow]")
    elif focus.get("active_topics", 0) > 0:
        top_topics = focus.get("top_topics", [])
        explicit = focus.get("explicit_topics", [])
        for topic, weight in top_topics:
            explicit_marker = " [bold](explicit)[/bold]" if topic in explicit else ""
            console.print(f"  • {topic}: {weight:.2f}{explicit_marker}")
    else:
        console.print("  [dim]No active focus[/dim]")

    # Tier distribution
    console.print("\n[bold]Tier Distribution:[/bold]")
    tiers = debug_info.get("tier_distribution", {})
    console.print(f"  HOT:  {tiers.get('hot', 0):3d} turns")
    console.print(f"  WARM: {tiers.get('warm', 0):3d} chunks")
    console.print(f"  COLD: {tiers.get('cold', 0):3d} archives")

    # Matching learnings
    learnings = debug_info.get("matching_learnings", [])
    if learnings:
        console.print("\n[bold]Matching Learnings:[/bold]")
        for learning in learnings:
            console.print(
                f"  • [{learning['category']}] {learning['fact']} "
                f"(confidence: {learning['confidence']:.2f})"
            )

    # Matching episodes
    episodes = debug_info.get("matching_episodes", [])
    if episodes:
        console.print("\n[bold]Matching Episodes:[/bold]")
        for ep in episodes:
            relevance_color = "green" if ep["relevance"] == "high" else "yellow"
            console.print(
                f"  • [{relevance_color}]{ep['outcome']}[/{relevance_color}]: "
                f"{ep['summary']}"
            )


# =============================================================================
# Health Command
# =============================================================================


@memory.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def health(as_json: bool) -> None:
    """Check memory system health.

    Validates:
    - Tier balance (hot not overflowing)
    - Embeddings status
    - Topology coverage
    - Storage consistency

    \b
    Examples:
        sunwell memory health
        sunwell memory health --json
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    memory_path = get_memory_path()

    if not memory_path.exists():
        if as_json:
            click.echo(json.dumps({"error": "No memory found"}, indent=2))
        else:
            console.print("[yellow]No memory found. Start a session first.[/yellow]")
        return

    # Initialize store
    store = SimulacrumStore(base_path=memory_path)

    # Get health info
    health_info = store.health_check()

    if as_json:
        click.echo(json.dumps(health_info, indent=2))
        return

    # Display results
    overall_status = health_info["overall_status"]
    status_colors = {
        "healthy": "green",
        "degraded": "yellow",
        "error": "red",
    }
    status_color = status_colors.get(overall_status, "white")

    console.print(f"\n[bold]Memory System Health[/bold]")
    console.print(f"Overall Status: [{status_color}]{overall_status.upper()}[/{status_color}]\n")

    # Build health tree
    tree = Tree("[bold]Health Checks[/bold]")

    checks = health_info.get("checks", {})
    for check_name, check_data in checks.items():
        status = check_data.get("status", "unknown")
        status_emoji = {
            "ok": "✓",
            "warning": "⚠",
            "critical": "✗",
            "error": "✗",
            "missing": "⚠",
        }.get(status, "?")

        status_color = {
            "ok": "green",
            "warning": "yellow",
            "critical": "red",
            "error": "red",
            "missing": "yellow",
        }.get(status, "white")

        branch = tree.add(f"[{status_color}]{status_emoji}[/{status_color}] {check_name}")

        # Add details
        for key, value in check_data.items():
            if key != "status":
                branch.add(f"{key}: {value}")

    console.print(tree)

    # Health advice
    if overall_status != "healthy":
        console.print("\n[bold yellow]Recommendations:[/bold yellow]")
        if checks.get("hot_tier", {}).get("status") in ("warning", "critical"):
            console.print("  • Hot tier is full. Run: [cyan]sunwell memory compact[/cyan]")
        if checks.get("embeddings", {}).get("status") == "warning":
            console.print("  • Embeddings not available. Install sentence-transformers for semantic search.")
        if checks.get("chunks", {}).get("status") == "missing":
            console.print("  • Chunk manager not initialized. Memory system may not be fully functional.")


# =============================================================================
# Compact Command
# =============================================================================


@memory.command()
@click.option("--older-than", "-o", type=int, help="Archive warm chunks older than N hours")
@click.option("--dry-run", is_flag=True, help="Show what would be archived without doing it")
def compact(older_than: int | None, dry_run: bool) -> None:
    """Manual tier maintenance.

    Moves old content from hot → warm → cold tiers.

    \b
    Examples:
        sunwell memory compact
        sunwell memory compact --older-than 24
        sunwell memory compact --dry-run
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    memory_path = get_memory_path()

    if not memory_path.exists():
        console.print("[yellow]No memory found. Start a session first.[/yellow]")
        return

    # Initialize store
    store = SimulacrumStore(base_path=memory_path)

    console.print("\n[bold]Memory Compaction[/bold]\n")

    # Show current state
    stats_before = store.stats()
    console.print(f"Before: HOT={stats_before['hot_turns']} WARM={stats_before['warm_files']} "
                  f"COLD={stats_before['cold_files']}")

    if dry_run:
        console.print("\n[yellow]DRY RUN - No changes will be made[/yellow]")
        return

    # Perform compaction
    with console.status("[bold green]Compacting tiers..."):
        # Move compressed to archived
        archived = store.move_to_archived(older_than_hours=older_than)

    stats_after = store.stats()
    console.print(f"After:  HOT={stats_after['hot_turns']} WARM={stats_after['warm_files']} "
                  f"COLD={stats_after['cold_files']}")

    if archived > 0:
        console.print(f"\n[green]✓ Archived {archived} warm chunks to cold storage[/green]")
    else:
        console.print("\n[dim]No chunks needed archiving[/dim]")


# =============================================================================
# Stats Command
# =============================================================================


@memory.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def stats(as_json: bool) -> None:
    """Show memory statistics.

    \b
    Examples:
        sunwell memory stats
        sunwell memory stats --json
    """
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

    memory_path = get_memory_path()

    if not memory_path.exists():
        if as_json:
            click.echo(json.dumps({"error": "No memory found"}, indent=2))
        else:
            console.print("[yellow]No memory found. Start a session first.[/yellow]")
        return

    # Initialize store
    store = SimulacrumStore(base_path=memory_path)

    # Get stats
    stats_info = store.stats()

    if as_json:
        click.echo(json.dumps(stats_info, indent=2))
        return

    # Display stats
    console.print("\n[bold]Memory Statistics[/bold]\n")

    console.print(f"Session: {stats_info['session_id']}")
    console.print(f"Hot turns: {stats_info['hot_turns']}")
    console.print(f"Warm files: {stats_info['warm_files']} ({stats_info['warm_size_mb']:.2f} MB)")
    console.print(f"Cold files: {stats_info['cold_files']} ({stats_info['cold_size_mb']:.2f} MB)")

    # Chunk stats
    if "chunk_stats" in stats_info:
        console.print("\n[bold]Chunk Statistics:[/bold]")
        chunk_stats = stats_info["chunk_stats"]
        for key, value in chunk_stats.items():
            console.print(f"  {key}: {value}")

    # Unified store stats
    if "unified_store" in stats_info:
        console.print("\n[bold]Unified Store:[/bold]")
        unified = stats_info["unified_store"]
        console.print(f"  Total nodes: {unified['total_nodes']}")
        console.print(f"  Total edges: {unified['total_edges']}")
        console.print(f"  Facet index size: {unified['facet_index_size']}")

    # DAG stats
    if "dag_stats" in stats_info:
        console.print("\n[bold]DAG Statistics:[/bold]")
        dag_stats = stats_info["dag_stats"]
        for key, value in dag_stats.items():
            console.print(f"  {key}: {value}")
