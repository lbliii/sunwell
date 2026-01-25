"""ToC data models for reasoning-based navigation (RFC-124).

Provides hierarchical Table of Contents structures optimized for
in-context LLM reasoning about codebase structure.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

# Pre-compiled regex for node ID generation (avoid recompiling per-call)
_RE_NODE_ID_CLEAN = re.compile(r"[^a-zA-Z0-9_]")

# Node types for the ToC tree
NodeType = Literal["module", "class", "function", "directory", "file"]


@dataclass(frozen=True, slots=True)
class TocNode:
    """Single node in the Table of Contents tree.

    Designed for compact in-context consumption by the LLM.
    Target: ~15 tokens per node in JSON serialization.

    Attributes:
        node_id: Unique identifier (e.g., 'sunwell.planning.naaru.harmonic').
        title: Human-readable title.
        node_type: Type: 'module', 'class', 'function', 'directory', 'file'.
        summary: 1-2 sentence description of what this contains.
        path: File path (for navigation).
        line_range: Start/end lines for code entities.
        children: Child node IDs (for tree traversal).
        cross_refs: Detected cross-references ('see X', 'imports Y').
        concepts: Semantic concepts this node relates to (for reasoning hints).
    """

    node_id: str
    title: str
    node_type: NodeType
    summary: str
    path: str
    line_range: tuple[int, int] | None = None
    children: tuple[str, ...] = ()
    cross_refs: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()

    def to_compact_dict(self) -> dict:
        """Serialize to compact dict for context window.

        Uses short keys to minimize tokens:
        - id: node_id
        - t: node_type
        - s: summary
        - c: children (omitted if empty)
        - r: cross_refs (omitted if empty)
        - k: concepts (omitted if empty)
        """
        d: dict = {
            "id": self.node_id,
            "t": self.node_type,
            "s": self.summary,
        }
        if self.children:
            d["c"] = list(self.children)
        if self.cross_refs:
            d["r"] = list(self.cross_refs)
        if self.concepts:
            d["k"] = list(self.concepts)
        return d


@dataclass(slots=True)
class ProjectToc:
    """Complete project Table of Contents.

    Storage: `.sunwell/navigation/toc.json`

    The ToC is designed to fit in LLM context windows with depth-limited
    serialization. For large projects, use pagination via get_subtree().

    Token budget targets:
    - Small (<100 files): ~2,250 tokens (full ToC)
    - Medium (100-500 files): ~7,500 tokens (depth=2 + expansion)
    - Large (500-1000 files): ~18,000 tokens (depth=1 + pagination)
    """

    root_id: str
    """Root node ID (typically project name)."""

    nodes: dict[str, TocNode] = field(default_factory=dict)
    """All nodes indexed by ID."""

    # Indexes for fast lookup
    path_to_node: dict[str, str] = field(default_factory=dict)
    """File path → node ID."""

    concept_index: dict[str, list[str]] = field(default_factory=dict)
    """Concept → node IDs that contain it."""

    # Metadata
    generated_at: datetime | None = None
    file_count: int = 0
    node_count: int = 0

    def add_node(self, node: TocNode) -> None:
        """Add a node to the ToC.

        Updates all indexes automatically.

        Args:
            node: TocNode to add.
        """
        self.nodes[node.node_id] = node
        self.path_to_node[node.path] = node.node_id
        self.node_count = len(self.nodes)

        # Update concept index
        for concept in node.concepts:
            if concept not in self.concept_index:
                self.concept_index[concept] = []
            self.concept_index[concept].append(node.node_id)

    def get_node(self, node_id: str) -> TocNode | None:
        """Get a node by ID.

        Args:
            node_id: The node identifier.

        Returns:
            TocNode if found, None otherwise.
        """
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> list[TocNode]:
        """Get all child nodes for a given node.

        Args:
            node_id: Parent node ID.

        Returns:
            List of child TocNodes.
        """
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children if cid in self.nodes]

    def get_nodes_by_concept(self, concept: str) -> list[TocNode]:
        """Get all nodes related to a concept.

        Args:
            concept: Concept name (e.g., 'auth', 'api').

        Returns:
            List of TocNodes tagged with this concept.
        """
        node_ids = self.concept_index.get(concept, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def to_context_json(self, max_depth: int = 3) -> str:
        """Serialize ToC for LLM context window.

        Produces compact JSON optimized for in-context reasoning.
        Uses depth-limited traversal to control token count.

        Args:
            max_depth: Maximum tree depth to include.

        Returns:
            JSON string suitable for LLM context.
        """
        if not self.root_id or self.root_id not in self.nodes:
            return "[]"

        nodes_to_include = self._collect_nodes_to_depth(self.root_id, max_depth)
        compact_nodes = [self.nodes[nid].to_compact_dict() for nid in nodes_to_include]
        return json.dumps(compact_nodes, separators=(",", ":"))

    def _collect_nodes_to_depth(
        self, start_id: str, max_depth: int, current_depth: int = 0
    ) -> list[str]:
        """Collect node IDs up to a given depth.

        Args:
            start_id: Starting node ID.
            max_depth: Maximum depth to traverse.
            current_depth: Current traversal depth.

        Returns:
            List of node IDs in breadth-first order.
        """
        if current_depth > max_depth:
            return []

        result = [start_id]
        node = self.nodes.get(start_id)
        if node and current_depth < max_depth:
            for child_id in node.children:
                if child_id in self.nodes:
                    result.extend(
                        self._collect_nodes_to_depth(child_id, max_depth, current_depth + 1)
                    )
        return result

    def get_subtree(self, node_id: str, depth: int = 2) -> str:
        """Get JSON for a specific subtree.

        Used for iterative navigation: expand a section on demand.

        Args:
            node_id: Root of subtree to expand.
            depth: How deep to expand.

        Returns:
            JSON string for the subtree.
        """
        if node_id not in self.nodes:
            return "[]"

        nodes_to_include = self._collect_nodes_to_depth(node_id, depth)
        compact_nodes = [self.nodes[nid].to_compact_dict() for nid in nodes_to_include]
        return json.dumps(compact_nodes, separators=(",", ":"))

    def estimate_tokens(self, max_depth: int = 3) -> int:
        """Estimate token count for serialized ToC.

        Rough estimate: ~15 tokens per node.

        Args:
            max_depth: Depth limit for estimation.

        Returns:
            Estimated token count.
        """
        nodes = self._collect_nodes_to_depth(self.root_id, max_depth)
        return len(nodes) * 15

    def save(self, base_path: Path) -> None:
        """Save ToC to disk.

        Storage location: `{base_path}/navigation/toc.json`

        Args:
            base_path: Base directory (typically .sunwell/).
        """
        toc_path = base_path / "navigation" / "toc.json"
        toc_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "root_id": self.root_id,
            "nodes": {
                nid: {
                    "node_id": n.node_id,
                    "title": n.title,
                    "node_type": n.node_type,
                    "summary": n.summary,
                    "path": n.path,
                    "line_range": list(n.line_range) if n.line_range else None,
                    "children": list(n.children),
                    "cross_refs": list(n.cross_refs),
                    "concepts": list(n.concepts),
                }
                for nid, n in self.nodes.items()
            },
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "file_count": self.file_count,
            "node_count": self.node_count,
        }
        toc_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, base_path: Path) -> ProjectToc | None:
        """Load ToC from disk.

        Args:
            base_path: Base directory (typically .sunwell/).

        Returns:
            ProjectToc if found, None otherwise.
        """
        toc_path = base_path / "navigation" / "toc.json"
        if not toc_path.exists():
            return None

        try:
            data = json.loads(toc_path.read_text())

            toc = cls(root_id=data["root_id"])
            toc.generated_at = (
                datetime.fromisoformat(data["generated_at"])
                if data.get("generated_at")
                else None
            )
            toc.file_count = data.get("file_count", 0)

            # Rebuild nodes
            for _nid, node_data in data.get("nodes", {}).items():
                node = TocNode(
                    node_id=node_data["node_id"],
                    title=node_data["title"],
                    node_type=node_data["node_type"],
                    summary=node_data["summary"],
                    path=node_data["path"],
                    line_range=(
                        tuple(node_data["line_range"]) if node_data.get("line_range") else None
                    ),
                    children=tuple(node_data.get("children", [])),
                    cross_refs=tuple(node_data.get("cross_refs", [])),
                    concepts=tuple(node_data.get("concepts", [])),
                )
                toc.add_node(node)

            return toc
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if ToC needs rebuilding.

        Args:
            max_age_hours: Maximum age before considered stale.

        Returns:
            True if stale or missing timestamp.
        """
        if not self.generated_at:
            return True

        age = datetime.now() - self.generated_at
        return age.total_seconds() > (max_age_hours * 3600)


def node_id_from_path(path: Path, root: Path) -> str:
    """Generate a node ID from a file path.

    Converts path to a dotted identifier:
    - `sunwell/planning/naaru/harmonic.py` → `sunwell.planning.naaru.harmonic`

    Args:
        path: File path.
        root: Project root for relative path calculation.

    Returns:
        Dotted node ID.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path

    # Remove extension and convert to dotted notation
    parts = list(relative.with_suffix("").parts)

    # Clean up parts (remove invalid Python identifiers)
    clean_parts = []
    for part in parts:
        # Replace non-alphanumeric with underscore
        clean = _RE_NODE_ID_CLEAN.sub("_", part)
        # Ensure doesn't start with number
        if clean and clean[0].isdigit():
            clean = "_" + clean
        if clean:
            clean_parts.append(clean)

    return ".".join(clean_parts)
