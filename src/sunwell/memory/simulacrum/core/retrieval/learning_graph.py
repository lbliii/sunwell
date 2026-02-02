"""Learning relationship graph for importance scoring.

Tracks relationships between learnings to compute hub scores
for MIRA-inspired importance scoring. Learnings that are
referenced by many other learnings are "hubs" of knowledge
and should rank higher in retrieval.

Relationship types:
- DERIVES_FROM: This learning was derived from another
- SUPPORTS: This learning provides evidence for another
- CONTRADICTS: This learning conflicts with another
- ELABORATES: This learning expands on another
- SUPERSEDES: This learning replaces another (use Learning.superseded_by)

Thread-safe for concurrent reads; mutations require lock.
"""

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sunwell.foundation.utils import safe_json_dump, safe_json_load
from sunwell.memory.simulacrum.core.turn import Learning

logger = logging.getLogger(__name__)


class RelationType(Enum):
    """Types of relationships between learnings."""

    DERIVES_FROM = "derives_from"
    """This learning was extracted/derived from another."""

    SUPPORTS = "supports"
    """This learning provides evidence for another."""

    CONTRADICTS = "contradicts"
    """This learning conflicts with another."""

    ELABORATES = "elaborates"
    """This learning expands on another."""

    RELATED = "related"
    """Generic semantic similarity relationship."""


@dataclass(frozen=True, slots=True)
class LearningEdge:
    """An edge representing a relationship between two learnings."""

    source_id: str
    """ID of the source learning (the one that references)."""

    target_id: str
    """ID of the target learning (the one being referenced)."""

    relation_type: RelationType
    """Type of relationship."""

    weight: float = 1.0
    """Strength of the relationship (0-1, default 1.0)."""

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.relation_type))


@dataclass(slots=True)
class LearningGraph:
    """Graph of relationships between learnings.

    Maintains adjacency lists for efficient traversal:
    - outgoing: learning_id → list of edges (this learning references others)
    - incoming: learning_id → list of edges (other learnings reference this)

    Thread-safe for concurrent reads. Mutations protected by lock.

    Example:
        >>> graph = LearningGraph()
        >>> graph.add_edge(LearningEdge("fact_1", "fact_2", RelationType.SUPPORTS))
        >>> count = graph.inbound_count("fact_2")  # Returns 1
    """

    _outgoing: dict[str, list[LearningEdge]] = field(
        default_factory=lambda: defaultdict(list)
    )
    """Outgoing edges: learning_id → list of edges."""

    _incoming: dict[str, list[LearningEdge]] = field(
        default_factory=lambda: defaultdict(list)
    )
    """Incoming edges: learning_id → list of edges."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for mutation operations."""

    def add_edge(self, edge: LearningEdge) -> None:
        """Add a relationship edge to the graph.

        Thread-safe.

        Args:
            edge: The edge to add
        """
        with self._lock:
            # Avoid duplicates
            existing = self._outgoing.get(edge.source_id, [])
            for e in existing:
                if e.target_id == edge.target_id and e.relation_type == edge.relation_type:
                    return  # Already exists

            self._outgoing[edge.source_id].append(edge)
            self._incoming[edge.target_id].append(edge)

    def remove_learning(self, learning_id: str) -> None:
        """Remove a learning and all its edges from the graph.

        Thread-safe.

        Args:
            learning_id: The learning ID to remove
        """
        with self._lock:
            # Remove outgoing edges
            if learning_id in self._outgoing:
                for edge in self._outgoing[learning_id]:
                    if edge.target_id in self._incoming:
                        self._incoming[edge.target_id] = [
                            e for e in self._incoming[edge.target_id]
                            if e.source_id != learning_id
                        ]
                del self._outgoing[learning_id]

            # Remove incoming edges
            if learning_id in self._incoming:
                for edge in self._incoming[learning_id]:
                    if edge.source_id in self._outgoing:
                        self._outgoing[edge.source_id] = [
                            e for e in self._outgoing[edge.source_id]
                            if e.target_id != learning_id
                        ]
                del self._incoming[learning_id]

    def inbound_count(self, learning_id: str) -> int:
        """Get count of learnings that reference this one.

        This is the primary metric for hub scoring.

        Args:
            learning_id: The learning ID to check

        Returns:
            Number of unique learnings that reference this one
        """
        edges = self._incoming.get(learning_id, [])
        # Count unique sources (a source can have multiple edge types)
        return len({e.source_id for e in edges})

    def inbound_weighted_count(self, learning_id: str) -> float:
        """Get weighted count of inbound references.

        Considers edge weights for more nuanced scoring.

        Args:
            learning_id: The learning ID to check

        Returns:
            Sum of edge weights for inbound references
        """
        edges = self._incoming.get(learning_id, [])
        return sum(e.weight for e in edges)

    def outbound_count(self, learning_id: str) -> int:
        """Get count of learnings this one references.

        Args:
            learning_id: The learning ID to check

        Returns:
            Number of unique learnings this one references
        """
        edges = self._outgoing.get(learning_id, [])
        return len({e.target_id for e in edges})

    def get_inbound(
        self,
        learning_id: str,
        relation_type: RelationType | None = None,
    ) -> list[LearningEdge]:
        """Get all inbound edges to a learning.

        Args:
            learning_id: The learning ID
            relation_type: Optional filter by relation type

        Returns:
            List of inbound edges
        """
        edges = self._incoming.get(learning_id, [])
        if relation_type:
            return [e for e in edges if e.relation_type == relation_type]
        return list(edges)

    def get_outbound(
        self,
        learning_id: str,
        relation_type: RelationType | None = None,
    ) -> list[LearningEdge]:
        """Get all outbound edges from a learning.

        Args:
            learning_id: The learning ID
            relation_type: Optional filter by relation type

        Returns:
            List of outbound edges
        """
        edges = self._outgoing.get(learning_id, [])
        if relation_type:
            return [e for e in edges if e.relation_type == relation_type]
        return list(edges)

    def get_related(self, learning_id: str) -> set[str]:
        """Get all learnings connected to this one (any direction).

        Args:
            learning_id: The learning ID

        Returns:
            Set of connected learning IDs
        """
        related: set[str] = set()
        for edge in self._outgoing.get(learning_id, []):
            related.add(edge.target_id)
        for edge in self._incoming.get(learning_id, []):
            related.add(edge.source_id)
        return related

    @property
    def stats(self) -> dict:
        """Graph statistics."""
        all_nodes = set(self._outgoing.keys()) | set(self._incoming.keys())
        total_edges = sum(len(edges) for edges in self._outgoing.values())

        return {
            "total_nodes": len(all_nodes),
            "total_edges": total_edges,
            "avg_inbound": total_edges / len(all_nodes) if all_nodes else 0,
        }

    # =========================================================================
    # Persistence
    # =========================================================================

    def save(self, path: Path) -> None:
        """Save graph to file with atomic write.

        Args:
            path: Path to save to
        """
        edges: list[dict] = []
        for edge_list in self._outgoing.values():
            for edge in edge_list:
                edges.append({
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "relation_type": edge.relation_type.value,
                    "weight": edge.weight,
                })

        if not safe_json_dump({"edges": edges}, path):
            logger.error("Failed to save learning graph to %s", path)

    @classmethod
    def load(cls, path: Path) -> LearningGraph:
        """Load graph from file. Returns empty graph if missing/corrupted.

        Args:
            path: Path to load from

        Returns:
            Loaded LearningGraph (empty on error)
        """
        graph = cls()
        data = safe_json_load(path, default={})
        if not data:
            return graph

        for edge_data in data.get("edges", []):
            edge = LearningEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relation_type=RelationType(edge_data["relation_type"]),
                weight=edge_data.get("weight", 1.0),
            )
            graph.add_edge(edge)

        return graph


