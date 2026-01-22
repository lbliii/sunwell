#!/usr/bin/env python3
"""Diagnose: How is simulacrum actually organizing knowledge?

Investigates:
1. DAG structure and learning propagation
2. Focus/weighting system
3. ConceptGraph (knowledge hubs)
4. Tier transitions (hot → warm → cold)
"""

import asyncio
import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console()


async def diagnose():
    """Diagnose memory architecture."""
    from sunwell.embedding import create_embedder
    from sunwell.simulacrum.core.store import SimulacrumStore
    from sunwell.simulacrum.core.turn import Turn, TurnType
    from sunwell.simulacrum.hierarchical.chunks import ChunkType

    console.print("\n[bold cyan]Memory Architecture Diagnostic[/bold cyan]")
    console.print("=" * 60)

    test_dir = Path(tempfile.mkdtemp(prefix="sunwell_arch_"))
    store = SimulacrumStore(base_path=test_dir)
    embedder = create_embedder()
    store.set_embedder(embedder)

    # ===== Phase 1: Add enough turns to trigger all tier transitions =====
    console.print("\n[bold]Phase 1: Adding turns to trigger tier transitions[/bold]")
    console.print("  Config:")
    cm = store._chunk_manager
    console.print(f"    micro_chunk_size: {cm.config.micro_chunk_size} turns")
    console.print(f"    mini_chunk_interval: {cm.config.mini_chunk_interval} turns")
    console.print(f"    macro_chunk_interval: {cm.config.macro_chunk_interval} turns")
    console.print(f"    hot_chunks limit: {cm.config.hot_chunks}")

    # Add 150 turns (enough for MICRO, MINI, and MACRO chunks)
    topics = ["auth", "database", "api", "frontend", "testing"]
    for i in range(150):
        topic = topics[i % len(topics)]
        content = f"Turn {i}: Discussing {topic}. Important fact: {topic} is critical."

        await store.add_turn_async(Turn(content=content, turn_type=TurnType.USER))
        await store.add_turn_async(Turn(content=f"Response about {topic}.", turn_type=TurnType.ASSISTANT))

        if (i + 1) % 50 == 0:
            console.print(f"  Added {i + 1}/150 turns...")

    # ===== Phase 2: Analyze chunk tiers =====
    console.print("\n[bold]Phase 2: Chunk Tier Analysis[/bold]")

    table = Table(title="Chunks by Tier and Type")
    table.add_column("Tier", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Count", style="yellow")
    table.add_column("Turn Ranges", style="white")

    chunks = list(cm._chunks.values())

    # Count by type
    hot_micro = [c for c in chunks if c.chunk_type == ChunkType.MICRO and c.turns is not None]
    warm_micro = [c for c in chunks if c.chunk_type == ChunkType.MICRO and c.turns is None and c.content_ctf]
    cold_micro = [c for c in chunks if c.chunk_type == ChunkType.MICRO and c.turns is None and c.content_ref]
    mini = [c for c in chunks if c.chunk_type == ChunkType.MINI]
    macro = [c for c in chunks if c.chunk_type == ChunkType.MACRO]

    def range_str(chunk_list):
        if not chunk_list:
            return "-"
        ranges = [f"{c.turn_range[0]}-{c.turn_range[1]}" for c in sorted(chunk_list, key=lambda c: c.turn_range[0])]
        return ", ".join(ranges[:5]) + ("..." if len(ranges) > 5 else "")

    table.add_row("HOT", "MICRO", str(len(hot_micro)), range_str(hot_micro))
    table.add_row("WARM", "MICRO", str(len(warm_micro)), range_str(warm_micro))
    table.add_row("COLD", "MICRO", str(len(cold_micro)), range_str(cold_micro))
    table.add_row("N/A", "MINI", str(len(mini)), range_str(mini))
    table.add_row("COLD", "MACRO", str(len(macro)), range_str(macro))

    console.print(table)

    # ===== Phase 3: Check ConceptGraph (hubs) =====
    console.print("\n[bold]Phase 3: ConceptGraph (Knowledge Hubs)[/bold]")

    if store._unified_store:
        graph = store._unified_store._concept_graph
        edge_count = sum(len(edges) for edges in graph._edges.values())
        node_count = len(graph._edges)

        console.print(f"  Nodes with edges: {node_count}")
        console.print(f"  Total edges: {edge_count}")

        if edge_count > 0:
            # Show relationship types
            rel_counts = {}
            for edges in graph._edges.values():
                for e in edges:
                    rel_counts[e.relation.value] = rel_counts.get(e.relation.value, 0) + 1

            console.print("  Relationship types:")
            for rel, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
                console.print(f"    {rel}: {count}")
        else:
            console.print("  [yellow]⚠ ConceptGraph is EMPTY[/yellow]")
            console.print("  [dim]Topology extraction not triggered automatically.[/dim]")
            console.print("  [dim]Needs: store.ingest_chunks() or store.ingest_codebase()[/dim]")
    else:
        console.print("  [red]UnifiedStore not initialized![/red]")

    # ===== Phase 4: Check Focus/Weighting =====
    console.print("\n[bold]Phase 4: Focus Weighting System[/bold]")

    # Get the simulacrum's focus (if it exists)
    if hasattr(store, '_focus'):
        focus = store._focus
        console.print(f"  Topics tracked: {len(focus.topics)}")
        for topic, weight in sorted(focus.topics.items(), key=lambda x: -x[1])[:5]:
            console.print(f"    {topic}: {weight:.0%}")
    else:
        console.print("  [yellow]⚠ Focus system not part of SimulacrumStore[/yellow]")
        console.print("  [dim]Focus is in Simulacrum (legacy), not SimulacrumStore[/dim]")

    # ===== Phase 5: Check DAG structure =====
    console.print("\n[bold]Phase 5: ConversationDAG Structure[/bold]")

    dag = store._hot_dag
    console.print(f"  Total turns: {len(dag.turns)}")
    console.print(f"  Learnings: {len(dag.learnings)}")

    if dag.learnings:
        console.print("  Recent learnings:")
        for learning in list(dag.learnings.values())[:3]:
            console.print(f"    - [{learning.category}] {learning.content[:50]}...")

    # ===== Phase 6: What's missing =====
    console.print("\n[bold]Phase 6: Architecture Gaps[/bold]")

    gaps = []

    # Check if cold demotion happened
    if len(cold_micro) == 0:
        gaps.append(("COLD tier never triggered", "demote_to_cold() not called automatically"))

    # Check if topology extraction happened
    if store._unified_store and sum(len(e) for e in store._unified_store._concept_graph._edges.values()) == 0:
        gaps.append(("ConceptGraph empty", "ingest_chunks() never called"))

    # Check if summaries were generated
    chunks_with_summary = [c for c in chunks if c.summary]
    if len(chunks_with_summary) == 0:
        gaps.append(("No summaries generated", "summarizer not configured"))

    # Check if facts were extracted
    chunks_with_facts = [c for c in chunks if c.key_facts]
    if len(chunks_with_facts) == 0:
        gaps.append(("No facts extracted", "fact extraction not triggered"))

    if gaps:
        table = Table(title="Architecture Gaps Detected")
        table.add_column("Issue", style="red")
        table.add_column("Reason", style="yellow")

        for issue, reason in gaps:
            table.add_row(issue, reason)

        console.print(table)
    else:
        console.print("[green]✓ No major gaps detected[/green]")

    # ===== Summary =====
    console.print("\n" + "=" * 60)
    console.print("[bold]Summary: How Knowledge is Currently Organized[/bold]")
    console.print("""
[cyan]Current State:[/cyan]
1. [green]✓[/green] HOT → WARM demotion: Working (auto after 2 hot chunks)
2. [yellow]⚠[/yellow] WARM → COLD demotion: Manual only (never auto-triggered)
3. [yellow]⚠[/yellow] ConceptGraph (hubs): Empty (needs ingest_chunks call)
4. [yellow]⚠[/yellow] Summaries: Not generated (no summarizer configured)
5. [green]✓[/green] Semantic search: Working via embeddings

[cyan]What the "hubs" concept was supposed to be:[/cyan]
The ConceptGraph (RFC-014) models relationships between chunks:
- ELABORATES: One chunk expands on another
- CONTRADICTS: Conflicting information
- DEPENDS_ON: Prerequisite relationships
- RELATES_TO: Topical similarity

This enables queries like "what contradicts X?" or "what does Y depend on?"

[cyan]Why it's not working:[/cyan]
The topology extraction (which populates the graph) requires explicit calls:
- store.ingest_chunks() - for conversation chunks
- store.ingest_codebase() - for code files

These are never called automatically during add_turn().
""")


if __name__ == "__main__":
    asyncio.run(diagnose())
