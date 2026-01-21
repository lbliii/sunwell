"""DAG and incremental execution CLI commands (RFC-074).

Provides visibility into artifact graph execution planning,
cache state, and impact analysis.

Commands:
    sunwell dag plan       - Show execution plan (what will execute vs skip)
    sunwell dag impact     - Show what changes if an artifact is modified
    sunwell dag cache      - Manage execution cache
"""

from datetime import UTC
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Default cache location
DEFAULT_CACHE_PATH = Path(".sunwell/cache/execution.db")


def get_cache_path() -> Path:
    """Get the execution cache path."""
    return DEFAULT_CACHE_PATH


@click.group()
def dag() -> None:
    """DAG execution and incremental cache management.

    \b
    View execution plans:
        sunwell dag plan

    \b
    Analyze change impact:
        sunwell dag impact UserModel

    \b
    Manage cache:
        sunwell dag cache stats
        sunwell dag cache clear
    """
    pass


# =============================================================================
# Plan Command
# =============================================================================


@dag.command()
@click.option("--goal", "-g", help="Goal to plan for (loads from saved state if omitted)")
@click.option("--force", "-f", multiple=True, help="Force re-run specific artifacts")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def plan(goal: str | None, force: tuple[str, ...], as_json: bool) -> None:
    """Show execution plan without running.

    \b
    Examples:
        sunwell dag plan
        sunwell dag plan --force artifact_a --force artifact_b
        sunwell dag plan --json
    """
    import json as json_module
    from datetime import datetime

    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        if as_json:
            result = {
                "toExecute": [],
                "toSkip": [],
                "skipPercentage": 0,
                "decisions": [],
                "cacheStats": None,
            }
            click.echo(json_module.dumps(result, indent=2))
        else:
            console.print("[yellow]No cache found. Run an execution first.[/yellow]")
        return

    cache = ExecutionCache(cache_path)

    # Get all artifacts and their status
    artifacts = cache.list_artifacts()
    stats = cache.get_stats()

    # Categorize artifacts
    force_set = set(force)
    to_execute = []
    to_skip = []
    decisions = []

    for artifact in artifacts:
        artifact_id = artifact["artifact_id"]
        status = artifact["status"]
        is_forced = artifact_id in force_set

        # Determine if this would be skipped or executed
        # Skippable if: completed + not forced
        can_skip = status == "completed" and not is_forced

        if is_forced:
            reason = "force_rerun"
        elif status == "completed":
            reason = "unchanged_success"
        elif status == "failed":
            reason = "previous_failed"
        elif status in ("pending", "running"):
            reason = "no_cache"
        else:
            reason = "no_cache"

        # Format timestamp
        last_executed_at = None
        if artifact["executed_at"]:
            dt = datetime.fromtimestamp(artifact["executed_at"], tz=UTC)
            last_executed_at = dt.isoformat()

        decision = {
            "artifactId": artifact_id,
            "canSkip": can_skip,
            "reason": reason,
            "currentHash": artifact["input_hash"],
            "previousHash": artifact["input_hash"],  # Same for cache display
            "lastExecutedAt": last_executed_at,
        }

        decisions.append(decision)

        if can_skip:
            to_skip.append(artifact_id)
        else:
            to_execute.append(artifact_id)

    total = len(artifacts)
    skip_percentage = (len(to_skip) / total * 100) if total > 0 else 0

    if as_json:
        result = {
            "toExecute": to_execute,
            "toSkip": to_skip,
            "skipPercentage": skip_percentage,
            "decisions": decisions,
            "cacheStats": {
                "byStatus": stats.get("by_status", {}),
                "totalSkips": stats.get("total_skips", 0),
                "avgExecutionTimeMs": stats.get("avg_execution_time_ms", 0),
                "totalArtifacts": stats.get("total_artifacts", 0),
            },
        }
        click.echo(json_module.dumps(result, indent=2))
        return

    # Display execution plan summary
    console.print("\n[bold]Execution Plan[/bold]")
    console.print("─" * 40)

    console.print(f"\n[green]● Skip (cached):[/green] {len(to_skip)} artifacts")
    for artifact_id in to_skip[:5]:
        console.print(f"    {artifact_id}")
    if len(to_skip) > 5:
        console.print(f"    ... and {len(to_skip) - 5} more")

    console.print(f"\n[yellow]○ Execute:[/yellow] {len(to_execute)} artifacts")
    for artifact_id in to_execute[:5]:
        console.print(f"    {artifact_id}")
    if len(to_execute) > 5:
        console.print(f"    ... and {len(to_execute) - 5} more")

    console.print(f"\n[bold]Summary:[/bold] {skip_percentage:.0f}% cache savings")

    if force:
        console.print(f"\n[yellow]Forced re-run: {', '.join(force)}[/yellow]")


