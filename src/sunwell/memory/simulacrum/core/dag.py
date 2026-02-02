"""ConversationDAG - Graph-based conversation structure.

Unlike linear chat history, conversations form a DAG:
- Branches when exploring alternatives
- Merges when conclusions are reached
- Dead ends are marked and compressed
- Learnings propagate up the graph

This enables:
- Non-linear exploration (try A, backtrack, try B)
- Parallel conversation threads
- Smart compression (keep important paths, compress dead ends)
- Provenance tracking (where did this insight come from?)

Graph scoring (MIRA-inspired):
- Learnings form a relationship graph (supports, derives_from, etc.)
- Inbound references indicate "hub" knowledge
- Used for importance scoring in retrieval
"""

import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from sunwell.foundation.utils import safe_json_dump, safe_json_load

logger = logging.getLogger(__name__)

from sunwell.memory.simulacrum.core.retrieval.learning_graph import (
    LearningGraph,
    RelationType,
    detect_relationships,
)
from sunwell.memory.simulacrum.core.turn import (
    Learning,
    TemplateData,
    TemplateVariable,
    Turn,
    TurnType,
)


@dataclass(slots=True)
class ConversationDAG:
    """Directed Acyclic Graph of conversation turns.

    Represents conversation as a graph rather than a linear list,
    enabling branching, merging, and non-linear exploration.

    Key properties:
    - Content-addressable: turns identified by hash
    - Immutable history: turns never modified, only added
    - Learnings extracted: insights persist beyond compression
    - Learning relationships: graph of how learnings relate (supports, derives, etc.)
    """

    # Core storage - O(1) lookup by ID
    turns: dict[str, Turn] = field(default_factory=dict)
    """All turns indexed by content-hash ID."""

    learnings: dict[str, Learning] = field(default_factory=dict)
    """Extracted learnings indexed by ID."""

    # Graph structure
    children: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    """Parent ID → set of child IDs."""

    # Pointers
    roots: set[str] = field(default_factory=set)
    """Turn IDs with no parents (conversation starts)."""

    heads: set[str] = field(default_factory=set)
    """Turn IDs with no children (current endpoints)."""

    active_head: str | None = None
    """Current position in the conversation."""

    # Metadata
    branches: dict[str, str] = field(default_factory=dict)
    """Named branches: name → head turn ID."""

    dead_ends: set[str] = field(default_factory=set)
    """Turn IDs marked as dead ends (don't continue)."""

    compressed: set[str] = field(default_factory=set)
    """Turn IDs that have been compressed (full content in cold storage)."""

    # Learning relationship graph (MIRA-inspired hub scoring)
    learning_graph: LearningGraph = field(default_factory=LearningGraph)
    """Graph of relationships between learnings for importance scoring."""

    def add_turn(self, turn: Turn) -> str:
        """Add a turn to the DAG.

        Returns:
            The turn's content-addressable ID.
        """
        turn_id = turn.id

        # Deduplicate - if we've seen this exact content, skip
        if turn_id in self.turns:
            return turn_id

        self.turns[turn_id] = turn

        # Update graph structure
        if not turn.parent_ids:
            self.roots.add(turn_id)
        else:
            for parent_id in turn.parent_ids:
                self.children[parent_id].add(turn_id)
                # Parent is no longer a head
                self.heads.discard(parent_id)

        # This turn is now a head
        self.heads.add(turn_id)

        # Update active head
        self.active_head = turn_id

        return turn_id

    def add_user_message(self, content: str, **kwargs) -> str:
        """Convenience: add a user message."""
        parent_ids = (self.active_head,) if self.active_head else ()
        turn = Turn(
            content=content,
            turn_type=TurnType.USER,
            parent_ids=parent_ids,
            **kwargs,
        )
        return self.add_turn(turn)

    def add_assistant_message(self, content: str, model: str | None = None, **kwargs) -> str:
        """Convenience: add an assistant message."""
        parent_ids = (self.active_head,) if self.active_head else ()
        turn = Turn(
            content=content,
            turn_type=TurnType.ASSISTANT,
            parent_ids=parent_ids,
            model=model,
            **kwargs,
        )
        return self.add_turn(turn)

    def add_learning(self, learning: Learning, auto_detect_relationships: bool = True) -> str:
        """Add an extracted learning.

        Optionally detects relationships to existing learnings and
        updates the learning graph for importance scoring.

        Args:
            learning: The learning to add
            auto_detect_relationships: If True, detect relationships to existing learnings

        Returns:
            The learning's content-addressable ID
        """
        self.learnings[learning.id] = learning

        # Auto-detect relationships for graph scoring
        if auto_detect_relationships and len(self.learnings) > 1:
            existing = [l for l in self.learnings.values() if l.id != learning.id]
            edges = detect_relationships(learning, existing)
            for edge in edges:
                self.learning_graph.add_edge(edge)

        return learning.id

    def find_learning(self, learning_id: str) -> Learning | None:
        """Find a learning by ID.

        Args:
            learning_id: The content-addressable ID of the learning

        Returns:
            The Learning if found, None otherwise
        """
        return self.learnings.get(learning_id)

    def replace_learning(self, old: Learning, new: Learning) -> bool:
        """Replace a learning with an updated version (immutable update pattern).

        Since Learning is frozen, we can't modify it in place. This method
        removes the old learning and adds the new one, updating any references.

        Note: The new learning may have a different ID if identity-affecting
        fields changed. For graph scoring updates (mention_count, activity_day_*)
        the ID should stay the same since these are metadata fields.

        Args:
            old: The learning to replace
            new: The updated learning

        Returns:
            True if replacement succeeded, False if old learning not found
        """
        if old.id not in self.learnings:
            return False

        # Remove old
        del self.learnings[old.id]

        # Add new (may have same or different ID) - skip auto-detect since relationships preserved
        self.learnings[new.id] = new

        # If ID changed, update learning graph references
        if old.id != new.id:
            self.learning_graph.remove_learning(old.id)
            # Re-detect relationships for the new learning
            existing = [l for l in self.learnings.values() if l.id != new.id]
            edges = detect_relationships(new, existing)
            for edge in edges:
                self.learning_graph.add_edge(edge)

        return True

    def get_inbound_link_count(self, learning_id: str) -> int:
        """Get the number of other learnings that reference this one.

        Used for graph-based importance scoring. Learnings with more
        inbound references are "hub" knowledge and rank higher.

        Args:
            learning_id: The learning ID to check

        Returns:
            Number of inbound references (0 if not in graph)
        """
        return self.learning_graph.inbound_count(learning_id)

    def branch(self, name: str, from_turn: str | None = None) -> str:
        """Create a named branch from a point in history.

        Args:
            name: Branch name.
            from_turn: Turn ID to branch from (default: active head).

        Returns:
            The branch point turn ID.
        """
        branch_point = from_turn or self.active_head
        if branch_point is None:
            raise ValueError("No turn to branch from")

        self.branches[name] = branch_point
        return branch_point

    def checkout(self, branch_or_turn: str) -> None:
        """Switch active head to a branch or turn ID."""
        if branch_or_turn in self.branches:
            self.active_head = self.branches[branch_or_turn]
        elif branch_or_turn in self.turns:
            self.active_head = branch_or_turn
        else:
            raise ValueError(f"Unknown branch or turn: {branch_or_turn}")

    def mark_dead_end(self, turn_id: str | None = None) -> None:
        """Mark current path as a dead end."""
        tid = turn_id or self.active_head
        if tid:
            self.dead_ends.add(tid)

    def get_path_to(self, turn_id: str) -> list[Turn]:
        """Get the path from root to a specific turn.

        Returns turns in chronological order (root → turn).
        """
        path = []
        current = turn_id

        while current:
            turn = self.turns.get(current)
            if not turn:
                break
            path.append(turn)
            # Follow first parent (main thread)
            current = turn.parent_ids[0] if turn.parent_ids else None

        path.reverse()
        return path

    def get_recent_turns(self, n: int = 10) -> list[Turn]:
        """Get n most recent turns from active head."""
        if not self.active_head:
            return []

        path = self.get_path_to(self.active_head)
        return path[-n:]

    def iter_all_turns(self) -> Iterator[Turn]:
        """Iterate all turns in topological order."""
        visited = set()

        def visit(turn_id: str) -> Iterator[Turn]:
            if turn_id in visited:
                return
            visited.add(turn_id)

            turn = self.turns.get(turn_id)
            if not turn:
                return

            # Visit parents first
            for parent_id in turn.parent_ids:
                yield from visit(parent_id)

            yield turn

        # Visit from all heads
        for head_id in self.heads:
            yield from visit(head_id)

    def find_related_turns(
        self,
        tags: set[str],
        limit: int = 10,
    ) -> list[Turn]:
        """Find turns with matching tags (for retrieval)."""
        matches = []
        for turn in self.turns.values():
            if set(turn.tags) & tags:
                matches.append(turn)

        # Sort by recency (timestamp)
        matches.sort(key=lambda t: t.timestamp, reverse=True)
        return matches[:limit]

    def get_active_learnings(self) -> list[Learning]:
        """Get all learnings not superseded by newer versions."""
        return [
            l for l in self.learnings.values()
            if l.superseded_by is None
        ]

    @property
    def stats(self) -> dict:
        """DAG statistics including learning relationship graph."""
        return {
            "total_turns": len(self.turns),
            "roots": len(self.roots),
            "heads": len(self.heads),
            "branches": len(self.branches),
            "dead_ends": len(self.dead_ends),
            "compressed": len(self.compressed),
            "learnings": len(self.learnings),
            "learning_graph": self.learning_graph.stats,
        }

    # =========================================================================
    # RFC-122: Template Data Serialization
    # =========================================================================

    @staticmethod
    def _serialize_template_data(template_data: TemplateData | None) -> dict | None:
        """Serialize TemplateData for JSON storage."""
        if template_data is None:
            return None
        return {
            "name": template_data.name,
            "match_patterns": list(template_data.match_patterns),
            "variables": [
                {
                    "name": v.name,
                    "description": v.description,
                    "var_type": v.var_type,
                    "extraction_hints": list(v.extraction_hints),
                    "default": v.default,
                }
                for v in template_data.variables
            ],
            "produces": list(template_data.produces),
            "requires": list(template_data.requires),
            "expected_artifacts": list(template_data.expected_artifacts),
            "validation_commands": list(template_data.validation_commands),
            "suggested_order": template_data.suggested_order,
        }

    @staticmethod
    def _deserialize_template_data(data: dict | None) -> TemplateData | None:
        """Deserialize TemplateData from JSON storage."""
        if data is None:
            return None
        return TemplateData(
            name=data["name"],
            match_patterns=tuple(data["match_patterns"]),
            variables=tuple(
                TemplateVariable(
                    name=v["name"],
                    description=v["description"],
                    var_type=v["var_type"],
                    extraction_hints=tuple(v["extraction_hints"]),
                    default=v.get("default"),
                )
                for v in data.get("variables", [])
            ),
            produces=tuple(data["produces"]),
            requires=tuple(data["requires"]),
            expected_artifacts=tuple(data["expected_artifacts"]),
            validation_commands=tuple(data["validation_commands"]),
            suggested_order=data.get("suggested_order", 50),
        )

    # =========================================================================
    # Persistence
    # =========================================================================

    def save(self, path: Path) -> None:
        """Save DAG to file."""
        # Serialize learning graph edges
        learning_graph_edges = []
        for edge_list in self.learning_graph._outgoing.values():
            for edge in edge_list:
                learning_graph_edges.append({
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "relation_type": edge.relation_type.value,
                    "weight": edge.weight,
                })

        data = {
            "turns": {
                tid: {
                    "content": t.content,
                    "turn_type": t.turn_type.value,
                    "timestamp": t.timestamp,
                    "parent_ids": list(t.parent_ids),
                    "source": t.source,
                    "token_count": t.token_count,
                    "model": t.model,
                    "confidence": t.confidence,
                    "tags": list(t.tags),
                }
                for tid, t in self.turns.items()
            },
            "learnings": {
                lid: {
                    "fact": l.fact,
                    "source_turns": list(l.source_turns),
                    "confidence": l.confidence,
                    "category": l.category,
                    "timestamp": l.timestamp,
                    "superseded_by": l.superseded_by,
                    # RFC-122: Extended fields
                    "template_data": self._serialize_template_data(l.template_data),
                    "embedding": list(l.embedding) if l.embedding else None,
                    "use_count": l.use_count,
                    "last_used": l.last_used,
                    # Graph scoring fields
                    "mention_count": l.mention_count,
                    "activity_day_created": l.activity_day_created,
                    "activity_day_accessed": l.activity_day_accessed,
                    "happens_at": l.happens_at,
                    "expires_at": l.expires_at,
                }
                for lid, l in self.learnings.items()
            },
            "learning_graph_edges": learning_graph_edges,
            "roots": list(self.roots),
            "heads": list(self.heads),
            "active_head": self.active_head,
            "branches": self.branches,
            "dead_ends": list(self.dead_ends),
            "compressed": list(self.compressed),
        }

        if not safe_json_dump(data, path):
            logger.error("Failed to save DAG to %s", path)

    @classmethod
    def load(cls, path: Path) -> ConversationDAG:
        """Load DAG from file. Returns empty DAG if file missing/corrupted."""
        data = safe_json_load(path, default={})
        if not data:
            return cls()

        dag = cls()

        # Reconstruct turns
        for tid, tdata in data.get("turns", {}).items():
            turn = Turn(
                content=tdata["content"],
                turn_type=TurnType(tdata["turn_type"]),
                timestamp=tdata["timestamp"],
                parent_ids=tuple(tdata["parent_ids"]),
                source=tdata.get("source"),
                token_count=tdata.get("token_count", 0),
                model=tdata.get("model"),
                confidence=tdata.get("confidence"),
                tags=tuple(tdata.get("tags", [])),
            )
            dag.turns[tid] = turn

        # Reconstruct learnings
        for lid, ldata in data.get("learnings", {}).items():
            learning = Learning(
                fact=ldata["fact"],
                source_turns=tuple(ldata["source_turns"]),
                confidence=ldata["confidence"],
                category=ldata["category"],
                timestamp=ldata["timestamp"],
                superseded_by=ldata.get("superseded_by"),
                # RFC-122: Extended fields
                template_data=dag._deserialize_template_data(ldata.get("template_data")),
                embedding=tuple(ldata["embedding"]) if ldata.get("embedding") else None,
                use_count=ldata.get("use_count", 0),
                last_used=ldata.get("last_used"),
                # Graph scoring fields
                mention_count=ldata.get("mention_count", 0),
                activity_day_created=ldata["activity_day_created"],
                activity_day_accessed=ldata["activity_day_accessed"],
                happens_at=ldata.get("happens_at"),
                expires_at=ldata.get("expires_at"),
            )
            dag.learnings[lid] = learning

        # Restore structure
        dag.roots = set(data.get("roots", []))
        dag.heads = set(data.get("heads", []))
        dag.active_head = data.get("active_head")
        dag.branches = data.get("branches", {})
        dag.dead_ends = set(data.get("dead_ends", []))
        dag.compressed = set(data.get("compressed", []))

        # Rebuild children index
        for turn in dag.turns.values():
            for parent_id in turn.parent_ids:
                dag.children[parent_id].add(turn.id)

        # Restore learning graph edges (MIRA-inspired hub scoring)
        from sunwell.memory.simulacrum.core.retrieval.learning_graph import LearningEdge

        for edge_data in data.get("learning_graph_edges", []):
            edge = LearningEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relation_type=RelationType(edge_data["relation_type"]),
                weight=edge_data.get("weight", 1.0),
            )
            dag.learning_graph.add_edge(edge)

        return dag
