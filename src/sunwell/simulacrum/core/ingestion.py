"""Document and codebase ingestion for multi-topology memory (RFC-014)."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.simulacrum.topology.unified_store import UnifiedMemoryStore


async def ingest_document(
    unified_store: UnifiedMemoryStore,
    file_path: str,
    content: str,
    *,
    extract_facets: bool = True,
    extract_topology: bool = True,
) -> int:
    """Ingest a document into multi-topology memory.

    This is the main entry point for adding external knowledge
    to the memory system. Documents are:
    1. Chunked structurally (respecting headings/code blocks)
    2. Annotated with spatial context (file, section path)
    3. Tagged with facets (Diataxis type, persona, domain)
    4. Optionally linked via concept relationships

    Args:
        unified_store: The unified memory store
        file_path: Path to the document
        content: Document content
        extract_facets: Auto-detect Diataxis type, personas, etc.
        extract_topology: Auto-extract concept relationships

    Returns:
        Number of memory nodes created
    """
    from sunwell.simulacrum.extractors.facet_extractor import FacetExtractor
    from sunwell.simulacrum.extractors.structural_chunker import StructuralChunker
    from sunwell.simulacrum.extractors.topology_extractor import TopologyExtractor
    from sunwell.simulacrum.topology.memory_node import MemoryNode

    chunker = StructuralChunker()
    facet_extractor = FacetExtractor() if extract_facets else None

    # Chunk the document structurally
    chunks = chunker.chunk_document(file_path, content)

    nodes: list[MemoryNode] = []
    for chunk, spatial, section in chunks:
        # Extract facets if enabled
        facets = None
        if facet_extractor and section:
            facets = facet_extractor.extract_from_text(
                chunk.summary or chunk.turns[0].content if chunk.turns else "",
                section=section,
                source_type="docs",
            )

        # Create memory node
        node = MemoryNode(
            id=chunk.id,
            content=chunk.summary or (chunk.turns[0].content if chunk.turns else ""),
            chunk=chunk,
            spatial=spatial,
            section=section,
            facets=facets,
        )
        nodes.append(node)
        unified_store.add_node(node)

    # Extract topology relationships if enabled
    if extract_topology and len(nodes) > 1:
        topology_extractor = TopologyExtractor()
        for i, node in enumerate(nodes):
            candidates = nodes[:i] + nodes[i+1:]  # All other nodes
            if len(candidates) > 10:
                candidates = candidates[:10]  # Limit for performance

            edges = topology_extractor.extract_heuristic_relationships(
                source_id=node.id,
                source_text=node.content,
                candidate_ids=[c.id for c in candidates],
                candidate_texts=[c.content for c in candidates],
            )

            for edge in edges:
                unified_store._concept_graph.add_edge(edge)

    # Save the store
    unified_store.save()

    return len(nodes)


async def ingest_codebase(
    unified_store: UnifiedMemoryStore,
    root_path: str,
    file_patterns: list[str] | None = None,
) -> int:
    """Ingest a codebase into multi-topology memory.

    Args:
        unified_store: The unified memory store
        root_path: Root directory of the codebase
        file_patterns: Glob patterns for files to include (e.g., ["*.py", "*.md"])

    Returns:
        Number of memory nodes created
    """
    patterns = file_patterns or ["*.py", "*.md", "*.rst", "*.yaml", "*.json"]
    root = Path(root_path)
    total_nodes = 0

    for pattern in patterns:
        for file_path in root.rglob(pattern):
            if file_path.is_file():
                try:
                    content = file_path.read_text()
                    nodes = await ingest_document(
                        unified_store,
                        str(file_path.relative_to(root)),
                        content,
                    )
                    total_nodes += nodes
                except (UnicodeDecodeError, OSError):
                    continue  # Skip binary/unreadable files

    return total_nodes