# =============================================================================
# Impact Command
# =============================================================================


@dag.command()
@click.argument("artifact_id")
@click.option("--depth", "-d", default=100, help="Maximum traversal depth")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def impact(artifact_id: str, depth: int, as_json: bool) -> None:
    """Analyze impact of changing an artifact.

    Shows which artifacts would need to be re-executed if the specified
    artifact is modified.

    \b
    Examples:
        sunwell dag impact UserModel
        sunwell dag impact UserModel --depth 3
        sunwell dag impact UserModel --json
    """
    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        console.print("[yellow]No cache found. Run an execution first.[/yellow]")
        return

    cache = ExecutionCache(cache_path)

    # Get provenance data
    direct_deps = cache.get_direct_dependencies(artifact_id)
    direct_dependents = cache.get_direct_dependents(artifact_id)
    upstream = cache.get_upstream(artifact_id, max_depth=depth)
    downstream = cache.get_downstream(artifact_id, max_depth=depth)

    result = {
        "artifact": artifact_id,
        "direct_dependencies": direct_deps,
        "direct_dependents": direct_dependents,
        "transitive_dependencies": upstream,
        "transitive_dependents": downstream,
        "would_invalidate": len(downstream),
    }

    if as_json:
        import json

        click.echo(json.dumps(result, indent=2))
        return

    console.print(f"\n[bold]Impact Analysis: {artifact_id}[/bold]")
    console.print("─" * 40)

    # Upstream (dependencies)
    if upstream:
        console.print(f"\n[cyan]Dependencies (upstream):[/cyan] {len(upstream)}")
        for dep in upstream[:10]:
            marker = "•" if dep in direct_deps else "  └"
            console.print(f"  {marker} {dep}")
        if len(upstream) > 10:
            console.print(f"  ... and {len(upstream) - 10} more")
    else:
        console.print("\n[dim]No dependencies (leaf artifact)[/dim]")

    # Downstream (dependents - would be invalidated)
    if downstream:
        console.print(f"\n[yellow]Would invalidate (downstream):[/yellow] {len(downstream)}")
        for dep in downstream[:10]:
            marker = "•" if dep in direct_dependents else "  └"
            console.print(f"  {marker} {dep}")
        if len(downstream) > 10:
            console.print(f"  ... and {len(downstream) - 10} more")
    else:
        console.print("\n[green]No dependents (root artifact)[/green]")

    console.print()


# =============================================================================
# Cache Commands
# =============================================================================


@dag.group()
def cache() -> None:
    """Manage execution cache.

    \b
    View statistics:
        sunwell dag cache stats

    \b
    Clear cache:
        sunwell dag cache clear
        sunwell dag cache clear --artifact UserModel
    """
    pass


@cache.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def stats(as_json: bool) -> None:
    """Show cache statistics.

    \b
    Examples:
        sunwell dag cache stats
        sunwell dag cache stats --json
    """
    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        console.print("[yellow]No cache found at .sunwell/cache/execution.db[/yellow]")
        return

    cache = ExecutionCache(cache_path)
    cache_stats = cache.get_stats()

    # Add file info
    cache_stats["cache_path"] = str(cache_path)
    cache_stats["cache_size_kb"] = cache_path.stat().st_size / 1024

    if as_json:
        import json

        click.echo(json.dumps(cache_stats, indent=2))
        return

    console.print("\n[bold]Execution Cache Statistics[/bold]")
    console.print("─" * 40)

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Location", str(cache_path))
    table.add_row("Size", f"{cache_stats['cache_size_kb']:.1f} KB")
    table.add_row("Total entries", str(cache_stats.get("total_artifacts", 0)))

    console.print(table)

    # Status breakdown
    by_status = cache_stats.get("by_status", {})
    if by_status:
        console.print("\n[bold]By Status:[/bold]")
        for status, count in sorted(by_status.items()):
            icon = {
                "completed": "✅",
                "failed": "❌",
                "pending": "⏳",
                "running": "🔄",
                "skipped": "⏭️",
            }.get(status, "•")
            console.print(f"  {icon} {status}: {count}")

    # Cache effectiveness
    total_skips = cache_stats.get("total_skips", 0)
    if total_skips > 0:
        console.print("\n[bold]Cache Effectiveness:[/bold]")
        console.print(f"  Total cache hits: {total_skips}")
        avg_time = cache_stats.get("avg_execution_time_ms", 0)
        saved_time = cache_stats.get("estimated_time_saved_ms", 0)
        console.print(f"  Avg execution time: {avg_time:.0f}ms")
        console.print(f"  Estimated time saved: {saved_time / 1000:.1f}s")
        console.print(f"  Cache hit rate: {cache_stats.get('cache_hit_rate', 0):.1f}%")

    console.print()