def detect_relationships(
    new_learning: Learning,
    existing_learnings: list[Learning],
    similarity_threshold: float = 0.5,
) -> list[LearningEdge]:
    """Detect relationships between a new learning and existing ones.

    Uses heuristics to identify relationships:
    - Source turn overlap → DERIVES_FROM
    - Keyword overlap → RELATED
    - Category compatibility → SUPPORTS/ELABORATES
    - Contradiction markers → CONTRADICTS

    Args:
        new_learning: The newly added learning
        existing_learnings: List of existing learnings to check against
        similarity_threshold: Minimum keyword overlap for RELATED

    Returns:
        List of detected edges (new_learning as source)
    """
    edges: list[LearningEdge] = []

    new_words = set(new_learning.fact.lower().split())
    new_sources = set(new_learning.source_turns)

    for existing in existing_learnings:
        if existing.id == new_learning.id:
            continue

        # Check for supersedes relationship (existing marked as superseded by new)
        if existing.superseded_by == new_learning.id:
            edges.append(LearningEdge(
                source_id=new_learning.id,
                target_id=existing.id,
                relation_type=RelationType.ELABORATES,
                weight=1.0,
            ))
            continue

        # Check for source turn overlap → DERIVES_FROM
        existing_sources = set(existing.source_turns)
        if new_sources & existing_sources:
            edges.append(LearningEdge(
                source_id=new_learning.id,
                target_id=existing.id,
                relation_type=RelationType.DERIVES_FROM,
                weight=0.8,
            ))
            continue

        # Check for keyword overlap → RELATED
        existing_words = set(existing.fact.lower().split())
        overlap = new_words & existing_words
        # Exclude common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "to", "of",
            "and", "in", "that", "it", "for", "on", "with", "as", "at", "by", "this", "i",
        }
        meaningful_overlap = overlap - stop_words

        # Compute overlap ratio for similarity and contradiction checks
        new_meaningful = new_words - stop_words
        existing_meaningful = existing_words - stop_words
        if new_meaningful and existing_meaningful:
            overlap_ratio = len(meaningful_overlap) / min(
                len(new_meaningful), len(existing_meaningful)
            )
        else:
            overlap_ratio = 0.0

        if len(meaningful_overlap) >= 3 and overlap_ratio >= similarity_threshold:
            # Same category suggests SUPPORTS, different suggests RELATED
            if new_learning.category == existing.category:
                edges.append(LearningEdge(
                    source_id=new_learning.id,
                    target_id=existing.id,
                    relation_type=RelationType.SUPPORTS,
                    weight=overlap_ratio,
                ))
            else:
                edges.append(LearningEdge(
                    source_id=new_learning.id,
                    target_id=existing.id,
                    relation_type=RelationType.RELATED,
                    weight=overlap_ratio * 0.8,
                ))

        # Check for contradiction markers
        contradiction_markers = {
            "but", "however", "instead", "not", "don't", "doesn't", "failed", "wrong",
        }
        is_contradiction_candidate = (
            (new_words & contradiction_markers)
            and overlap_ratio >= 0.4
            and (existing.category == "dead_end" or new_learning.category == "dead_end")
        )
        if is_contradiction_candidate:
            edges.append(LearningEdge(
                source_id=new_learning.id,
                target_id=existing.id,
                relation_type=RelationType.CONTRADICTS,
                weight=0.7,
            ))

    return edges
