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
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from sunwell.simulacrum.core.turn import Turn, TurnType, Learning


@dataclass
class ConversationDAG:
    """Directed Acyclic Graph of conversation turns.
    
    Represents conversation as a graph rather than a linear list,
    enabling branching, merging, and non-linear exploration.
    
    Key properties:
    - Content-addressable: turns identified by hash
    - Immutable history: turns never modified, only added
    - Learnings extracted: insights persist beyond compression
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
    
    def add_learning(self, learning: Learning) -> str:
        """Add an extracted learning."""
        self.learnings[learning.id] = learning
        return learning.id
    
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
        """DAG statistics."""
        return {
            "total_turns": len(self.turns),
            "roots": len(self.roots),
            "heads": len(self.heads),
            "branches": len(self.branches),
            "dead_ends": len(self.dead_ends),
            "compressed": len(self.compressed),
            "learnings": len(self.learnings),
        }
    
    def save(self, path: Path) -> None:
        """Save DAG to file."""
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
                }
                for lid, l in self.learnings.items()
            },
            "roots": list(self.roots),
            "heads": list(self.heads),
            "active_head": self.active_head,
            "branches": self.branches,
            "dead_ends": list(self.dead_ends),
            "compressed": list(self.compressed),
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "ConversationDAG":
        """Load DAG from file."""
        with open(path) as f:
            data = json.load(f)
        
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
        
        return dag