@cache.command()
@click.option("--artifact", "-a", help="Clear specific artifact only")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def clear(artifact: str | None, force: bool) -> None:
    """Clear execution cache.

    \b
    Examples:
        sunwell dag cache clear              # Clear all
        sunwell dag cache clear -a UserModel # Clear specific artifact
        sunwell dag cache clear --force      # Skip confirmation
    """
    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        console.print("[yellow]No cache found.[/yellow]")
        return

    cache = ExecutionCache(cache_path)

    if artifact:
        # Clear specific artifact
        if not force and not click.confirm(f"Clear cache for '{artifact}'?"):
            console.print("[dim]Cancelled[/dim]")
            return

        deleted = cache.clear_artifact(artifact)
        if deleted:
            console.print(f"[green]✓ Cleared cache for '{artifact}'[/green]")
        else:
            console.print(f"[yellow]Artifact '{artifact}' not found in cache[/yellow]")
    else:
        # Clear all
        cache_stats = cache.get_stats()
        total = cache_stats.get("total_artifacts", 0)

        if not force and not click.confirm(f"Clear entire cache ({total} entries)?"):
            console.print("[dim]Cancelled[/dim]")
            return

        cache.clear()
        cache.vacuum()
        console.print(f"[green]✓ Cleared {total} cache entries[/green]")


@cache.command()
def vacuum() -> None:
    """Compact the cache database to reclaim space.

    \b
    Example:
        sunwell dag cache vacuum
    """
    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        console.print("[yellow]No cache found.[/yellow]")
        return

    size_before = cache_path.stat().st_size

    cache = ExecutionCache(cache_path)
    cache.vacuum()

    size_after = cache_path.stat().st_size
    saved = size_before - size_after

    console.print("[green]✓ Vacuumed cache[/green]")
    console.print(f"  Before: {size_before / 1024:.1f} KB")
    console.print(f"  After:  {size_after / 1024:.1f} KB")
    console.print(f"  Saved:  {saved / 1024:.1f} KB")


# =============================================================================
# Provenance Commands
# =============================================================================


# =============================================================================
# Migration Command
# =============================================================================


