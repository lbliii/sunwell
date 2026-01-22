#!/usr/bin/env python3
"""Diagnose why memory retrieval isn't finding old facts.

Creates 100 turns with embedded facts and traces exactly what happens.
"""

import asyncio
import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

# Facts to embed at specific turns
FACTS = {
    10: ("name", "My name is Alex Chen"),
    30: ("database", "We're using PostgreSQL 15 for the database"),
    50: ("rate_limit", "The API rate limit is 1000 requests per minute"),
    70: ("deployment", "We're deploying to Kubernetes on GKE"),
    90: ("auth", "Auth tokens use JWT with 24 hour expiry"),
}


async def diagnose():
    """Run diagnostic on memory retrieval."""
    from sunwell.embedding import create_embedder
    from sunwell.simulacrum.core.store import SimulacrumStore
    from sunwell.simulacrum.core.turn import Turn, TurnType

    console.print("\n[bold cyan]Memory Retrieval Diagnostic[/bold cyan]")
    console.print("=" * 60)

    test_dir = Path(tempfile.mkdtemp(prefix="sunwell_diag_"))
    store = SimulacrumStore(base_path=test_dir)

    # Enable embeddings
    embedder = create_embedder()
    store.set_embedder(embedder)
    console.print(f"[green]✓[/green] Store created with embeddings\n")

    # Phase 1: Add 100 turns
    console.print("[bold]Phase 1: Adding 100 turns with embedded facts[/bold]")

    for i in range(100):
        if i in FACTS:
            key, fact = FACTS[i]
            content = f"{fact}. Now let's continue discussing the architecture."
            console.print(f"  Turn {i}: [green]Embedded '{key}'[/green]")
        else:
            content = f"Turn {i}: Discussing general architecture topics and system design considerations."

        user_turn = Turn(content=content, turn_type=TurnType.USER)
        await store.add_turn_async(user_turn)

        assistant_turn = Turn(
            content=f"Response to turn {i}: Here are my thoughts on the topic...",
            turn_type=TurnType.ASSISTANT,
        )
        await store.add_turn_async(assistant_turn)

    console.print(f"\n[green]✓[/green] Added 100 user + 100 assistant = 200 turns total")

    # Phase 2: Inspect chunks
    console.print("\n[bold]Phase 2: Chunk Analysis[/bold]")

    chunk_manager = store._chunk_manager
    if not chunk_manager:
        console.print("[red]No ChunkManager![/red]")
        return

    chunks = list(chunk_manager._chunks.values())
    console.print(f"Total chunks: {len(chunks)}")

    # Count by type
    by_type = {}
    for c in chunks:
        by_type[c.chunk_type.value] = by_type.get(c.chunk_type.value, 0) + 1

    for chunk_type, count in sorted(by_type.items()):
        console.print(f"  {chunk_type}: {count}")

    # Show hot chunks
    hot_chunks = [c for c in chunks if c.turns is not None]
    console.print(f"\nHot chunks (with full turns): {len(hot_chunks)}")
    for c in hot_chunks[-3:]:  # Show last 3
        console.print(f"  {c.id[:12]}... turns {c.turn_range[0]}-{c.turn_range[1]}")

    # Phase 3: Test context retrieval (SYNC - no semantic search)
    console.print("\n[bold]Phase 3a: Sync Context Retrieval (no semantic search)[/bold]")

    queries = [
        ("What is my name?", "Alex Chen", 10),
        ("What database?", "PostgreSQL", 30),
        ("API rate limit?", "1000", 50),
        ("Kubernetes deployment?", "Kubernetes", 70),
        ("Auth token expiry?", "24", 90),
    ]

    table = Table(title="SYNC Context Retrieval (hot + macro only)")
    table.add_column("Query", style="cyan")
    table.add_column("Expected", style="green")
    table.add_column("Fact Turn", style="yellow")
    table.add_column("Found?", style="magenta")

    for query, expected, fact_turn in queries:
        context = store.get_context_for_prompt(query, max_tokens=4000)
        found = expected.lower() in context.lower()
        status = "[green]✓[/green]" if found else "[red]✗[/red]"
        table.add_row(query, expected, str(fact_turn), status)

    console.print(table)

    # Phase 3b: Test ASYNC context retrieval with semantic search
    console.print("\n[bold]Phase 3b: Async Context Retrieval (with semantic search)[/bold]")

    table2 = Table(title="ASYNC Context Retrieval (semantic search enabled)")
    table2.add_column("Query", style="cyan")
    table2.add_column("Expected", style="green")
    table2.add_column("Fact Turn", style="yellow")
    table2.add_column("Found?", style="magenta")

    for query, expected, fact_turn in queries:
        context = await store.get_context_for_prompt_async(query, max_tokens=4000)
        found = expected.lower() in context.lower()
        status = "[green]✓[/green]" if found else "[red]✗[/red]"
        table2.add_row(query, expected, str(fact_turn), status)

    console.print(table2)

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Diagnosis Complete[/bold]")
    console.print("""
Comparing sync vs async retrieval shows the difference:
- SYNC: Only hot chunks + macro summaries (no semantic search)
- ASYNC: Uses embedding-based semantic search to find relevant warm chunks
""")


if __name__ == "__main__":
    asyncio.run(diagnose())
