"""Auto-wiring logic for RFC-084: Automatic topology extraction and cold demotion."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:

    from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager
    from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkSummary
    from sunwell.memory.simulacrum.hierarchical.config import ChunkConfig
    from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore


def turns_to_text(chunk: Chunk | ChunkSummary) -> str:
    """Convert chunk turns to text for topology extraction."""
    if chunk.turns:
        return "\n".join(f"{t.turn_type.value}: {t.content[:500]}" for t in chunk.turns)
    return chunk.summary or ""


async def extract_topology_batch(
    chunk_manager: ChunkManager,
    topology_extractor: Any,
    unified_store: UnifiedMemoryStore | None,
    topology_extracted_chunks: set[str],
) -> None:
    """Extract relationships from recent chunks (RFC-084 auto-topology)."""
    if not unified_store:
        return

    recent_chunks = chunk_manager._get_recent_chunks(limit=5)
    if len(recent_chunks) < 2:
        return

    for chunk in recent_chunks:
        if chunk.id in topology_extracted_chunks:
            continue

        # Get text for this chunk
        source_text = chunk.summary or turns_to_text(chunk)

        # Get candidate chunks (excluding self)
        candidates = [c for c in recent_chunks if c.id != chunk.id]
        candidate_ids = [c.id for c in candidates]
        candidate_texts = [c.summary or turns_to_text(c) for c in candidates]

        if not candidate_ids:
            continue

        # Extract relationships using heuristics
        edges = topology_extractor.extract_heuristic_relationships(
            source_id=chunk.id,
            source_text=source_text,
            candidate_ids=candidate_ids,
            candidate_texts=candidate_texts,
        )

        # Add edges to the concept graph
        if edges:
            for edge in edges:
                unified_store._concept_graph.add_edge(edge)

        topology_extracted_chunks.add(chunk.id)

    # Persist the graph
    unified_store.save()


def maybe_demote_warm_to_cold(
    chunk_manager: ChunkManager,
    config: ChunkConfig,
) -> None:
    """Demote old warm chunks to cold tier (RFC-084 auto-cold-demotion)."""
    import time
    from datetime import datetime

    warm_chunks = chunk_manager._get_warm_chunks()
    if not warm_chunks:
        return

    now = time.time()

    # By age: older than config threshold
    for chunk in warm_chunks:
        if not chunk.timestamp_end:
            continue
        try:
            # Parse ISO timestamp
            chunk_time = datetime.fromisoformat(chunk.timestamp_end).timestamp()
            age_days = (now - chunk_time) / 86400
            if age_days > config.warm_retention_days:
                chunk_manager.demote_to_cold(chunk.id)
        except (ValueError, OSError):
            continue

    # By count: keep only max_warm_chunks
    warm_chunks = chunk_manager._get_warm_chunks()  # Refresh after age-based demotion
    warm_chunks.sort(key=lambda c: c.turn_range[0])  # Sort by turn range (oldest first)

    while len(warm_chunks) > config.max_warm_chunks:
        oldest = warm_chunks.pop(0)
        chunk_manager.demote_to_cold(oldest.id)