@cache.command()
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without doing it")
@click.option("--source", default=".sunwell/plans", help="Source directory for old JSON files")
def migrate(dry_run: bool, source: str) -> None:
    """Migrate from JSON files to SQLite cache (RFC-074).

    Reads execution state from .sunwell/plans/*.json and imports
    into the new SQLite cache at .sunwell/cache/execution.db.

    \b
    Examples:
        sunwell dag cache migrate
        sunwell dag cache migrate --dry-run
        sunwell dag cache migrate --source .sunwell/plans
    """
    import json as json_module

    from sunwell.incremental import ExecutionCache, ExecutionStatus

    source_path = Path(source)
    cache_path = get_cache_path()

    if not source_path.exists():
        console.print(f"[yellow]Source directory not found: {source_path}[/yellow]")
        return

    # Find all JSON plan files (exclude .trace files)
    plan_files = [
        f for f in source_path.glob("*.json") if not f.name.endswith(".trace.json")
    ]

    if not plan_files:
        console.print(f"[yellow]No plan files found in {source_path}[/yellow]")
        return

    console.print(f"\n[bold]Migrating {len(plan_files)} plan files[/bold]")
    console.print(f"  Source: {source_path}")
    console.print(f"  Target: {cache_path}")

    if dry_run:
        console.print("\n[yellow]DRY RUN - no changes will be made[/yellow]")

    # Create cache if not dry run
    if not dry_run:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = ExecutionCache(cache_path)

    total_artifacts = 0
    migrated_artifacts = 0
    errors = []

    for plan_file in plan_files:
        try:
            with open(plan_file) as f:
                data = json_module.load(f)

            # Support both old format (graph.artifacts) and new format (tasks)
            artifacts = []
            completed = data.get("completed", {})
            failed = data.get("failed", {})

            # Old format
            if "graph" in data and "artifacts" in data.get("graph", {}):
                for artifact in data["graph"]["artifacts"]:
                    artifact_id = artifact.get("id", "")
                    if artifact_id:
                        is_completed = artifact_id in completed
                        is_failed = artifact_id in failed
                        artifacts.append(
                            {
                                "id": artifact_id,
                                "description": artifact.get("description", ""),
                                "status": (
                                    "completed"
                                    if is_completed
                                    else ("failed" if is_failed else "pending")
                                ),
                                "hash": completed.get(artifact_id, {}).get(
                                    "content_hash", ""
                                ),
                            }
                        )

            # New format
            elif "tasks" in data:
                for task in data.get("tasks", []):
                    task_id = task.get("id", "")
                    if task_id:
                        artifacts.append(
                            {
                                "id": task_id,
                                "description": task.get("description", ""),
                                "status": task.get("status", "pending"),
                                "hash": task.get("content_hash", ""),
                            }
                        )

            total_artifacts += len(artifacts)

            if dry_run:
                console.print(f"  {plan_file.name}: {len(artifacts)} artifacts")
            else:
                # Import into cache
                for artifact in artifacts:
                    status_str = artifact["status"]
                    if status_str in ("completed", "complete"):
                        status = ExecutionStatus.COMPLETED
                    elif status_str == "failed":
                        status = ExecutionStatus.FAILED
                    elif status_str == "running":
                        status = ExecutionStatus.RUNNING
                    else:
                        status = ExecutionStatus.PENDING

                    # Use content hash or generate a placeholder
                    input_hash = artifact.get("hash") or f"migrated_{artifact['id'][:8]}"

                    cache.set(
                        artifact_id=artifact["id"],
                        input_hash=input_hash,
                        status=status,
                        result={"migrated_from": str(plan_file.name)},
                    )
                    migrated_artifacts += 1

                console.print(
                    f"  [green]✓[/green] {plan_file.name}: {len(artifacts)} artifacts"
                )

        except (json_module.JSONDecodeError, KeyError) as e:
            errors.append((plan_file.name, str(e)))
            console.print(f"  [red]✗[/red] {plan_file.name}: {e}")

    # Summary
    console.print("\n[bold]Migration Summary[/bold]")
    console.print("─" * 40)
    console.print(f"  Plan files processed: {len(plan_files)}")
    console.print(f"  Total artifacts found: {total_artifacts}")

    if not dry_run:
        console.print(f"  Artifacts migrated: {migrated_artifacts}")
        console.print(f"  Cache location: {cache_path}")

    if errors:
        console.print(f"\n[red]Errors: {len(errors)}[/red]")
        for name, error in errors:
            console.print(f"  {name}: {error}")

    if dry_run:
        console.print("\n[yellow]Run without --dry-run to perform migration[/yellow]")
    else:
        console.print("\n[green]✓ Migration complete[/green]")


@dag.command()
@click.argument("artifact_id")
@click.option(
    "--direction",
    "-d",
    type=click.Choice(["up", "down", "both"]),
    default="both",
    help="Query direction",
)
@click.option("--depth", default=100, help="Maximum traversal depth")
def provenance(artifact_id: str, direction: str, depth: int) -> None:
    """Query artifact provenance (lineage).

    \b
    Examples:
        sunwell dag provenance UserModel
        sunwell dag provenance UserModel --direction up
        sunwell dag provenance UserModel --direction down --depth 3
    """
    from sunwell.incremental import ExecutionCache

    cache_path = get_cache_path()

    if not cache_path.exists():
        console.print("[yellow]No cache found.[/yellow]")
        return

    cache = ExecutionCache(cache_path)

    console.print(f"\n[bold]Provenance: {artifact_id}[/bold]")
    console.print("─" * 40)

    if direction in ("up", "both"):
        upstream = cache.get_upstream(artifact_id, max_depth=depth)
        console.print("\n[cyan]Upstream (dependencies):[/cyan]")
        if upstream:
            for dep in upstream:
                console.print(f"  ← {dep}")
        else:
            console.print("  [dim]None[/dim]")

    if direction in ("down", "both"):
        downstream = cache.get_downstream(artifact_id, max_depth=depth)
        console.print("\n[yellow]Downstream (dependents):[/yellow]")
        if downstream:
            for dep in downstream:
                console.print(f"  → {dep}")
        else:
            console.print("  [dim]None[/dim]")

    console.print()
