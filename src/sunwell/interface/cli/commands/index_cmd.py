"""CLI commands for codebase indexing (RFC-108)."""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.group()
def index() -> None:
    """Codebase indexing commands.

    Build and query a semantic index of your codebase for
    intelligent code retrieval.
    """
    pass


@index.command()
@click.option(
    "--json", "json_output", is_flag=True, help="JSON output for Studio integration"
)
@click.option("--progress", is_flag=True, help="Stream progress updates")
@click.option("--force", is_flag=True, help="Force full rebuild (ignore cache)")
def build(json_output: bool, progress: bool, force: bool) -> None:
    """Build or update the codebase index."""
    asyncio.run(_build_index(json_output, progress, force))


async def _build_index(json_output: bool, progress: bool, force: bool) -> None:
    """Build index with progress reporting."""
    from sunwell.knowledge import IndexingService, IndexState

    cwd = Path.cwd()

    # Clear cache if forced
    if force:
        cache_dir = cwd / ".sunwell" / "index"
        if cache_dir.exists():
            import shutil

            shutil.rmtree(cache_dir)

    service = IndexingService(workspace_root=cwd)

    if json_output:
        # Stream JSON for Tauri
        def on_status(status):
            print(json.dumps(status.to_json()), flush=True)

        service.on_status_change = on_status
        await service.start()
        await service.wait_ready(timeout=300)  # 5 min timeout for large repos

    elif progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress_bar:
            task = progress_bar.add_task("Indexing...", total=100)

            def on_status(status):
                progress_bar.update(
                    task,
                    completed=status.progress,
                    description=f"Indexing: {status.current_file or '...'}",
                )

            service.on_status_change = on_status
            await service.start()
            await service.wait_ready(timeout=300)

            progress_bar.update(task, completed=100, description="Done!")

        console.print(
            f"[green]✓[/green] Indexed {service.status.chunk_count} chunks "
            f"from {service.status.file_count} files"
        )
    else:
        # Simple output
        console.print("[dim]Building index...[/dim]")
        await service.start()
        await service.wait_ready(timeout=300)

        if service.status.state == IndexState.READY:
            project_type = service.project_type.value.title()
            console.print(
                f"[green]✓[/green] Indexed {service.status.chunk_count} chunks "
                f"from {service.status.file_count} files"
            )
            console.print(f"[dim]Project type: {project_type}[/dim]")
        elif service.status.state == IndexState.DEGRADED:
            console.print(
                f"[yellow]⚠️[/yellow] Running in fallback mode: "
                f"{service.status.fallback_reason}"
            )
        else:
            console.print(f"[red]✗[/red] Indexing failed: {service.status.error}")


@index.command()
@click.argument("query")
@click.option("--top-k", default=10, help="Number of results")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def query(query: str, top_k: int, json_output: bool) -> None:
    """Query the codebase index."""
    asyncio.run(_query_index(query, top_k, json_output))


async def _query_index(query_text: str, top_k: int, json_output: bool) -> None:
    """Query the index."""
    import time

    from sunwell.knowledge import IndexingService

    cwd = Path.cwd()
    service = IndexingService(workspace_root=cwd)

    await service.start()
    if not await service.wait_ready(timeout=5):
        if json_output:
            print(
                json.dumps({"error": "Index not ready", "chunks": [], "fallback_used": True})
            )
        else:
            console.print("[yellow]Index not ready. Building...[/yellow]")
        return

    start = time.perf_counter()
    chunks = await service.query(query_text, top_k=top_k)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    if json_output:
        print(
            json.dumps({
                "chunks": [
                    {
                        "id": c.id,
                        "file_path": str(c.file_path),
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "content": c.content,
                        "chunk_type": c.chunk_type,
                        "name": c.name,
                        "score": 0.0,  # TODO: Add score to query result
                    }
                    for c in chunks
                ],
                "fallback_used": False,
                "query_time_ms": elapsed_ms,
                "total_chunks_searched": service.status.chunk_count or 0,
            })
        )
    else:
        if not chunks:
            console.print("[dim]No results found[/dim]")
            return

        table = Table(title=f"Results for: {query_text}")
        table.add_column("File", style="cyan")
        table.add_column("Lines", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Name")

        for chunk in chunks:
            try:
                rel_path = chunk.file_path.relative_to(cwd)
            except ValueError:
                rel_path = chunk.file_path

            table.add_row(
                str(rel_path),
                f"{chunk.start_line}-{chunk.end_line}",
                chunk.chunk_type,
                chunk.name or "",
            )

        console.print(table)
        console.print(f"[dim]Query time: {elapsed_ms}ms[/dim]")


@index.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def status(json_output: bool) -> None:
    """Show index status."""
    asyncio.run(_show_status(json_output))


async def _show_status(json_output: bool) -> None:
    """Show current index status."""
    cwd = Path.cwd()
    cache_dir = cwd / ".sunwell" / "index"
    meta_file = cache_dir / "meta.json"

    if not meta_file.exists():
        if json_output:
            print(json.dumps({"state": "no_index", "error": "No index found"}))
        else:
            console.print("[yellow]No index found. Run `sunwell index build`[/yellow]")
        return

    meta = json.loads(meta_file.read_text())

    if json_output:
        print(
            json.dumps({
                "state": "ready",
                "chunk_count": meta.get("chunk_count", 0),
                "file_count": meta.get("file_count", 0),
                "last_updated": meta.get("updated_at"),
                "content_hash": meta.get("content_hash"),
                "project_type": meta.get("project_type", "unknown"),
            })
        )
    else:
        console.print("[bold]Index Status[/bold]")
        console.print("  State: [green]Ready[/green]")
        console.print(f"  Chunks: {meta.get('chunk_count', 0)}")
        console.print(f"  Files: {meta.get('file_count', 0)}")
        console.print(f"  Project type: {meta.get('project_type', 'unknown').title()}")
        console.print(f"  Updated: {meta.get('updated_at', 'unknown')}")


@index.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def metrics(json_output: bool) -> None:
    """Show index metrics for debugging."""
    asyncio.run(_show_metrics(json_output))


async def _show_metrics(json_output: bool) -> None:
    """Show index metrics."""
    from sunwell.knowledge import IndexingService

    cwd = Path.cwd()
    service = IndexingService(workspace_root=cwd)

    await service.start()
    if not await service.wait_ready(timeout=5):
        if json_output:
            print(json.dumps({"error": "Index not ready"}))
        else:
            console.print("[yellow]Index not ready[/yellow]")
        return

    metrics_data = service.metrics.to_json()

    if json_output:
        print(json.dumps(metrics_data))
    else:
        console.print("[bold]Index Metrics[/bold]")
        console.print(f"  Build time: {metrics_data['build_time_ms']}ms")
        console.print(f"  Embedding time: {metrics_data.get('embedding_time_ms', 0)}ms")
        console.print(f"  Chunks: {metrics_data['chunk_count']}")
        console.print(f"  Files: {metrics_data['file_count']}")
        console.print(f"  Cache hit rate: {metrics_data['cache_hit_rate']:.0%}")
        console.print(f"  Avg query latency: {metrics_data['avg_query_latency_ms']:.0f}ms")
        console.print(
            f"  Health: {'[green]Healthy[/green]' if metrics_data['is_healthy'] else '[red]Unhealthy[/red]'}"
        )


@index.command()
def clear() -> None:
    """Clear the index cache."""
    import shutil

    cache_dir = Path.cwd() / ".sunwell" / "index"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        console.print("[green]✓[/green] Index cache cleared")
    else:
        console.print("[yellow]No index cache found[/yellow]")
