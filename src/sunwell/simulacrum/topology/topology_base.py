# src/sunwell/simulacrum/topology.py
"""Topological memory - models RELATIONSHIPS between concepts as a typed graph.

Enables queries like:
- "What contradicts X?"
- "What does X depend on?"
- "What elaborates on X?"
- "Find the chain from A to B"

Part of RFC-014: Multi-Topology Memory.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RelationType(Enum):
    """Types of relationships between concepts."""

    # Knowledge relationships
    ELABORATES = "elaborates"
    """X provides more detail about Y. Directional: X → Y."""

    SUMMARIZES = "summarizes"
    """X is a summary of Y. Directional: X → Y."""

    EXEMPLIFIES = "exemplifies"
    """X is an example of Y. Directional: X → Y."""

    # Logical relationships
    CONTRADICTS = "contradicts"
    """X conflicts with Y. Bidirectional."""

    SUPPORTS = "supports"
    """X provides evidence for Y. Directional: X → Y."""

    QUALIFIES = "qualifies"
    """X adds conditions/caveats to Y. Directional: X → Y."""

    # Structural relationships
    DEPENDS_ON = "depends_on"
    """X requires Y to be understood. Directional: X → Y."""

    SUPERSEDES = "supersedes"
    """X replaces Y (newer version). Directional: X → Y."""

    RELATES_TO = "relates_to"
    """X is topically related to Y. Bidirectional."""

    # Temporal relationships
    FOLLOWS = "follows"
    """X comes after Y in sequence. Directional: X → Y."""

    UPDATES = "updates"
    """X is an update to Y. Directional: X → Y."""


@dataclass(frozen=True, slots=True)
class ConceptEdge:
    """A typed, weighted edge between two memory nodes.

    Represents relationships like:
    - "RFC-014 ELABORATES RFC-013"
    - "Claim X CONTRADICTS Claim Y"
    - "Feature A DEPENDS_ON Feature B"
    """

    source_id: str
    """ID of the source memory node."""

    target_id: str
    """ID of the target memory node."""

    relation: RelationType
    """Type of relationship."""

    confidence: float = 1.0
    """How confident we are in this relationship (0.0-1.0)."""

    evidence: str = ""
    """Why this relationship exists (human or LLM explanation)."""

    auto_extracted: bool = False
    """True if relationship was auto-detected, False if human-confirmed."""

    timestamp: str = ""
    """When this relationship was created."""

    def __str__(self) -> str:
        return f"{self.source_id} --{self.relation.value}--> {self.target_id}"

    @property
    def is_bidirectional(self) -> bool:
        """Some relationships are symmetric."""
        return self.relation in {
            RelationType.CONTRADICTS,
            RelationType.RELATES_TO,
        }


@dataclass
class ConceptGraph:
    """Graph of concept relationships for topological retrieval.

    Enables queries like:
    - "What contradicts X?"
    - "What does X depend on?"
    - "What elaborates on X?"
    - "Find the chain from A to B"
    """

    _edges: dict[str, list[ConceptEdge]] = field(default_factory=dict)
    """Adjacency list: source_id -> list of outgoing edges."""

    _reverse_edges: dict[str, list[ConceptEdge]] = field(default_factory=dict)
    """Reverse adjacency: target_id -> list of incoming edges."""

    def add_edge(self, edge: ConceptEdge) -> None:
        """Add an edge to the graph."""
        # Forward edge
        if edge.source_id not in self._edges:
            self._edges[edge.source_id] = []
        self._edges[edge.source_id].append(edge)

        # Reverse edge for efficient lookup
        if edge.target_id not in self._reverse_edges:
            self._reverse_edges[edge.target_id] = []
        self._reverse_edges[edge.target_id].append(edge)

        # For bidirectional relations, add reverse
        if edge.is_bidirectional:
            reverse = ConceptEdge(
                source_id=edge.target_id,
                target_id=edge.source_id,
                relation=edge.relation,
                confidence=edge.confidence,
                evidence=edge.evidence,
                auto_extracted=edge.auto_extracted,
                timestamp=edge.timestamp,
            )
            if reverse.source_id not in self._edges:
                self._edges[reverse.source_id] = []
            self._edges[reverse.source_id].append(reverse)

    def get_outgoing(
        self,
        node_id: str,
        relation: RelationType | None = None,
    ) -> list[ConceptEdge]:
        """Get edges from a node, optionally filtered by type."""
        edges = self._edges.get(node_id, [])
        if relation:
            edges = [e for e in edges if e.relation == relation]
        return edges

    def get_incoming(
        self,
        node_id: str,
        relation: RelationType | None = None,
    ) -> list[ConceptEdge]:
        """Get edges to a node, optionally filtered by type."""
        edges = self._reverse_edges.get(node_id, [])
        if relation:
            edges = [e for e in edges if e.relation == relation]
        return edges

    def find_contradictions(self, node_id: str) -> list[ConceptEdge]:
        """Find all nodes that contradict the given node."""
        return self.get_outgoing(node_id, RelationType.CONTRADICTS)

    def find_dependencies(self, node_id: str) -> list[str]:
        """Find all nodes that the given node depends on (transitive)."""
        visited = set()
        to_visit = [node_id]
        dependencies = []

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)

            for edge in self.get_outgoing(current, RelationType.DEPENDS_ON):
                dependencies.append(edge.target_id)
                to_visit.append(edge.target_id)

        return dependencies

    def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> list[ConceptEdge] | None:
        """Find shortest path between two nodes via any relationship.

        Returns list of edges forming the path, or None if no path exists.

        Complexity: O(V + E) — BFS traversal, bounded by max_depth.
        """
        if from_id == to_id:
            return []

        # BFS for shortest path
        queue: deque[tuple[str, list[ConceptEdge]]] = deque([(from_id, [])])
        visited = {from_id}

        while queue:
            current, path = queue.popleft()

            if len(path) >= max_depth:
                continue

            for edge in self.get_outgoing(current):
                if edge.target_id == to_id:
                    return path + [edge]

                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, path + [edge]))

        return None

    def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
    ) -> set[str]:
        """Get all nodes within N hops of the given node."""
        neighborhood = {node_id}
        frontier = {node_id}

        for _ in range(depth):
            new_frontier = set()
            for node in frontier:
                for edge in self.get_outgoing(node):
                    new_frontier.add(edge.target_id)
                for edge in self.get_incoming(node):
                    new_frontier.add(edge.source_id)
            frontier = new_frontier - neighborhood
            neighborhood.update(frontier)

        return neighborhood

    def to_dict(self) -> dict:
        """Serialize graph for storage."""
        return {
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "relation": e.relation.value,
                    "confidence": e.confidence,
                    "evidence": e.evidence,
                    "auto_extracted": e.auto_extracted,
                    "timestamp": e.timestamp,
                }
                for edges in self._edges.values()
                for e in edges
                if not e.is_bidirectional or e.source_id < e.target_id  # Dedupe bidirectional
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConceptGraph:
        """Deserialize graph from storage."""
        graph = cls()
        for edge_data in data.get("edges", []):
            edge = ConceptEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relation=RelationType(edge_data["relation"]),
                confidence=edge_data.get("confidence", 1.0),
                evidence=edge_data.get("evidence", ""),
                auto_extracted=edge_data.get("auto_extracted", False),
                timestamp=edge_data.get("timestamp", ""),
            )
            graph.add_edge(edge)
        return graph

    def prune(
        self,
        min_confidence: float = 0.3,
        max_edges_per_node: int = 50,
        decay_factor: float = 0.95,
        decay_days: int = 7,
    ) -> int:
        """Prune low-confidence and stale edges to prevent unbounded growth.

        Strategy:
        1. Apply time-based confidence decay to auto-extracted edges
        2. Remove edges below min_confidence threshold
        3. Keep only top-k edges per node (by confidence)

        Returns: Number of edges removed.

        Complexity: O(E log E) due to sorting per node.
        """
        removed = 0
        now = datetime.now()

        # Phase 1: Apply decay and collect edges to remove
        edges_to_remove: list[tuple[str, ConceptEdge]] = []

        for source_id, edges in list(self._edges.items()):
            # Apply decay to auto-extracted edges
            decayed_edges = []
            for edge in edges:
                new_confidence = edge.confidence

                if edge.auto_extracted and edge.timestamp:
                    try:
                        edge_time = datetime.fromisoformat(edge.timestamp)
                        days_old = (now - edge_time).days
                        decay_periods = days_old // decay_days
                        new_confidence = edge.confidence * (decay_factor ** decay_periods)
                    except ValueError:
                        pass

                if new_confidence < min_confidence:
                    edges_to_remove.append((source_id, edge))
                else:
                    # Update confidence (immutable, so recreate)
                    decayed_edges.append(ConceptEdge(
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        relation=edge.relation,
                        confidence=new_confidence,
                        evidence=edge.evidence,
                        auto_extracted=edge.auto_extracted,
                        timestamp=edge.timestamp,
                    ))

            self._edges[source_id] = decayed_edges

            # Phase 2: Limit edges per node
            if len(decayed_edges) > max_edges_per_node:
                sorted_edges = sorted(decayed_edges, key=lambda e: e.confidence, reverse=True)
                keep = sorted_edges[:max_edges_per_node]
                drop = sorted_edges[max_edges_per_node:]
                self._edges[source_id] = keep
                for edge in drop:
                    edges_to_remove.append((source_id, edge))

        # Phase 3: Remove from reverse index
        for source_id, edge in edges_to_remove:
            if edge.target_id in self._reverse_edges:
                self._reverse_edges[edge.target_id] = [
                    e for e in self._reverse_edges[edge.target_id]
                    if e.source_id != source_id or e.relation != edge.relation
                ]
            removed += 1

        return removed

    @property
    def stats(self) -> dict:
        """Graph statistics for monitoring."""
        total_edges = sum(len(edges) for edges in self._edges.values())
        nodes_with_edges = len(self._edges)
        avg_degree = total_edges / nodes_with_edges if nodes_with_edges else 0

        return {
            "total_edges": total_edges,
            "nodes_with_edges": nodes_with_edges,
            "avg_out_degree": round(avg_degree, 2),
            "max_out_degree": max((len(e) for e in self._edges.values()), default=0),
        }
