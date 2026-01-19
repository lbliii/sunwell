# src/sunwell/simulacrum/unified_store.py
"""Unified store supporting all memory topologies.

Combines:
- Temporal (RFC-013): Progressive compression
- Spatial: Position-aware retrieval
- Structural: Document-hierarchy-aware retrieval
- Topological: Graph-based relationship queries
- Multi-Faceted: Cross-dimensional filtering

Part of RFC-014: Multi-Topology Memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from sunwell.simulacrum.topology.memory_node import MemoryNode
from sunwell.simulacrum.topology.topology_base import ConceptGraph, RelationType
from sunwell.simulacrum.topology.facets import FacetedIndex, FacetQuery
from sunwell.simulacrum.topology.spatial import SpatialQuery, spatial_match, SpatialContext, PositionType
from sunwell.simulacrum.topology.structural import DocumentTree
from sunwell.embedding.index import InMemoryIndex

if TYPE_CHECKING:
    from sunwell.embedding.protocol import EmbeddingProtocol


@dataclass
class UnifiedMemoryStore:
    """Unified store supporting all memory topologies.
    
    Combines:
    - Temporal (RFC-013): Progressive compression
    - Spatial: Position-aware retrieval
    - Structural: Document-hierarchy-aware retrieval
    - Topological: Graph-based relationship queries
    - Multi-Faceted: Cross-dimensional filtering
    """
    
    base_path: Path
    
    # Embedding dimensions (default: OpenAI text-embedding-3-small)
    embedding_dims: int = 1536
    
    # Core storage
    _nodes: dict[str, MemoryNode] = field(default_factory=dict)
    
    # Indexes
    _concept_graph: ConceptGraph = field(default_factory=ConceptGraph)
    _facet_index: FacetedIndex = field(default_factory=FacetedIndex)
    _document_trees: dict[str, DocumentTree] = field(default_factory=dict)
    
    # Vector index for semantic search (uses existing InMemoryIndex)
    _embedding_index: InMemoryIndex | None = field(default=None, init=False)
    
    # Optional embedder for query-time embedding
    _embedder: "EmbeddingProtocol | None" = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        """Initialize the embedding index."""
        self._embedding_index = InMemoryIndex(_dimensions=self.embedding_dims)
    
    def set_embedder(self, embedder: "EmbeddingProtocol") -> None:
        """Set the embedder for query-time embedding generation.
        
        Also reinitializes the embedding index if dimensions change.
        """
        self._embedder = embedder
        
        # Reinitialize index if dimensions differ
        if embedder.dimensions != self.embedding_dims:
            self.embedding_dims = embedder.dimensions
            self._embedding_index = InMemoryIndex(_dimensions=self.embedding_dims)
            
            # Re-index existing nodes with embeddings
            for node in self._nodes.values():
                if node.embedding and len(node.embedding) == self.embedding_dims:
                    vector = np.array(node.embedding, dtype=np.float32)
                    self._embedding_index.add(
                        id=node.id,
                        vector=vector,
                        metadata={"content_preview": node.content[:100]},
                    )
    
    def add_node(self, node: MemoryNode) -> None:
        """Add a memory node to the store.
        
        Complexity: O(f + e) where f=facets, e=edges.
        """
        self._nodes[node.id] = node
        
        # Update facet index — O(f)
        if node.facets:
            self._facet_index.add(node.id, node.facets)
        
        # Update concept graph — O(e)
        for edge in node.outgoing_edges:
            self._concept_graph.add_edge(edge)
        
        # Update embedding index — O(1) amortized
        if node.embedding and self._embedding_index:
            vector = np.array(node.embedding, dtype=np.float32)
            self._embedding_index.add(
                id=node.id,
                vector=vector,
                metadata={"content_preview": node.content[:100]},
            )
    
    def get_node(self, node_id: str) -> MemoryNode | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the store."""
        if node_id not in self._nodes:
            return False
        
        # Remove from facet index
        self._facet_index.remove(node_id)
        
        # Remove from embedding index
        if self._embedding_index:
            self._embedding_index.delete(node_id)
        
        # Remove the node
        del self._nodes[node_id]
        return True
    
    # === Temporal Retrieval (RFC-013 style) ===
    
    def get_recent(self, limit: int = 10) -> list[MemoryNode]:
        """Get most recent nodes."""
        nodes = list(self._nodes.values())
        nodes.sort(key=lambda n: n.created_at, reverse=True)
        return nodes[:limit]
    
    # === Spatial Retrieval ===
    
    def query_spatial(
        self,
        query: SpatialQuery,
        limit: int = 10,
    ) -> list[tuple[MemoryNode, float]]:
        """Query nodes by spatial constraints."""
        results = []
        
        for node in self._nodes.values():
            if node.spatial:
                score = spatial_match(node.spatial, query)
                if score > 0:
                    results.append((node, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    # === Structural Retrieval ===
    
    def query_by_section(
        self,
        section_title: str,
        file_path: str | None = None,
    ) -> list[MemoryNode]:
        """Find nodes under a specific section."""
        results = []
        
        for node in self._nodes.values():
            if node.spatial and node.spatial.section_path:
                if section_title.lower() in " > ".join(node.spatial.section_path).lower():
                    if file_path is None or node.spatial.file_path == file_path:
                        results.append(node)
        
        return results
    
    # === Topological Retrieval ===
    
    def find_contradictions(self, node_id: str) -> list[MemoryNode]:
        """Find nodes that contradict the given node."""
        edges = self._concept_graph.find_contradictions(node_id)
        return [self._nodes[e.target_id] for e in edges if e.target_id in self._nodes]
    
    def find_elaborations(self, node_id: str) -> list[MemoryNode]:
        """Find nodes that elaborate on the given node."""
        edges = self._concept_graph.get_incoming(node_id, RelationType.ELABORATES)
        return [self._nodes[e.source_id] for e in edges if e.source_id in self._nodes]
    
    def find_dependencies(self, node_id: str) -> list[MemoryNode]:
        """Find all nodes the given node depends on (transitive)."""
        dep_ids = self._concept_graph.find_dependencies(node_id)
        return [self._nodes[did] for did in dep_ids if did in self._nodes]
    
    def find_related(self, node_id: str, depth: int = 2) -> list[MemoryNode]:
        """Find nodes related to the given node within N hops."""
        neighborhood = self._concept_graph.get_neighborhood(node_id, depth)
        return [self._nodes[nid] for nid in neighborhood if nid in self._nodes and nid != node_id]
    
    # === Multi-Faceted Retrieval ===
    
    def query_facets(
        self,
        query: FacetQuery,
        limit: int = 10,
    ) -> list[tuple[MemoryNode, float]]:
        """Query nodes by facets."""
        results = self._facet_index.query(query)
        return [
            (self._nodes[node_id], score)
            for node_id, score in results[:limit]
            if node_id in self._nodes
        ]
    
    # === Hybrid Retrieval ===
    
    def query(
        self,
        text_query: str | None = None,
        spatial_query: SpatialQuery | None = None,
        facet_query: FacetQuery | None = None,
        relationship_from: str | None = None,
        relationship_type: RelationType | None = None,
        limit: int = 10,
    ) -> list[tuple[MemoryNode, float]]:
        """Hybrid query combining multiple topology dimensions.
        
        Example:
            store.query(
                text_query="caching",
                spatial_query=SpatialQuery(section_contains="Limitations"),
                facet_query=FacetQuery(diataxis_type=DiataxisType.REFERENCE),
            )
        
        Returns nodes matching ALL constraints, scored by relevance.
        """
        # Start with all nodes
        candidates: set[str] | None = None
        scores: dict[str, list[float]] = {}
        
        # Filter by facets (uses inverted index, fast)
        if facet_query and facet_query.has_constraints():
            facet_results = self._facet_index.query(facet_query)
            candidates = {node_id for node_id, _ in facet_results}
            for node_id, score in facet_results:
                scores.setdefault(node_id, []).append(score)
        
        # Filter by relationships
        if relationship_from:
            related_ids = self._concept_graph.get_neighborhood(relationship_from, depth=2)
            if relationship_type:
                edges = self._concept_graph.get_outgoing(relationship_from, relationship_type)
                related_ids = {e.target_id for e in edges}
            candidates = related_ids if candidates is None else candidates & related_ids
        
        # Filter by spatial
        if spatial_query:
            spatial_candidates = set()
            for node in self._nodes.values():
                if node.spatial:
                    score = spatial_match(node.spatial, spatial_query)
                    if score > 0:
                        spatial_candidates.add(node.id)
                        scores.setdefault(node.id, []).append(score)
            candidates = spatial_candidates if candidates is None else candidates & spatial_candidates
        
        # Filter by text (embedding similarity) — O(n) vectorized
        if text_query and self._embedding_index and self._embedding_index.count > 0:
            if self._embedder:
                # Use embedding-based semantic search
                query_vector = np.array(self._embedder.embed(text_query), dtype=np.float32)
                search_results = self._embedding_index.search(query_vector, top_k=limit * 3)
                text_candidates = set()
                for result in search_results:
                    text_candidates.add(result.id)
                    scores.setdefault(result.id, []).append(result.score)
                candidates = text_candidates if candidates is None else candidates & text_candidates
            else:
                # Fall back to keyword match — O(n)
                text_candidates = set()
                query_lower = text_query.lower()
                for node in self._nodes.values():
                    if query_lower in node.content.lower():
                        text_candidates.add(node.id)
                        scores.setdefault(node.id, []).append(0.8)
                candidates = text_candidates if candidates is None else candidates & text_candidates
        
        # If no filters, return recent
        if candidates is None:
            return [(n, 1.0) for n in self.get_recent(limit)]
        
        # Score and sort
        results = []
        for node_id in candidates:
            node = self._nodes.get(node_id)
            if node:
                node_scores = scores.get(node_id, [1.0])
                avg_score = sum(node_scores) / len(node_scores)
                results.append((node, avg_score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    # === Persistence ===
    
    def save(self) -> None:
        """Persist store to disk.
        
        Complexity: O(n) — serializes all nodes and indexes.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Save nodes
        nodes_data = {}
        for node_id, node in self._nodes.items():
            nodes_data[node_id] = node.to_dict()
        
        with open(self.base_path / "nodes.json", "w") as f:
            json.dump(nodes_data, f, indent=2)
        
        # Save concept graph
        with open(self.base_path / "graph.json", "w") as f:
            json.dump(self._concept_graph.to_dict(), f, indent=2)
        
        # Save embedding index (uses InMemoryIndex.save())
        if self._embedding_index and self._embedding_index.count > 0:
            self._embedding_index.save(self.base_path / "embeddings")
    
    @classmethod
    def load(cls, base_path: Path, embedding_dims: int = 1536) -> "UnifiedMemoryStore":
        """Load store from disk.
        
        Complexity: O(n) — deserializes all nodes and indexes.
        """
        store = cls(base_path=base_path, embedding_dims=embedding_dims)
        
        nodes_path = base_path / "nodes.json"
        if nodes_path.exists():
            with open(nodes_path) as f:
                nodes_data = json.load(f)
            
            for node_id, data in nodes_data.items():
                node = MemoryNode.from_dict(data)
                # Note: add_node without embedding — embeddings loaded separately
                store._nodes[node.id] = node
                if node.facets:
                    store._facet_index.add(node.id, node.facets)
        
        # Load concept graph
        graph_path = base_path / "graph.json"
        if graph_path.exists():
            with open(graph_path) as f:
                store._concept_graph = ConceptGraph.from_dict(json.load(f))
        
        # Load embedding index (uses InMemoryIndex.load())
        embeddings_path = base_path / "embeddings"
        if (embeddings_path / "metadata.json").exists():
            store._embedding_index = InMemoryIndex.load(embeddings_path)
        
        return store
    
    # === Statistics ===
    
    @property
    def stats(self) -> dict:
        """Get store statistics."""
        return {
            "total_nodes": len(self._nodes),
            "graph": self._concept_graph.stats,
            "facets": self._facet_index.stats(),
            "embeddings": self._embedding_index.count if self._embedding_index else 0,
        }
