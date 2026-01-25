"""CLI commands for ToC navigation (RFC-124)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree

console = Console()


@click.group()
def nav() -> None:
    """Table of Contents navigation commands.

    Build and navigate a hierarchical ToC for reasoning-based
    code discovery. Excels at structural queries like:

    \b
    - "Where is authentication implemented?"
    - "How does the routing work?"
    - "Find the model validation code"
    """


@nav.command()
@click.option("--force", is_flag=True, help="Force rebuild (ignore cache)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--depth", default=10, help="Maximum scan depth")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
def build(force: bool, json_output: bool, depth: int, verbose: bool) -> None:
    """Build or rebuild the ToC index."""
    asyncio.run(_build_toc(force, json_output, depth, verbose))


async def _build_toc(
    force: bool, json_output: bool, max_depth: int, verbose: bool
) -> None:
    """Build ToC with progress reporting."""
    import time

    from sunwell.knowledge.navigation import GeneratorConfig, ProjectToc, TocGenerator

    cwd = Path.cwd()
    cache_dir = cwd / ".sunwell" / "navigation"

    # Check for existing ToC
    if not force:
        existing = ProjectToc.load(cache_dir.parent)
        if existing and not existing.is_stale():
            if json_output:
                gen_at = existing.generated_at.isoformat() if existing.generated_at else None
                print(json.dumps({
                    "status": "cached",
                    "node_count": existing.node_count,
                    "file_count": existing.file_count,
                    "generated_at": gen_at,
                }))
            else:
                console.print(f"[green]✓[/green] ToC up to date ({existing.node_count} nodes)")
                console.print("[dim]Use --force to rebuild[/dim]")
            return

    start = time.perf_counter()

    config = GeneratorConfig(max_depth=max_depth)
    generator = TocGenerator(root=cwd, config=config)

    if json_output:
        toc = generator.generate()
        elapsed = time.perf_counter() - start
        toc.save(cache_dir.parent)
        print(json.dumps({
            "status": "built",
            "node_count": toc.node_count,
            "file_count": toc.file_count,
            "build_time_ms": int(elapsed * 1000),
            "estimated_tokens": toc.estimate_tokens(max_depth=2),
        }))
    elif verbose:
        # Verbose mode with detailed progress
        console.print("[bold]Building ToC...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Scan phase
            scan_task = progress.add_task("[cyan]Scanning directories...", total=None)

            # Count files first for progress bar
            py_files = list(cwd.rglob("*.py"))
            total_files = len(py_files)
            progress.update(scan_task, total=total_files, completed=0)
            progress.update(scan_task, description=f"[cyan]Found {total_files} Python files")

            # Generate
            progress.update(scan_task, description="[cyan]Parsing AST...")
            toc = generator.generate()
            progress.update(scan_task, completed=total_files)

            # Save
            progress.update(scan_task, description="[cyan]Saving ToC...")
            toc.save(cache_dir.parent)
            progress.update(scan_task, description="[green]Complete")

        elapsed = time.perf_counter() - start

        # Detailed stats
        console.print(f"\n[green]✓[/green] Built ToC in {elapsed:.2f}s\n")

        # Node type breakdown
        type_counts: dict[str, int] = {}
        for node in toc.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        table = Table(title="Node Breakdown", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right")

        for nt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            table.add_row(nt, f"{count:,}")
        table.add_row("[bold]Total[/bold]", f"[bold]{toc.node_count:,}[/bold]")

        console.print(table)
        console.print()

        # Concept breakdown
        if toc.concept_index:
            console.print("[bold]Concepts Detected[/bold]")
            for concept, nodes in sorted(
                toc.concept_index.items(), key=lambda x: -len(x[1])
            ):
                console.print(f"  {concept}: {len(nodes):,} nodes")
            console.print()

        # Token estimates
        console.print("[bold]Token Estimates[/bold]")
        console.print(f"  Depth 1: ~{toc.estimate_tokens(max_depth=1):,} tokens")
        console.print(f"  Depth 2: ~{toc.estimate_tokens(max_depth=2):,} tokens")
        console.print(f"  Depth 3: ~{toc.estimate_tokens(max_depth=3):,} tokens")
    else:
        # Simple progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building ToC...", total=None)
            toc = generator.generate()
            progress.update(task, description="Saving...")
            toc.save(cache_dir.parent)

        elapsed = time.perf_counter() - start
        console.print(f"[green]✓[/green] Built ToC in {elapsed:.2f}s")
        console.print(f"  Nodes: {toc.node_count}")
        console.print(f"  Files: {toc.file_count}")
        console.print(f"  Estimated tokens (depth=2): {toc.estimate_tokens(max_depth=2)}")


@nav.command()
@click.argument("query")
@click.option("--max-results", "-n", default=3, help="Maximum navigation steps")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--rebuild", is_flag=True, help="Rebuild ToC if stale before searching")
@click.option("--fallback", is_flag=True, help="Use keyword fallback if LLM unavailable")
def find(
    query: str,
    max_results: int,
    json_output: bool,
    rebuild: bool,
    fallback: bool,
) -> None:
    """Navigate to find code matching a query.

    Uses LLM reasoning to navigate the ToC structure.
    Best for structural queries like "where is X implemented?"

    Examples:

    \b
        sunwell nav find "where is authentication implemented"
        sunwell nav find "how does model routing work" -n 5
        sunwell nav find "find the config parser" --fallback
    """
    asyncio.run(_find_code(query, max_results, json_output, rebuild, fallback))


async def _find_code(
    query: str,
    max_results: int,
    json_output: bool,
    rebuild: bool,
    fallback: bool,
) -> None:
    """Navigate to find relevant code."""
    from sunwell.knowledge.navigation import (
        GeneratorConfig,
        NavigationResult,
        ProjectToc,
        TocGenerator,
        TocNavigator,
    )

    cwd = Path.cwd()

    # Load ToC
    toc = ProjectToc.load(cwd / ".sunwell")

    # Auto-rebuild if stale or missing
    if not toc or (rebuild and toc.is_stale()):
        if not json_output:
            if not toc:
                console.print("[yellow]No ToC found. Building...[/yellow]")
            else:
                console.print("[yellow]ToC is stale. Rebuilding...[/yellow]")

        generator = TocGenerator(root=cwd, config=GeneratorConfig())

        if json_output:
            toc = generator.generate()
            toc.save(cwd / ".sunwell")
        else:
            with console.status("[bold]Building ToC...[/bold]"):
                toc = generator.generate()
                toc.save(cwd / ".sunwell")
            console.print(f"[green]✓[/green] Built ToC ({toc.node_count} nodes)\n")

    if not toc:
        if json_output:
            print(json.dumps({"error": "Failed to build ToC"}))
        else:
            console.print("[red]✗[/red] Failed to build ToC")
        return

    # Warn if stale but not rebuilding
    if toc.is_stale() and not rebuild and not json_output:
        console.print("[yellow]⚠ ToC is stale. Use --rebuild to refresh.[/yellow]\n")

    # Create model (skip if fallback mode)
    model = None

    if fallback:
        if not json_output:
            console.print("[dim]Using keyword fallback (no LLM)[/dim]\n")
    else:
        try:
            from sunwell.models.providers import create_model
            model = create_model()
        except Exception as e:
            if json_output:
                print(json.dumps({
                    "error": f"Failed to create model: {e}",
                    "hint": "Use --fallback for keyword-based search",
                }))
            else:
                console.print(f"[red]✗[/red] Failed to create model: {e}")
                console.print("[dim]Tip: Use --fallback for keyword-based search[/dim]")
            return

    # For fallback mode, use mock model (navigator uses _fallback_navigate internally)
    if not model:
        from sunwell.models.mock import MockModel
        model = MockModel()

    navigator = TocNavigator(toc=toc, model=model, workspace_root=cwd)

    # In fallback mode, use keyword matching directly
    if fallback:
        result = navigator._fallback_navigate(query)
        content = await navigator._read_path(result.path)
        result_with_content = NavigationResult(
            path=result.path,
            reasoning=result.reasoning,
            confidence=result.confidence,
            content=content,
            follow_up=result.follow_up,
        )

        if json_output:
            print(json.dumps({
                "query": query,
                "mode": "fallback",
                "results": [{
                    "path": result_with_content.path,
                    "reasoning": result_with_content.reasoning,
                    "confidence": result_with_content.confidence,
                    "content_length": len(content) if content else 0,
                    "follow_up": list(result_with_content.follow_up),
                }],
            }))
        else:
            console.print(f"[bold]Results for:[/bold] {query}\n")
            console.print(f"[cyan]1. {result_with_content.path}[/cyan]")
            console.print(f"   [dim]{result_with_content.reasoning}[/dim]")
            console.print(f"   Confidence: [yellow]{result_with_content.confidence:.0%}[/yellow]")
            if result_with_content.content:
                lines = [
                    ln.strip() for ln in result_with_content.content.split("\n")
                    if ln.strip() and not ln.strip().startswith("#")
                ][:3]
                if lines:
                    preview = " | ".join(lines)[:150]
                    console.print(f"   [dim]Preview: {preview}...[/dim]")
            if result_with_content.follow_up:
                console.print(
                    f"   [dim]Related: {', '.join(result_with_content.follow_up[:3])}[/dim]"
                )
            console.print()
        return

    # LLM mode
    if json_output:
        results_list = await navigator.iterative_search(query, max_iterations=max_results)
        results = [
            {
                "path": r.path,
                "reasoning": r.reasoning,
                "confidence": r.confidence,
                "content_length": len(r.content) if r.content else 0,
                "follow_up": list(r.follow_up),
            }
            for r in results_list
        ]

        print(json.dumps({
            "query": query,
            "mode": "llm",
            "results": results,
        }))
    else:
        with console.status("[bold]Navigating...[/bold]"):
            results = await navigator.iterative_search(query, max_iterations=max_results)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"\n[bold]Results for:[/bold] {query}\n")

        for i, result in enumerate(results, 1):
            # Color code confidence
            if result.confidence >= 0.8:
                conf_color = "green"
            elif result.confidence >= 0.5:
                conf_color = "yellow"
            else:
                conf_color = "red"

            console.print(f"[cyan]{i}. {result.path}[/cyan]")
            console.print(f"   [dim]{result.reasoning}[/dim]")
            console.print(f"   Confidence: [{conf_color}]{result.confidence:.0%}[/{conf_color}]")

            if result.content:
                # Show first meaningful lines
                lines = [
                    ln.strip() for ln in result.content.split("\n")
                    if ln.strip() and not ln.strip().startswith("#")
                ][:3]
                if lines:
                    preview = " | ".join(lines)[:150]
                    console.print(f"   [dim]Preview: {preview}...[/dim]")

            if result.follow_up:
                console.print(f"   [dim]Related: {', '.join(result.follow_up[:3])}[/dim]")
            console.print()


@nav.command()
@click.option("--depth", "-d", default=2, help="Tree depth to show")
@click.option("--node", "-n", help="Show subtree from specific node ID")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def show(depth: int, node: str | None, json_output: bool) -> None:
    """Show the ToC structure."""
    from sunwell.knowledge.navigation import ProjectToc

    cwd = Path.cwd()

    toc = ProjectToc.load(cwd / ".sunwell")
    if not toc:
        if json_output:
            print(json.dumps({"error": "No ToC found. Run `sunwell nav build` first."}))
        else:
            console.print("[red]✗[/red] No ToC found. Run `sunwell nav build` first.")
        return

    if json_output:
        if node:
            print(toc.get_subtree(node, depth=depth))
        else:
            print(toc.to_context_json(max_depth=depth))
    else:
        start_id = node or toc.root_id
        start_node = toc.get_node(start_id)

        if not start_node:
            console.print(f"[red]✗[/red] Node not found: {start_id}")
            return

        tree = Tree(f"[bold]{start_node.title}[/bold] ({start_node.node_type})")
        _build_tree(tree, toc, start_id, depth, current_depth=0)
        console.print(tree)


def _build_tree(
    tree: Tree,
    toc,
    node_id: str,
    max_depth: int,
    current_depth: int,
) -> None:
    """Recursively build Rich tree from ToC."""
    if current_depth >= max_depth:
        return

    node = toc.get_node(node_id)
    if not node:
        return

    for child_id in node.children:
        child = toc.get_node(child_id)
        if not child:
            continue

        # Format based on type
        if child.node_type == "directory":
            label = f"[blue]{child.title}/[/blue]"
        elif child.node_type == "module":
            label = f"[cyan]{child.title}[/cyan]"
        elif child.node_type == "class":
            label = f"[yellow]{child.title}[/yellow]"
        elif child.node_type == "function":
            label = f"[green]{child.title}()[/green]"
        else:
            label = child.title

        # Add summary if short
        if len(child.summary) < 40:
            label += f" [dim]- {child.summary}[/dim]"

        branch = tree.add(label)
        _build_tree(branch, toc, child_id, max_depth, current_depth + 1)


@nav.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def stats(json_output: bool) -> None:
    """Show ToC statistics."""
    from sunwell.knowledge.navigation import ProjectToc

    cwd = Path.cwd()

    toc = ProjectToc.load(cwd / ".sunwell")
    if not toc:
        if json_output:
            print(json.dumps({"error": "No ToC found. Run `sunwell nav build` first."}))
        else:
            console.print("[red]✗[/red] No ToC found. Run `sunwell nav build` first.")
        return

    # Count node types
    type_counts: dict[str, int] = {}
    for node_val in toc.nodes.values():
        nt = node_val.node_type
        type_counts[nt] = type_counts.get(nt, 0) + 1

    # Token estimates
    tokens_d1 = toc.estimate_tokens(max_depth=1)
    tokens_d2 = toc.estimate_tokens(max_depth=2)
    tokens_d3 = toc.estimate_tokens(max_depth=3)

    if json_output:
        print(json.dumps({
            "root_id": toc.root_id,
            "node_count": toc.node_count,
            "file_count": toc.file_count,
            "generated_at": toc.generated_at.isoformat() if toc.generated_at else None,
            "is_stale": toc.is_stale(),
            "type_counts": type_counts,
            "concept_counts": {k: len(v) for k, v in toc.concept_index.items()},
            "token_estimates": {
                "depth_1": tokens_d1,
                "depth_2": tokens_d2,
                "depth_3": tokens_d3,
            },
        }))
    else:
        console.print("[bold]ToC Statistics[/bold]\n")

        # Basic info
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="dim")
        table.add_column("Value")

        table.add_row("Root", toc.root_id)
        table.add_row("Total nodes", str(toc.node_count))
        table.add_row("Files indexed", str(toc.file_count))
        table.add_row(
            "Generated",
            toc.generated_at.strftime("%Y-%m-%d %H:%M") if toc.generated_at else "Unknown",
        )
        status = "[yellow]Stale[/yellow]" if toc.is_stale() else "[green]Fresh[/green]"
        table.add_row("Status", status)

        console.print(table)
        console.print()

        # Node types
        console.print("[bold]Node Types[/bold]")
        for nt, count in sorted(type_counts.items()):
            console.print(f"  {nt}: {count}")
        console.print()

        # Concepts
        console.print("[bold]Concepts[/bold]")
        for concept, nodes in sorted(toc.concept_index.items()):
            console.print(f"  {concept}: {len(nodes)} nodes")
        console.print()

        # Token estimates
        console.print("[bold]Token Estimates[/bold]")
        console.print(f"  Depth 1: ~{tokens_d1:,} tokens")
        console.print(f"  Depth 2: ~{tokens_d2:,} tokens")
        console.print(f"  Depth 3: ~{tokens_d3:,} tokens")


@nav.command()
def clear() -> None:
    """Clear the ToC cache."""
    import shutil

    cache_dir = Path.cwd() / ".sunwell" / "navigation"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        console.print("[green]✓[/green] ToC cache cleared")
    else:
        console.print("[yellow]No ToC cache found[/yellow]")
