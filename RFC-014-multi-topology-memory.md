# RFC-014: Multi-Topology Memory

**Status:** Draft  
**Author:** Sunwell Contributors  
**Created:** 2026-01-15  
**Updated:** 2026-01-15  
**Related:** [RFC-013: Hierarchical Memory](./RFC-013-hierarchical-memory.md), [RFC-012: Tool Calling](./RFC-012-tool-calling.md)

---

## Summary

Extend RFC-013's temporal-hierarchical memory with **spatial**, **topological**, **structural**, and **multi-faceted** memory models. This enables context-aware retrieval that understands *where* information lives, *how* concepts relate, *what structure* contains them, and *which dimensions* they span.

**Key insight:** Different content types demand different memory topologies. Chat history benefits from temporal chunking (RFC-013), but documents need structural awareness, codebases need spatial context, and frameworks need multi-dimensional tagging.

**v3 addition:** Integrates with RFC-012 tool calling to provide **memory tools** that give models explicit agency over memory operations (search, learn, recall, mark dead ends).

---

## Motivation

### Relationship to Existing Memory Architecture

RFC-014 **extends** (does not replace) the existing memory type hierarchy in `memory.py`:

| Existing Type | RFC-014 Extension | Relationship |
|---------------|-------------------|--------------|
| `WorkingMemory` | Unchanged | Hot tier turns, direct access |
| `LongTermMemory` | + `ContentFacets.verification_state` | Learnings gain trust metadata |
| `EpisodicMemory` | + `ConceptGraph` edges | Dead ends tracked via `CONTRADICTS` |
| `SemanticMemory` | + `SpatialContext` | Indexed chunks gain position awareness |
| `ProceduralMemory` | + `ContentFacets.diataxis_type` | Lens heuristics tagged by content type |

**Migration path**: Existing sessions continue working. New topologies are opt-in and lazily populated when content is re-indexed or new content added.

---

### RFC-013 Limitations

RFC-013 introduced hierarchical memory with progressive compression:

```
HOT (20 turns) → WARM (100 turns) → COLD (archive)
```

This works well for **linear conversation history**, but fails for:

1. **Documents with structure** — Headers create semantic boundaries that arbitrary turn-counts ignore
2. **Codebases** — Position in module/class/function hierarchy carries meaning
3. **Conceptual frameworks** — Ideas span multiple dimensions (Diataxis type, audience, verification state)
4. **Related concepts** — Relationships beyond parent-child (contradictions, elaborations, dependencies)

### Evidence: Real-World Retrieval Failures

When querying "What are the limitations of the CTF format?":

- **RFC-013 approach**: Searches all chunks by embedding similarity
- **Problem**: Returns chunks about CTF from `## Design` section with equal weight as chunks from `## Limitations` section
- **Structural approach**: Knows that content *under* `## Limitations` heading is definitionally about limitations

When querying "Does anything contradict our earlier caching decision?":

- **RFC-013 approach**: Cannot answer — no relationship tracking
- **Topological approach**: Traverses `CONTRADICTS` edges in concept graph

---

## Design

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-TOPOLOGY MEMORY SYSTEM                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         MEMORY NODE                                   │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │  │ Content │  │Temporal │  │ Spatial │  │Structural│  │ Facets  │    │  │
│  │  │ (text)  │  │(RFC-013)│  │(position)│  │(doc tree)│  │(tags)   │    │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      CONCEPT GRAPH (Topological)                      │  │
│  │                                                                        │  │
│  │    [Node A] ──ELABORATES──▶ [Node B]                                  │  │
│  │        │                        │                                      │  │
│  │        │                        │                                      │  │
│  │   CONTRADICTS              DEPENDS_ON                                  │  │
│  │        │                        │                                      │  │
│  │        ▼                        ▼                                      │  │
│  │    [Node C] ◀──SUPERSEDES── [Node D]                                  │  │
│  │                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      RETRIEVAL STRATEGIES                             │  │
│  │                                                                        │  │
│  │  • Temporal: "Recent context about X"                                 │  │
│  │  • Spatial: "X in the config module"                                  │  │
│  │  • Structural: "X under the Limitations heading"                      │  │
│  │  • Topological: "What contradicts X?"                                 │  │
│  │  • Multi-faceted: "Tutorial content for novices about X"              │  │
│  │  • Hybrid: Combine any of the above                                   │  │
│  │                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Complexity Analysis (Big O)

### Summary Table

| Operation | Time Complexity | Space Complexity | Notes |
|-----------|-----------------|------------------|-------|
| **Spatial Memory** ||||
| `spatial_match()` | O(1) | O(1) | Per-node matching |
| `query_spatial()` | O(n) | O(k) | n=nodes, k=results |
| **Topological Memory** ||||
| `add_edge()` | O(1) amortized | O(1) | Dict/list append |
| `get_outgoing()`/`get_incoming()` | O(e) | O(e) | e=edges for node |
| `find_dependencies()` | O(V + E) | O(V) | BFS traversal |
| `find_path()` | O(V + E) | O(V) | BFS shortest path |
| `get_neighborhood(depth=k)` | O(d^k) | O(d^k) | d=avg degree |
| **Structural Memory** ||||
| `parse_document()` | O(L) | O(S) | L=lines, S=sections |
| `get_ancestors()` | O(h) | O(h) | h=tree height |
| `find_by_title()` | O(S) | O(m) | S=sections, m=matches |
| `iter_depth_first()` | O(S) | O(h) | Stack depth=height |
| **Multi-Faceted Memory** ||||
| `FacetedIndex.add()` | O(f) | O(f) | f=facet dimensions |
| `FacetedIndex.query()` | O(min(|A|,|B|,...)) | O(r) | Inverted index intersection |
| **Unified Store** ||||
| `query()` hybrid | O(n) worst | O(r) | Falls back to scan |
| `save()`/`load()` | O(n) | O(n) | Serialization |

### Best/Worst Case Scenarios

#### Best Case: Inverted Index Hit (Multi-Faceted Query)

```python
# Query: "All TUTORIAL content for NOVICE persona"
query = FacetQuery(diataxis_type=DiataxisType.TUTORIAL, persona=PersonaType.NOVICE)
```

**Complexity**: O(min(|tutorials|, |novice_content|))

The inverted indexes (`_by_diataxis`, `_by_persona`) allow set intersection without scanning all nodes. If 50 tutorials exist and 30 novice items, we intersect two small sets instead of scanning 10,000 nodes.

#### Worst Case: Full Scan (Hybrid Query with Text)

```python
# Query: text search without spatial/facet filters
results = store.query(text_query="caching", limit=10)
```

**Complexity**: O(n) where n = total nodes

Without inverted index support for text queries (requires embedding search), we must scan all nodes. **Mitigation**: Use `InMemoryIndex` for embedding-based retrieval → O(n) but vectorized with NumPy.

#### Graph Traversal Scaling

```python
# Find all transitive dependencies
deps = graph.find_dependencies(node_id)
```

**Complexity**: O(V + E) for BFS

For a graph with 1,000 nodes and 5,000 edges, this is ~6,000 operations. Acceptable for interactive use.

**Danger zone**: `get_neighborhood(depth=5)` with high-degree nodes.
- If average degree d=20, depth k=5: O(20^5) = O(3.2M) operations
- **Mitigation**: Cap `max_depth=3` in config, add visited set pruning.

### Space Complexity Notes

| Component | Expected Size | Storage |
|-----------|---------------|---------|
| `MemoryNode` | ~2KB avg | JSON on disk |
| `ConceptEdge` | ~200 bytes | In graph.json |
| `embedding` | 1536 floats = 6KB | NumPy array |
| `FacetedIndex` | O(n × f) pointers | In-memory sets |

**Memory budget for 10,000 nodes**:
- Nodes: ~20MB
- Embeddings: ~60MB (if using 1536-dim)
- Graph edges (5 per node avg): ~10MB
- Facet indexes: ~5MB
- **Total**: ~95MB — fits comfortably in memory

---

## 1. Spatial Memory

Spatial memory tracks **where** content exists — in documents, codebases, or other positional systems.

### 1.1 Data Model

```python
# src/sunwell/headspace/spatial.py

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Future type imports


class PositionType(Enum):
    """Type of positional context."""
    
    DOCUMENT = "document"     # Markdown, RST, etc.
    CODE = "code"             # Source code
    CONVERSATION = "conversation"  # Chat turn
    EXTERNAL = "external"     # URL, API response, etc.


@dataclass(frozen=True, slots=True)
class SpatialContext:
    """Position metadata for spatial-aware retrieval.
    
    Answers: "Where is this information located?"
    """
    
    position_type: PositionType
    
    # === Document Position ===
    file_path: str | None = None
    """Relative path to source file."""
    
    line_range: tuple[int, int] = (0, 0)
    """Line numbers (1-indexed, inclusive)."""
    
    char_range: tuple[int, int] = (0, 0)
    """Character offsets within file."""
    
    # === Hierarchical Position ===
    section_path: tuple[str, ...] = ()
    """Path through document headings: ("Architecture", "Data Flow", "Caching")."""
    
    heading_level: int = 0
    """Heading depth: H1=1, H2=2, etc. 0 = not under a heading."""
    
    # === Code Position ===
    module_path: str | None = None
    """Python module path: sunwell.headspace.spatial"""
    
    class_name: str | None = None
    """Containing class name."""
    
    function_name: str | None = None
    """Containing function/method name."""
    
    scope_depth: int = 0
    """Nesting level (0 = module level, 1 = class level, etc.)."""
    
    # === External Position ===
    url: str | None = None
    """Source URL for external content."""
    
    anchor: str | None = None
    """URL fragment/anchor."""
    
    def __str__(self) -> str:
        """Human-readable position string."""
        if self.position_type == PositionType.DOCUMENT:
            path = " > ".join(self.section_path) if self.section_path else ""
            return f"{self.file_path}:{self.line_range[0]} [{path}]"
        elif self.position_type == PositionType.CODE:
            parts = [self.module_path, self.class_name, self.function_name]
            return ".".join(p for p in parts if p)
        elif self.position_type == PositionType.EXTERNAL:
            return f"{self.url}#{self.anchor}" if self.anchor else self.url or ""
        return f"turn:{self.line_range[0]}"


@dataclass(frozen=True, slots=True)
class SpatialQuery:
    """Query constraints for spatial retrieval."""
    
    # File constraints
    file_pattern: str | None = None
    """Glob pattern for file paths: "docs/*.md", "src/sunwell/**"."""
    
    # Section constraints
    section_contains: str | None = None
    """Section path must contain this string: "Limitations"."""
    
    heading_level_max: int | None = None
    """Only content under headings at this level or deeper."""
    
    # Code constraints
    module_prefix: str | None = None
    """Module must start with: "sunwell.headspace"."""
    
    in_class: str | None = None
    """Must be within this class."""
    
    in_function: str | None = None
    """Must be within this function."""
    
    # Line constraints
    line_range: tuple[int, int] | None = None
    """Restrict to line range."""


def spatial_match(context: SpatialContext, query: SpatialQuery) -> float:
    """Score how well a spatial context matches a query.
    
    Returns: 0.0 (no match) to 1.0 (perfect match).
    
    Complexity: O(1) per node — constant-time field comparisons.
    """
    if not query:
        return 1.0  # No constraints = everything matches
    
    score = 1.0
    checks = 0
    
    # File pattern — O(m) where m is path length
    if query.file_pattern and context.file_path:
        if fnmatch.fnmatch(context.file_path, query.file_pattern):
            checks += 1
        else:
            return 0.0  # Hard filter
    
    # Section contains
    if query.section_contains and context.section_path:
        section_str = " > ".join(context.section_path).lower()
        if query.section_contains.lower() in section_str:
            checks += 1
        else:
            return 0.0  # Hard filter
    
    # Heading level
    if query.heading_level_max is not None:
        if context.heading_level > 0 and context.heading_level <= query.heading_level_max:
            checks += 1
        elif context.heading_level == 0:
            pass  # No penalty for unheaded content
        else:
            score *= 0.5  # Soft penalty
    
    # Module prefix
    if query.module_prefix and context.module_path:
        if context.module_path.startswith(query.module_prefix):
            checks += 1
        else:
            return 0.0  # Hard filter
    
    # Class constraint
    if query.in_class:
        if context.class_name == query.in_class:
            checks += 1
        else:
            return 0.0
    
    # Function constraint
    if query.in_function:
        if context.function_name == query.in_function:
            checks += 1
        else:
            return 0.0
    
    return score
```

### 1.2 Spatial Extraction

```python
# src/sunwell/headspace/spatial_extractor.py

import re
from pathlib import Path

from sunwell.headspace.spatial import SpatialContext, PositionType


class SpatialExtractor:
    """Extract spatial context from content sources."""
    
    @staticmethod
    def from_markdown(
        file_path: str,
        content: str,
        line_start: int = 1,
    ) -> list[tuple[str, SpatialContext]]:
        """Extract chunks with spatial context from markdown.
        
        Returns list of (chunk_text, spatial_context) pairs.
        """
        chunks = []
        current_section_path: list[str] = []
        current_level = 0
        current_chunk_lines: list[str] = []
        chunk_start_line = line_start
        
        lines = content.split("\n")
        
        for i, line in enumerate(lines, start=line_start):
            # Detect heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Save previous chunk
                if current_chunk_lines:
                    chunk_text = "\n".join(current_chunk_lines)
                    if chunk_text.strip():
                        ctx = SpatialContext(
                            position_type=PositionType.DOCUMENT,
                            file_path=file_path,
                            line_range=(chunk_start_line, i - 1),
                            section_path=tuple(current_section_path),
                            heading_level=current_level,
                        )
                        chunks.append((chunk_text, ctx))
                
                # Update section path
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Pop sections at same or higher level
                while len(current_section_path) >= level:
                    current_section_path.pop()
                
                current_section_path.append(title)
                current_level = level
                current_chunk_lines = [line]
                chunk_start_line = i
            else:
                current_chunk_lines.append(line)
        
        # Don't forget last chunk
        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if chunk_text.strip():
                ctx = SpatialContext(
                    position_type=PositionType.DOCUMENT,
                    file_path=file_path,
                    line_range=(chunk_start_line, len(lines)),
                    section_path=tuple(current_section_path),
                    heading_level=current_level,
                )
                chunks.append((chunk_text, ctx))
        
        return chunks
    
    @staticmethod
    def from_python(
        file_path: str,
        content: str,
    ) -> list[tuple[str, SpatialContext]]:
        """Extract chunks with spatial context from Python code.
        
        Uses AST to identify module/class/function boundaries.
        """
        import ast
        
        chunks = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to treating entire file as one chunk
            return [(content, SpatialContext(
                position_type=PositionType.CODE,
                file_path=file_path,
                module_path=file_path.replace("/", ".").replace(".py", ""),
            ))]
        
        module_path = file_path.replace("/", ".").replace(".py", "")
        if module_path.startswith("src."):
            module_path = module_path[4:]
        
        def extract_node(
            node: ast.AST,
            class_name: str | None = None,
            depth: int = 0,
        ) -> None:
            """Recursively extract code chunks."""
            
            if isinstance(node, ast.ClassDef):
                # Extract class
                chunk_text = ast.get_source_segment(content, node)
                if chunk_text:
                    ctx = SpatialContext(
                        position_type=PositionType.CODE,
                        file_path=file_path,
                        line_range=(node.lineno, node.end_lineno or node.lineno),
                        module_path=module_path,
                        class_name=node.name,
                        scope_depth=depth,
                    )
                    chunks.append((chunk_text, ctx))
                
                # Recurse into class body
                for child in node.body:
                    extract_node(child, class_name=node.name, depth=depth + 1)
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Extract function
                chunk_text = ast.get_source_segment(content, node)
                if chunk_text:
                    ctx = SpatialContext(
                        position_type=PositionType.CODE,
                        file_path=file_path,
                        line_range=(node.lineno, node.end_lineno or node.lineno),
                        module_path=module_path,
                        class_name=class_name,
                        function_name=node.name,
                        scope_depth=depth,
                    )
                    chunks.append((chunk_text, ctx))
        
        # Extract top-level items
        for node in ast.iter_child_nodes(tree):
            extract_node(node, depth=0)
        
        return chunks
```

---

## 2. Topological Memory (Concept Graph)

Topological memory models **relationships** between concepts as a typed graph.

### 2.1 Relationship Types

```python
# src/sunwell/headspace/topology.py

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterator


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
    def from_dict(cls, data: dict) -> "ConceptGraph":
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
```

### 2.2 Auto-Extraction of Relationships

```python
# src/sunwell/headspace/topology_extractor.py

from sunwell.headspace.topology import RelationType, ConceptEdge
from sunwell.models.protocol import ModelProtocol


class TopologyExtractor:
    """Extract concept relationships from content using LLM or heuristics."""
    
    def __init__(self, model: ModelProtocol | None = None):
        self.model = model
    
    async def extract_relationships(
        self,
        source_id: str,
        source_text: str,
        candidate_ids: list[str],
        candidate_texts: list[str],
    ) -> list[ConceptEdge]:
        """Identify relationships between a source and candidate chunks.
        
        Uses LLM to detect: elaboration, contradiction, dependency, etc.
        """
        if not self.model or not candidate_ids:
            return []
        
        # Format candidates
        candidates_formatted = "\n\n".join(
            f"[{cid}]: {text[:500]}"
            for cid, text in zip(candidate_ids, candidate_texts)
        )
        
        prompt = f"""Analyze relationships between the SOURCE chunk and CANDIDATE chunks.

SOURCE [{source_id}]:
{source_text[:1000]}

CANDIDATES:
{candidates_formatted}

For each meaningful relationship, output one line in format:
RELATION_TYPE: [candidate_id] - brief reason

Valid RELATION_TYPEs:
- ELABORATES: Source provides more detail about candidate
- SUMMARIZES: Source summarizes candidate
- CONTRADICTS: Source conflicts with candidate
- SUPPORTS: Source provides evidence for candidate
- DEPENDS_ON: Source requires candidate to be understood
- SUPERSEDES: Source replaces/updates candidate
- RELATES_TO: Source is topically related to candidate

Only output strong, clear relationships. Skip weak or uncertain ones.

Relationships:"""
        
        result = await self.model.generate(prompt)
        
        # Parse response
        edges = []
        for line in result.text.strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            
            try:
                relation_part, rest = line.split(":", 1)
                relation_type = RelationType(relation_part.strip().lower())
                
                # Extract candidate ID (in brackets)
                import re
                match = re.search(r'\[([^\]]+)\]', rest)
                if match:
                    target_id = match.group(1)
                    reason = rest.replace(f"[{target_id}]", "").strip(" -")
                    
                    if target_id in candidate_ids:
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation=relation_type,
                            confidence=0.8,  # LLM-extracted, needs confirmation
                            evidence=reason,
                            auto_extracted=True,
                        ))
            except (ValueError, KeyError):
                continue  # Skip malformed lines
        
        return edges
    
    def extract_heuristic_relationships(
        self,
        source_id: str,
        source_text: str,
        candidate_ids: list[str],
        candidate_texts: list[str],
    ) -> list[ConceptEdge]:
        """Heuristic relationship detection without LLM.
        
        Detects:
        - Explicit references ("as mentioned in", "see also", "cf.")
        - Contradiction signals ("however", "but", "unlike", "in contrast")
        - Dependency signals ("requires", "depends on", "building on")
        """
        import re
        edges = []
        
        source_lower = source_text.lower()
        
        for cid, ctext in zip(candidate_ids, candidate_texts):
            # Check for explicit reference
            if cid.lower() in source_lower:
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.RELATES_TO,
                    confidence=0.9,
                    evidence=f"Explicit reference to {cid}",
                    auto_extracted=True,
                ))
            
            # Check for contradiction signals near candidate mentions
            contradiction_patterns = [
                r'\bhowever\b',
                r'\bbut\b',
                r'\bunlike\b',
                r'\bin contrast\b',
                r'\bcontradicts?\b',
            ]
            for pattern in contradiction_patterns:
                if re.search(pattern, source_lower):
                    # Check if candidate topic is nearby
                    candidate_keywords = set(ctext.lower().split()[:10])
                    source_words = set(source_lower.split())
                    overlap = len(candidate_keywords & source_words)
                    if overlap > 3:  # Significant topic overlap
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=cid,
                            relation=RelationType.CONTRADICTS,
                            confidence=0.5,  # Low confidence, needs review
                            evidence=f"Contradiction signal + topic overlap",
                            auto_extracted=True,
                        ))
                        break
        
        return edges
```

---

## 3. Structural Memory

Structural memory understands **document hierarchy** — headers, sections, nesting.

### 3.1 Document Structure Model

```python
# src/sunwell/headspace/structural.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator


class SectionType(Enum):
    """Semantic types of document sections."""
    
    # Diataxis-aligned
    OVERVIEW = "overview"
    TUTORIAL = "tutorial"
    HOWTO = "howto"
    REFERENCE = "reference"
    EXPLANATION = "explanation"
    
    # Common patterns
    INTRODUCTION = "introduction"
    INSTALLATION = "installation"
    QUICKSTART = "quickstart"
    CONFIGURATION = "configuration"
    API = "api"
    EXAMPLES = "examples"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    LIMITATIONS = "limitations"
    CHANGELOG = "changelog"
    
    # Meta
    UNKNOWN = "unknown"


@dataclass
class DocumentSection:
    """A section in a document hierarchy.
    
    Represents the tree structure:
    
    # RFC-014 (level=1)
    ## Summary (level=2)
    ## Design (level=2)
    ### Architecture (level=3)
    ### Components (level=3)
    """
    
    id: str
    """Unique identifier for this section."""
    
    title: str
    """Section heading text."""
    
    level: int
    """Heading level (1-6 for H1-H6)."""
    
    section_type: SectionType = SectionType.UNKNOWN
    """Semantic type of section (auto-detected or explicit)."""
    
    content: str = ""
    """Text content of this section (excluding subsections)."""
    
    line_start: int = 0
    """Starting line number."""
    
    line_end: int = 0
    """Ending line number."""
    
    # Hierarchy
    parent_id: str | None = None
    """ID of parent section."""
    
    child_ids: list[str] = field(default_factory=list)
    """IDs of child sections."""
    
    # Metadata
    word_count: int = 0
    """Word count of content (excluding children)."""
    
    has_code: bool = False
    """Contains code blocks."""
    
    has_admonitions: bool = False
    """Contains notes/warnings/etc."""


@dataclass
class DocumentTree:
    """Hierarchical document structure for structural retrieval.
    
    Enables queries like:
    - "Content under 'Limitations' section"
    - "All H2 sections"
    - "Siblings of section X"
    """
    
    file_path: str
    """Source file."""
    
    root_id: str = ""
    """ID of root (H1) section."""
    
    _sections: dict[str, DocumentSection] = field(default_factory=dict)
    """All sections by ID."""
    
    def add_section(self, section: DocumentSection) -> None:
        """Add a section to the tree."""
        self._sections[section.id] = section
        
        if section.level == 1 and not self.root_id:
            self.root_id = section.id
    
    def get_section(self, section_id: str) -> DocumentSection | None:
        """Get section by ID."""
        return self._sections.get(section_id)
    
    def get_children(self, section_id: str) -> list[DocumentSection]:
        """Get direct children of a section."""
        section = self._sections.get(section_id)
        if not section:
            return []
        return [self._sections[cid] for cid in section.child_ids if cid in self._sections]
    
    def get_ancestors(self, section_id: str) -> list[DocumentSection]:
        """Get all ancestors from section to root."""
        ancestors = []
        current = self._sections.get(section_id)
        
        while current and current.parent_id:
            parent = self._sections.get(current.parent_id)
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break
        
        return ancestors
    
    def get_siblings(self, section_id: str) -> list[DocumentSection]:
        """Get sibling sections (same parent, same level)."""
        section = self._sections.get(section_id)
        if not section or not section.parent_id:
            return []
        
        parent = self._sections.get(section.parent_id)
        if not parent:
            return []
        
        return [
            self._sections[cid]
            for cid in parent.child_ids
            if cid != section_id and cid in self._sections
        ]
    
    def get_section_path(self, section_id: str) -> list[str]:
        """Get path from root to section as list of titles."""
        ancestors = self.get_ancestors(section_id)
        section = self._sections.get(section_id)
        
        path = [a.title for a in reversed(ancestors)]
        if section:
            path.append(section.title)
        
        return path
    
    def find_by_title(self, title: str, fuzzy: bool = False) -> list[DocumentSection]:
        """Find sections by title."""
        results = []
        title_lower = title.lower()
        
        for section in self._sections.values():
            if fuzzy:
                if title_lower in section.title.lower():
                    results.append(section)
            else:
                if section.title.lower() == title_lower:
                    results.append(section)
        
        return results
    
    def find_by_type(self, section_type: SectionType) -> list[DocumentSection]:
        """Find all sections of a given type."""
        return [s for s in self._sections.values() if s.section_type == section_type]
    
    def find_by_level(self, level: int) -> list[DocumentSection]:
        """Find all sections at a given heading level."""
        return [s for s in self._sections.values() if s.level == level]
    
    def iter_depth_first(self) -> Iterator[DocumentSection]:
        """Iterate sections in depth-first order."""
        if not self.root_id:
            return
        
        def visit(section_id: str) -> Iterator[DocumentSection]:
            section = self._sections.get(section_id)
            if section:
                yield section
                for child_id in section.child_ids:
                    yield from visit(child_id)
        
        yield from visit(self.root_id)


def infer_section_type(title: str) -> SectionType:
    """Infer semantic type from section title."""
    title_lower = title.lower()
    
    patterns = {
        SectionType.OVERVIEW: ["overview", "introduction", "about"],
        SectionType.INSTALLATION: ["install", "setup", "getting started"],
        SectionType.QUICKSTART: ["quickstart", "quick start", "getting started"],
        SectionType.CONFIGURATION: ["config", "configuration", "settings", "options"],
        SectionType.API: ["api", "reference", "specification"],
        SectionType.EXAMPLES: ["example", "examples", "usage", "demo"],
        SectionType.TROUBLESHOOTING: ["troubleshoot", "debug", "common issues", "faq"],
        SectionType.LIMITATIONS: ["limit", "caveat", "known issues", "restrictions"],
        SectionType.CHANGELOG: ["changelog", "history", "release notes", "what's new"],
    }
    
    for section_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in title_lower:
                return section_type
    
    return SectionType.UNKNOWN
```

### 3.2 Structure-Aware Chunking

```python
# src/sunwell/headspace/structural_chunker.py

from sunwell.headspace.structural import (
    DocumentTree, DocumentSection, SectionType, infer_section_type
)
from sunwell.headspace.chunks import Chunk, ChunkType
from sunwell.headspace.spatial import SpatialContext, PositionType
import re
import hashlib


class StructuralChunker:
    """Chunk documents by semantic structure, not arbitrary boundaries.
    
    Key insight: A section under "## Limitations" is semantically different
    from identical text under "## Features". Structure carries meaning.
    """
    
    def __init__(
        self,
        min_chunk_size: int = 100,   # Min chars per chunk
        max_chunk_size: int = 4000,  # Max chars per chunk
        preserve_code_blocks: bool = True,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.preserve_code_blocks = preserve_code_blocks
    
    def parse_document(self, file_path: str, content: str) -> DocumentTree:
        """Parse markdown into a document tree."""
        tree = DocumentTree(file_path=file_path)
        
        lines = content.split("\n")
        section_stack: list[DocumentSection] = []
        current_content_lines: list[str] = []
        current_line_start = 1
        
        for i, line in enumerate(lines, start=1):
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Finalize previous section's content
                if section_stack:
                    section_stack[-1].content = "\n".join(current_content_lines)
                    section_stack[-1].line_end = i - 1
                    section_stack[-1].word_count = len(section_stack[-1].content.split())
                    section_stack[-1].has_code = "```" in section_stack[-1].content
                
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                section_id = hashlib.md5(f"{file_path}:{i}:{title}".encode()).hexdigest()[:12]
                
                section = DocumentSection(
                    id=section_id,
                    title=title,
                    level=level,
                    section_type=infer_section_type(title),
                    line_start=i,
                )
                
                # Find parent (first section with lower level)
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()
                
                if section_stack:
                    section.parent_id = section_stack[-1].id
                    section_stack[-1].child_ids.append(section_id)
                
                tree.add_section(section)
                section_stack.append(section)
                current_content_lines = []
                current_line_start = i + 1
            else:
                current_content_lines.append(line)
        
        # Finalize last section
        if section_stack:
            section_stack[-1].content = "\n".join(current_content_lines)
            section_stack[-1].line_end = len(lines)
            section_stack[-1].word_count = len(section_stack[-1].content.split())
            section_stack[-1].has_code = "```" in section_stack[-1].content
        
        return tree
    
    def chunk_document(
        self,
        file_path: str,
        content: str,
    ) -> list[tuple[Chunk, SpatialContext, DocumentSection]]:
        """Chunk document by structure, returning enriched chunks.
        
        Returns list of (Chunk, SpatialContext, DocumentSection) tuples.
        """
        tree = self.parse_document(file_path, content)
        chunks = []
        
        for section in tree.iter_depth_first():
            if not section.content.strip():
                continue
            
            # Build spatial context
            section_path = tuple(tree.get_section_path(section.id))
            spatial = SpatialContext(
                position_type=PositionType.DOCUMENT,
                file_path=file_path,
                line_range=(section.line_start, section.line_end),
                section_path=section_path,
                heading_level=section.level,
            )
            
            # Check if section needs splitting
            if len(section.content) > self.max_chunk_size:
                sub_chunks = self._split_large_section(section, spatial, tree)
                chunks.extend(sub_chunks)
            else:
                chunk = Chunk(
                    id=f"struct_{section.id}",
                    chunk_type=ChunkType.MICRO,
                    turn_range=(section.line_start, section.line_end),
                    summary=f"{section_path[-1] if section_path else 'Untitled'}: {section.content[:100]}...",
                    token_count=int(section.word_count * 1.3),
                    themes=(section.section_type.value,) if section.section_type != SectionType.UNKNOWN else (),
                )
                chunks.append((chunk, spatial, section))
        
        return chunks
    
    def _split_large_section(
        self,
        section: DocumentSection,
        spatial: SpatialContext,
        tree: DocumentTree,
    ) -> list[tuple[Chunk, SpatialContext, DocumentSection]]:
        """Split a large section into smaller chunks.
        
        Respects code blocks and paragraph boundaries.
        """
        chunks = []
        content = section.content
        
        if self.preserve_code_blocks:
            # Split around code blocks
            parts = re.split(r'(```[\s\S]*?```)', content)
        else:
            parts = [content]
        
        current_chunk = ""
        chunk_idx = 0
        
        for part in parts:
            is_code_block = part.startswith("```")
            
            if is_code_block:
                # Code block: keep together if under limit, else truncate
                if len(part) <= self.max_chunk_size:
                    if len(current_chunk) + len(part) > self.max_chunk_size:
                        # Save current chunk first
                        if current_chunk.strip():
                            chunks.append(self._make_chunk(
                                section, spatial, tree, current_chunk, chunk_idx
                            ))
                            chunk_idx += 1
                        current_chunk = part
                    else:
                        current_chunk += part
                else:
                    # Very large code block: save as-is with truncation note
                    if current_chunk.strip():
                        chunks.append(self._make_chunk(
                            section, spatial, tree, current_chunk, chunk_idx
                        ))
                        chunk_idx += 1
                    truncated = part[:self.max_chunk_size - 50] + "\n... [truncated]\n```"
                    chunks.append(self._make_chunk(
                        section, spatial, tree, truncated, chunk_idx
                    ))
                    chunk_idx += 1
                    current_chunk = ""
            else:
                # Regular text: split by paragraphs
                paragraphs = part.split("\n\n")
                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                        if current_chunk.strip():
                            chunks.append(self._make_chunk(
                                section, spatial, tree, current_chunk, chunk_idx
                            ))
                            chunk_idx += 1
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para
        
        # Don't forget last chunk
        if current_chunk.strip():
            chunks.append(self._make_chunk(
                section, spatial, tree, current_chunk, chunk_idx
            ))
        
        return chunks
    
    def _make_chunk(
        self,
        section: DocumentSection,
        spatial: SpatialContext,
        tree: DocumentTree,
        content: str,
        idx: int,
    ) -> tuple[Chunk, SpatialContext, DocumentSection]:
        """Create a chunk tuple."""
        section_path = tree.get_section_path(section.id)
        
        chunk = Chunk(
            id=f"struct_{section.id}_{idx}",
            chunk_type=ChunkType.MICRO,
            turn_range=(section.line_start, section.line_end),
            summary=f"{section_path[-1] if section_path else 'Untitled'} (part {idx+1}): {content[:80]}...",
            token_count=int(len(content.split()) * 1.3),
            themes=(section.section_type.value,) if section.section_type != SectionType.UNKNOWN else (),
        )
        
        return (chunk, spatial, section)
```

---

## 4. Multi-Faceted Memory

Multi-faceted memory enables **cross-dimensional tagging** for retrieval across multiple axes simultaneously.

### 4.1 Facet System

```python
# src/sunwell/headspace/facets.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiataxisType(Enum):
    """Diataxis documentation types."""
    TUTORIAL = "tutorial"
    HOWTO = "howto"
    REFERENCE = "reference"
    EXPLANATION = "explanation"


class PersonaType(Enum):
    """Target audience personas."""
    NOVICE = "novice"           # New to the tool
    PRAGMATIST = "pragmatist"   # Just wants code
    SKEPTIC = "skeptic"         # Needs convincing
    EXPERT = "expert"           # Advanced user


class VerificationState(Enum):
    """Verification status of content."""
    UNVERIFIED = "unverified"   # Not yet checked
    VERIFIED = "verified"       # Confirmed accurate
    DISPUTED = "disputed"       # Known issues
    OUTDATED = "outdated"       # Needs update


class ConfidenceLevel(Enum):
    """Confidence in the content."""
    HIGH = "high"         # 90-100%
    MODERATE = "moderate" # 70-89%
    LOW = "low"           # 50-69%
    UNCERTAIN = "uncertain"  # <50%


@dataclass(frozen=True, slots=True)
class ContentFacets:
    """Multi-dimensional tags for cross-axis retrieval.
    
    Enables queries like:
    - "Tutorial content for novices" (diataxis + persona)
    - "Unverified reference content" (verification + diataxis)
    - "High-confidence CLI documentation" (confidence + domain)
    """
    
    # Diataxis
    diataxis_type: DiataxisType | None = None
    """Content type per Diataxis framework."""
    
    # Audience
    primary_persona: PersonaType | None = None
    """Primary target audience."""
    
    secondary_personas: tuple[PersonaType, ...] = ()
    """Additional relevant audiences."""
    
    # Trust
    verification_state: VerificationState = VerificationState.UNVERIFIED
    """Verification status."""
    
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    """Confidence in accuracy."""
    
    # Domain
    domain_tags: tuple[str, ...] = ()
    """Domain/topic tags: ("cli", "api", "config", "security")."""
    
    # Temporal
    is_time_sensitive: bool = False
    """Content may become outdated."""
    
    last_verified: str | None = None
    """ISO timestamp of last verification."""
    
    # Source
    source_type: str | None = None
    """Where this came from: "code", "docs", "conversation", "external"."""
    
    source_authority: float = 1.0
    """Authority of source (0.0-1.0). Code = 1.0, docs = 0.9, user = 0.7."""
    
    def matches(self, query: "FacetQuery") -> float:
        """Score how well facets match a query.
        
        Returns 0.0 (no match) to 1.0 (perfect match).
        """
        if not query.has_constraints():
            return 1.0
        
        score = 0.0
        checks = 0
        
        # Diataxis match
        if query.diataxis_type is not None:
            checks += 1
            if self.diataxis_type == query.diataxis_type:
                score += 1.0
        
        # Persona match
        if query.persona is not None:
            checks += 1
            if self.primary_persona == query.persona:
                score += 1.0
            elif query.persona in self.secondary_personas:
                score += 0.7
        
        # Verification match
        if query.verification_states:
            checks += 1
            if self.verification_state in query.verification_states:
                score += 1.0
        
        # Confidence match
        if query.min_confidence is not None:
            checks += 1
            confidence_order = [
                ConfidenceLevel.UNCERTAIN,
                ConfidenceLevel.LOW,
                ConfidenceLevel.MODERATE,
                ConfidenceLevel.HIGH,
            ]
            if confidence_order.index(self.confidence) >= confidence_order.index(query.min_confidence):
                score += 1.0
        
        # Domain match
        if query.domain_tags:
            checks += 1
            overlap = len(set(self.domain_tags) & set(query.domain_tags))
            if overlap > 0:
                score += overlap / len(query.domain_tags)
        
        return score / checks if checks > 0 else 1.0


@dataclass
class FacetQuery:
    """Query for multi-faceted retrieval."""
    
    # Diataxis filter
    diataxis_type: DiataxisType | None = None
    
    # Persona filter
    persona: PersonaType | None = None
    
    # Verification filter
    verification_states: tuple[VerificationState, ...] = ()
    
    # Confidence filter
    min_confidence: ConfidenceLevel | None = None
    
    # Domain filter
    domain_tags: tuple[str, ...] = ()
    """All tags must match (AND logic)."""
    
    # Source filter
    source_types: tuple[str, ...] = ()
    
    def has_constraints(self) -> bool:
        """Check if query has any constraints."""
        return any([
            self.diataxis_type,
            self.persona,
            self.verification_states,
            self.min_confidence,
            self.domain_tags,
            self.source_types,
        ])


@dataclass
class FacetedIndex:
    """Index for efficient multi-faceted retrieval.
    
    Maintains inverted indexes for each facet dimension.
    """
    
    # Inverted indexes: facet_value -> set of node IDs
    _by_diataxis: dict[DiataxisType, set[str]] = field(default_factory=dict)
    _by_persona: dict[PersonaType, set[str]] = field(default_factory=dict)
    _by_verification: dict[VerificationState, set[str]] = field(default_factory=dict)
    _by_confidence: dict[ConfidenceLevel, set[str]] = field(default_factory=dict)
    _by_domain: dict[str, set[str]] = field(default_factory=dict)
    
    # Forward index: node ID -> facets
    _facets: dict[str, ContentFacets] = field(default_factory=dict)
    
    def add(self, node_id: str, facets: ContentFacets) -> None:
        """Add node to index."""
        self._facets[node_id] = facets
        
        # Update inverted indexes
        if facets.diataxis_type:
            if facets.diataxis_type not in self._by_diataxis:
                self._by_diataxis[facets.diataxis_type] = set()
            self._by_diataxis[facets.diataxis_type].add(node_id)
        
        if facets.primary_persona:
            if facets.primary_persona not in self._by_persona:
                self._by_persona[facets.primary_persona] = set()
            self._by_persona[facets.primary_persona].add(node_id)
        
        for persona in facets.secondary_personas:
            if persona not in self._by_persona:
                self._by_persona[persona] = set()
            self._by_persona[persona].add(node_id)
        
        if facets.verification_state not in self._by_verification:
            self._by_verification[facets.verification_state] = set()
        self._by_verification[facets.verification_state].add(node_id)
        
        if facets.confidence not in self._by_confidence:
            self._by_confidence[facets.confidence] = set()
        self._by_confidence[facets.confidence].add(node_id)
        
        for tag in facets.domain_tags:
            if tag not in self._by_domain:
                self._by_domain[tag] = set()
            self._by_domain[tag].add(node_id)
    
    def query(self, query: FacetQuery) -> list[tuple[str, float]]:
        """Query index, returning (node_id, score) pairs.
        
        Uses inverted indexes for efficient filtering,
        then scores remaining candidates.
        """
        # Start with all nodes
        candidates: set[str] | None = None
        
        # Filter by diataxis
        if query.diataxis_type:
            matching = self._by_diataxis.get(query.diataxis_type, set())
            candidates = matching if candidates is None else candidates & matching
        
        # Filter by persona
        if query.persona:
            matching = self._by_persona.get(query.persona, set())
            candidates = matching if candidates is None else candidates & matching
        
        # Filter by verification
        if query.verification_states:
            matching = set()
            for state in query.verification_states:
                matching |= self._by_verification.get(state, set())
            candidates = matching if candidates is None else candidates & matching
        
        # Filter by confidence
        if query.min_confidence:
            confidence_order = [
                ConfidenceLevel.UNCERTAIN,
                ConfidenceLevel.LOW,
                ConfidenceLevel.MODERATE,
                ConfidenceLevel.HIGH,
            ]
            min_idx = confidence_order.index(query.min_confidence)
            matching = set()
            for level in confidence_order[min_idx:]:
                matching |= self._by_confidence.get(level, set())
            candidates = matching if candidates is None else candidates & matching
        
        # Filter by domain (AND logic)
        if query.domain_tags:
            matching = None
            for tag in query.domain_tags:
                tag_nodes = self._by_domain.get(tag, set())
                matching = tag_nodes if matching is None else matching & tag_nodes
            if matching:
                candidates = matching if candidates is None else candidates & matching
            else:
                candidates = set()
        
        # If no filters, return all
        if candidates is None:
            candidates = set(self._facets.keys())
        
        # Score candidates
        results = []
        for node_id in candidates:
            facets = self._facets.get(node_id)
            if facets:
                score = facets.matches(query)
                if score > 0:
                    results.append((node_id, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def get_facets(self, node_id: str) -> ContentFacets | None:
        """Get facets for a node."""
        return self._facets.get(node_id)
    
    def stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_nodes": len(self._facets),
            "by_diataxis": {k.value: len(v) for k, v in self._by_diataxis.items()},
            "by_persona": {k.value: len(v) for k, v in self._by_persona.items()},
            "by_verification": {k.value: len(v) for k, v in self._by_verification.items()},
            "by_confidence": {k.value: len(v) for k, v in self._by_confidence.items()},
            "domain_tags": {k: len(v) for k, v in self._by_domain.items()},
        }
```

### 4.2 Auto-Faceting

```python
# src/sunwell/headspace/facet_extractor.py

import re
from sunwell.headspace.facets import (
    ContentFacets, DiataxisType, PersonaType, VerificationState, ConfidenceLevel
)
from sunwell.headspace.structural import DocumentSection, SectionType


class FacetExtractor:
    """Extract facets from content using heuristics and patterns."""
    
    # Diataxis detection patterns
    DIATAXIS_PATTERNS = {
        DiataxisType.TUTORIAL: [
            r'\blearn\b', r'\bstep[- ]by[- ]step\b', r'\bwalkthrough\b',
            r'\bfollow along\b', r'\blet\'s\b', r'\byou will\b',
        ],
        DiataxisType.HOWTO: [
            r'\bhow to\b', r'\bguide\b', r'\bsolve\b', r'\bachieve\b',
            r'\baccomplish\b', r'\btask\b', r'\bgoal\b',
        ],
        DiataxisType.REFERENCE: [
            r'\bapi\b', r'\bspecification\b', r'\bschema\b', r'\bformat\b',
            r'\boptions?\b', r'\bparameters?\b', r'\bsyntax\b',
        ],
        DiataxisType.EXPLANATION: [
            r'\bwhy\b', r'\barchitecture\b', r'\bdesign\b', r'\bconcept\b',
            r'\bunderstand\b', r'\btheory\b', r'\bbackground\b',
        ],
    }
    
    # Persona detection patterns
    PERSONA_PATTERNS = {
        PersonaType.NOVICE: [
            r'\bbeginner\b', r'\bintroduction\b', r'\bbasic\b', r'\bfirst\b',
            r'\bsimple\b', r'\beasy\b', r'\bstarting\b',
        ],
        PersonaType.EXPERT: [
            r'\badvanced\b', r'\bexpert\b', r'\bprofessional\b', r'\bdeep dive\b',
            r'\barchitect\b', r'\boptimiz\b', r'\bperformance\b',
        ],
    }
    
    # Domain keywords
    DOMAIN_KEYWORDS = {
        "cli": [r'\bcommand[- ]line\b', r'\bcli\b', r'\bterminal\b', r'\bshell\b'],
        "api": [r'\bapi\b', r'\bendpoint\b', r'\brequest\b', r'\bresponse\b'],
        "config": [r'\bconfig\b', r'\bsettings?\b', r'\byaml\b', r'\bjson\b', r'\btoml\b'],
        "security": [r'\bsecurity\b', r'\bauth\b', r'\btoken\b', r'\bpermission\b'],
        "testing": [r'\btest\b', r'\bpytest\b', r'\bassert\b', r'\bmock\b'],
    }
    
    def extract_from_text(
        self,
        text: str,
        section: DocumentSection | None = None,
        source_type: str = "docs",
    ) -> ContentFacets:
        """Extract facets from text content."""
        text_lower = text.lower()
        
        # Detect Diataxis type
        diataxis_type = self._detect_diataxis(text_lower, section)
        
        # Detect persona
        persona = self._detect_persona(text_lower)
        
        # Detect domains
        domains = self._detect_domains(text_lower)
        
        # Infer confidence from indicators
        confidence = self._infer_confidence(text_lower)
        
        return ContentFacets(
            diataxis_type=diataxis_type,
            primary_persona=persona,
            verification_state=VerificationState.UNVERIFIED,
            confidence=confidence,
            domain_tags=tuple(domains),
            source_type=source_type,
            source_authority=0.9 if source_type == "docs" else 0.7,
        )
    
    def _detect_diataxis(
        self,
        text: str,
        section: DocumentSection | None,
    ) -> DiataxisType | None:
        """Detect Diataxis type from text and section."""
        # Check section type first (high confidence)
        if section:
            type_mapping = {
                SectionType.TUTORIAL: DiataxisType.TUTORIAL,
                SectionType.QUICKSTART: DiataxisType.TUTORIAL,
                SectionType.HOWTO: DiataxisType.HOWTO,
                SectionType.TROUBLESHOOTING: DiataxisType.HOWTO,
                SectionType.REFERENCE: DiataxisType.REFERENCE,
                SectionType.API: DiataxisType.REFERENCE,
                SectionType.EXPLANATION: DiataxisType.EXPLANATION,
                SectionType.OVERVIEW: DiataxisType.EXPLANATION,
            }
            if section.section_type in type_mapping:
                return type_mapping[section.section_type]
        
        # Fall back to pattern matching
        scores: dict[DiataxisType, int] = {}
        for dtype, patterns in self.DIATAXIS_PATTERNS.items():
            scores[dtype] = sum(1 for p in patterns if re.search(p, text))
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        return None
    
    def _detect_persona(self, text: str) -> PersonaType | None:
        """Detect target persona from text."""
        scores: dict[PersonaType, int] = {}
        for persona, patterns in self.PERSONA_PATTERNS.items():
            scores[persona] = sum(1 for p in patterns if re.search(p, text))
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        # Default to pragmatist if no clear signal
        return PersonaType.PRAGMATIST
    
    def _detect_domains(self, text: str) -> list[str]:
        """Detect domain tags from text."""
        domains = []
        for domain, patterns in self.DOMAIN_KEYWORDS.items():
            if any(re.search(p, text) for p in patterns):
                domains.append(domain)
        return domains
    
    def _infer_confidence(self, text: str) -> ConfidenceLevel:
        """Infer confidence level from uncertainty markers."""
        high_certainty = [
            r'\bmust\b', r'\balways\b', r'\bnever\b', r'\bdefinitely\b',
            r'\bguaranteed\b', r'\brequired\b',
        ]
        low_certainty = [
            r'\bmaybe\b', r'\bmight\b', r'\bpossibly\b', r'\bprobably\b',
            r'\btypically\b', r'\busually\b', r'\bgenerally\b',
        ]
        
        high_count = sum(1 for p in high_certainty if re.search(p, text))
        low_count = sum(1 for p in low_certainty if re.search(p, text))
        
        if high_count > low_count and high_count > 2:
            return ConfidenceLevel.HIGH
        elif low_count > high_count and low_count > 2:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MODERATE
```

---

## 5. Unified Memory Node

### 5.1 Combined Data Model

```python
# src/sunwell/headspace/memory_node.py

from dataclasses import dataclass, field
from datetime import datetime

from sunwell.headspace.chunks import Chunk
from sunwell.headspace.spatial import SpatialContext
from sunwell.headspace.structural import DocumentSection
from sunwell.headspace.facets import ContentFacets
from sunwell.headspace.topology import ConceptEdge


@dataclass
class MemoryNode:
    """Unified memory node combining all topology dimensions.
    
    A single unit of memory with:
    - Content (text, code, etc.)
    - Temporal position (RFC-013 chunk)
    - Spatial position (where in document/code)
    - Structural context (document hierarchy)
    - Faceted tags (multi-dimensional)
    - Graph edges (relationships to other nodes)
    """
    
    id: str
    """Unique identifier."""
    
    content: str
    """The actual content."""
    
    # === Temporal (RFC-013) ===
    chunk: Chunk | None = None
    """RFC-013 chunk data (turn-based chunking)."""
    
    # === Spatial ===
    spatial: SpatialContext | None = None
    """Position context (file, line, section path)."""
    
    # === Structural ===
    section: DocumentSection | None = None
    """Document section context."""
    
    # === Multi-Faceted ===
    facets: ContentFacets | None = None
    """Cross-dimensional tags."""
    
    # === Topological ===
    outgoing_edges: list[ConceptEdge] = field(default_factory=list)
    """Relationships where this node is source."""
    
    incoming_edges: list[ConceptEdge] = field(default_factory=list)
    """Relationships where this node is target."""
    
    # === Metadata ===
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # === Retrieval ===
    embedding: tuple[float, ...] | None = None
    """Vector embedding for semantic search."""
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        parts = []
        
        if self.spatial:
            parts.append(str(self.spatial))
        
        if self.section:
            parts.append(f"[{self.section.section_type.value}]")
        
        if self.facets and self.facets.diataxis_type:
            parts.append(f"({self.facets.diataxis_type.value})")
        
        parts.append(self.content[:100] + "..." if len(self.content) > 100 else self.content)
        
        return " ".join(parts)
```

### 5.2 Unified Memory Store

```python
# src/sunwell/headspace/unified_store.py

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import numpy as np

from sunwell.headspace.memory_node import MemoryNode
from sunwell.headspace.topology import ConceptGraph, RelationType
from sunwell.headspace.facets import FacetedIndex, FacetQuery
from sunwell.headspace.spatial import SpatialQuery, spatial_match
from sunwell.headspace.structural import DocumentTree
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
        """Set the embedder for query-time embedding generation."""
        self._embedder = embedder
    
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
        import json
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Save nodes
        nodes_data = {}
        for node_id, node in self._nodes.items():
            nodes_data[node_id] = {
                "id": node.id,
                "content": node.content,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
                # Spatial
                "spatial": {
                    "position_type": node.spatial.position_type.value,
                    "file_path": node.spatial.file_path,
                    "section_path": list(node.spatial.section_path),
                    "heading_level": node.spatial.heading_level,
                    "line_range": list(node.spatial.line_range),
                } if node.spatial else None,
                # Facets
                "facets": {
                    "diataxis_type": node.facets.diataxis_type.value if node.facets and node.facets.diataxis_type else None,
                    "primary_persona": node.facets.primary_persona.value if node.facets and node.facets.primary_persona else None,
                    "verification_state": node.facets.verification_state.value if node.facets else None,
                    "confidence": node.facets.confidence.value if node.facets else None,
                    "domain_tags": list(node.facets.domain_tags) if node.facets else [],
                } if node.facets else None,
            }
        
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
        import json
        from sunwell.headspace.spatial import SpatialContext, PositionType
        from sunwell.headspace.facets import (
            ContentFacets, DiataxisType, PersonaType, VerificationState, ConfidenceLevel
        )
        
        store = cls(base_path=base_path, embedding_dims=embedding_dims)
        
        nodes_path = base_path / "nodes.json"
        if nodes_path.exists():
            with open(nodes_path) as f:
                nodes_data = json.load(f)
            
            for node_id, data in nodes_data.items():
                # Reconstruct spatial
                spatial = None
                if data.get("spatial"):
                    s = data["spatial"]
                    spatial = SpatialContext(
                        position_type=PositionType(s["position_type"]),
                        file_path=s.get("file_path"),
                        section_path=tuple(s.get("section_path", [])),
                        heading_level=s.get("heading_level", 0),
                        line_range=tuple(s.get("line_range", (0, 0))),
                    )
                
                # Reconstruct facets
                facets = None
                if data.get("facets"):
                    f_data = data["facets"]
                    facets = ContentFacets(
                        diataxis_type=DiataxisType(f_data["diataxis_type"]) if f_data.get("diataxis_type") else None,
                        primary_persona=PersonaType(f_data["primary_persona"]) if f_data.get("primary_persona") else None,
                        verification_state=VerificationState(f_data["verification_state"]) if f_data.get("verification_state") else VerificationState.UNVERIFIED,
                        confidence=ConfidenceLevel(f_data["confidence"]) if f_data.get("confidence") else ConfidenceLevel.MODERATE,
                        domain_tags=tuple(f_data.get("domain_tags", [])),
                    )
                
                node = MemoryNode(
                    id=data["id"],
                    content=data["content"],
                    spatial=spatial,
                    facets=facets,
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                )
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
```

---

## Storage Layout

```
.sunwell/memory/
├── unified/                        # Unified memory store
│   ├── nodes.json                  # All memory nodes (O(n) space)
│   ├── graph.json                  # Concept graph edges (O(E) space)
│   └── embeddings/                 # InMemoryIndex persistence
│       ├── vectors.npy             # NumPy array (n × dims floats)
│       └── metadata.json           # IDs and metadata
│
├── chunks/                         # RFC-013 temporal chunks
│   ├── hot/
│   ├── warm/
│   └── cold/
│
├── documents/                      # Document structure cache (DocumentTree)
│   ├── RFC-013.tree.json
│   └── RFC-014.tree.json
│
└── indexes/                        # Inverted indexes (FacetedIndex)
    ├── by_diataxis.json            # O(|diataxis_types|) sets
    ├── by_persona.json             # O(|personas|) sets
    └── by_domain.json              # O(|domains|) sets
```

### Storage Size Estimates

| Component | Formula | Example (10K nodes) |
|-----------|---------|---------------------|
| `nodes.json` | ~2KB × n | ~20MB |
| `vectors.npy` | 4B × dims × n | ~60MB (1536 dims) |
| `graph.json` | ~200B × E | ~10MB (5 edges/node) |
| Facet indexes | O(n × f) refs | ~5MB |
| **Total** | — | **~95MB** |

---

## Query Examples

### 1. Spatial: "What did we say about caching in the Design section?"

```python
results = store.query(
    text_query="caching",
    spatial_query=SpatialQuery(section_contains="Design"),
)
```

### 2. Topological: "What contradicts our decision about CTF format?"

```python
ctf_node = store.get_node("ctf_decision")
contradictions = store.find_contradictions(ctf_node.id)
```

### 3. Structural: "All content under Limitations headings"

```python
results = store.query_by_section("Limitations")
```

### 4. Multi-faceted: "Tutorial content for novices about CLI"

```python
results = store.query_facets(FacetQuery(
    diataxis_type=DiataxisType.TUTORIAL,
    persona=PersonaType.NOVICE,
    domain_tags=("cli",),
))
```

### 5. Hybrid: Everything combined

```python
results = store.query(
    text_query="configuration",
    spatial_query=SpatialQuery(
        file_pattern="docs/*.md",
        section_contains="Reference",
    ),
    facet_query=FacetQuery(
        verification_state=(VerificationState.VERIFIED,),
        min_confidence=ConfidenceLevel.MODERATE,
    ),
    limit=10,
)
```

---

## Implementation Plan

### Phase 1: Core Types (Week 1)

- [ ] Add `SpatialContext` and `SpatialQuery` types
- [ ] Add `ContentFacets` and `FacetQuery` types
- [ ] Add `RelationType` and `ConceptEdge` types
- [ ] Add `MemoryNode` unified type
- [ ] Unit tests for all new types

**Exit criteria**: Types compile, serialize/deserialize correctly.

**Complexity validation**:
```python
def test_spatial_match_constant_time():
    """Verify spatial_match is O(1) per node."""
    ctx = SpatialContext(...)
    query = SpatialQuery(...)
    # Should complete in <1ms regardless of content size
    assert timeit(lambda: spatial_match(ctx, query), number=10000) < 1.0
```

### Phase 2: Extractors (Week 2)

- [ ] Implement `SpatialExtractor` for markdown and Python
- [ ] Implement `FacetExtractor` with heuristic detection
- [ ] Implement basic `TopologyExtractor` (heuristic)
- [ ] Unit tests for extractors

**Exit criteria**: Extractors produce reasonable output for sample documents.

**Complexity targets**:
- `SpatialExtractor.from_markdown()`: O(L) where L=lines
- `SpatialExtractor.from_python()`: O(AST nodes)
- `FacetExtractor.extract_from_text()`: O(text length × patterns)

### Phase 3: Indexes (Week 3)

- [ ] Implement `FacetedIndex` with inverted indexes
- [ ] Implement `ConceptGraph` with edge operations + `prune()`
- [ ] Implement `DocumentTree` for structural parsing
- [ ] Benchmark index query performance
- [ ] Add `ConceptGraph.stats` for monitoring

**Exit criteria**: Index queries return correct results in <10ms for 10K nodes.

**Benchmark targets**:
| Operation | 1K nodes | 10K nodes | 100K nodes |
|-----------|----------|-----------|------------|
| `FacetedIndex.query()` | <1ms | <5ms | <50ms |
| `ConceptGraph.find_path()` | <2ms | <20ms | <200ms |
| `get_neighborhood(depth=2)` | <5ms | <50ms | <500ms |

### Phase 4: Unified Store (Week 4)

- [ ] Implement `UnifiedMemoryStore`
- [ ] Integrate with `InMemoryIndex` for embeddings
- [ ] Integrate with RFC-013 `ChunkManager`
- [ ] Implement persistence (save/load)
- [ ] Add hybrid query support

**Exit criteria**: Store persists and retrieves nodes correctly. Embedding search <100ms.

### Phase 5: LLM Integration (Week 5)

- [ ] Add LLM-based `TopologyExtractor.extract_relationships()`
- [ ] Add LLM-based facet refinement
- [ ] Add relationship confirmation UI (`/confirm-link`)
- [ ] Cost analysis: track tokens per extraction

**Exit criteria**: LLM extraction produces high-quality relationships. Cost <$0.01 per 10 relationships.

**Token budget**:
```yaml
relationship_extraction:
  max_source_tokens: 1000     # Truncate source content
  max_candidates: 10          # Limit comparison window
  max_output_tokens: 200      # Cap response
  estimated_cost: $0.003      # Per extraction call
```

### Phase 6: CLI & Integration (Week 6)

- [ ] Add `/memory` commands for inspecting store
- [ ] Add `/memory stats` showing complexity metrics
- [ ] Integrate with existing HeadspaceStore
- [ ] Add migration path from RFC-013 chunks
- [ ] Documentation and examples

**Exit criteria**: Users can query multi-topology memory from CLI.

**CLI commands**:
```bash
sunwell memory stats          # Show node/edge counts, index sizes
sunwell memory prune          # Run graph pruning
sunwell memory query "..."    # Hybrid query with timing
sunwell memory graph <id>     # Visualize node neighborhood
```

---

## Test Stubs

Key tests to validate correctness and complexity bounds:

```python
# tests/test_rfc014_multi_topology.py

import pytest
import numpy as np
from sunwell.headspace.spatial import SpatialContext, SpatialQuery, spatial_match, PositionType
from sunwell.headspace.topology import ConceptGraph, ConceptEdge, RelationType
from sunwell.headspace.facets import FacetedIndex, FacetQuery, ContentFacets, DiataxisType
from sunwell.headspace.unified_store import UnifiedMemoryStore


class TestSpatialMemory:
    """Tests for spatial context matching."""
    
    def test_spatial_match_exact_section(self):
        """Section constraint filters correctly."""
        ctx = SpatialContext(
            position_type=PositionType.DOCUMENT,
            file_path="docs/rfc.md",
            section_path=("Design", "Architecture", "Caching"),
            heading_level=3,
        )
        
        query = SpatialQuery(section_contains="Caching")
        assert spatial_match(ctx, query) == 1.0
        
        query_miss = SpatialQuery(section_contains="Limitations")
        assert spatial_match(ctx, query_miss) == 0.0
    
    def test_spatial_match_file_pattern(self):
        """Glob patterns match file paths."""
        ctx = SpatialContext(
            position_type=PositionType.DOCUMENT,
            file_path="src/sunwell/headspace/store.py",
        )
        
        assert spatial_match(ctx, SpatialQuery(file_pattern="src/**/*.py")) == 1.0
        assert spatial_match(ctx, SpatialQuery(file_pattern="docs/*.md")) == 0.0


class TestConceptGraph:
    """Tests for topological memory."""
    
    def test_find_path_bfs(self):
        """Shortest path found via BFS."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.ELABORATES))
        graph.add_edge(ConceptEdge("B", "C", RelationType.ELABORATES))
        graph.add_edge(ConceptEdge("A", "C", RelationType.RELATES_TO))  # Direct but different
        
        path = graph.find_path("A", "C")
        assert path is not None
        assert len(path) == 1  # Direct A→C is shortest
    
    def test_prune_removes_low_confidence(self):
        """Pruning removes edges below threshold."""
        graph = ConceptGraph()
        graph.add_edge(ConceptEdge("A", "B", RelationType.RELATES_TO, confidence=0.9))
        graph.add_edge(ConceptEdge("A", "C", RelationType.RELATES_TO, confidence=0.2))
        
        removed = graph.prune(min_confidence=0.5)
        assert removed == 1
        assert len(graph.get_outgoing("A")) == 1
    
    def test_neighborhood_bounded_by_depth(self):
        """Neighborhood expansion respects max_depth."""
        graph = ConceptGraph()
        # Create chain: A → B → C → D → E
        for i, (src, tgt) in enumerate([("A","B"), ("B","C"), ("C","D"), ("D","E")]):
            graph.add_edge(ConceptEdge(src, tgt, RelationType.ELABORATES))
        
        n1 = graph.get_neighborhood("A", depth=1)
        assert n1 == {"A", "B"}
        
        n2 = graph.get_neighborhood("A", depth=2)
        assert n2 == {"A", "B", "C"}


class TestFacetedIndex:
    """Tests for multi-faceted retrieval."""
    
    def test_inverted_index_intersection(self):
        """Query uses set intersection for efficiency."""
        index = FacetedIndex()
        
        # Add nodes with different facets
        index.add("n1", ContentFacets(diataxis_type=DiataxisType.TUTORIAL))
        index.add("n2", ContentFacets(diataxis_type=DiataxisType.TUTORIAL))
        index.add("n3", ContentFacets(diataxis_type=DiataxisType.REFERENCE))
        
        results = index.query(FacetQuery(diataxis_type=DiataxisType.TUTORIAL))
        assert len(results) == 2
        assert {r[0] for r in results} == {"n1", "n2"}


class TestUnifiedStore:
    """Integration tests for unified memory store."""
    
    def test_hybrid_query_combines_filters(self, tmp_path):
        """Hybrid query intersects spatial + facet constraints."""
        store = UnifiedMemoryStore(base_path=tmp_path, embedding_dims=384)
        
        from sunwell.headspace.memory_node import MemoryNode
        
        # Add nodes
        store.add_node(MemoryNode(
            id="n1",
            content="Caching improves performance",
            spatial=SpatialContext(
                position_type=PositionType.DOCUMENT,
                section_path=("Design", "Caching"),
            ),
            facets=ContentFacets(diataxis_type=DiataxisType.EXPLANATION),
        ))
        
        results = store.query(
            text_query="caching",
            spatial_query=SpatialQuery(section_contains="Design"),
            facet_query=FacetQuery(diataxis_type=DiataxisType.EXPLANATION),
        )
        
        assert len(results) == 1
        assert results[0][0].id == "n1"
    
    def test_save_load_roundtrip(self, tmp_path):
        """Store persists and loads correctly."""
        store = UnifiedMemoryStore(base_path=tmp_path)
        
        from sunwell.headspace.memory_node import MemoryNode
        store.add_node(MemoryNode(id="test", content="hello world"))
        store.save()
        
        loaded = UnifiedMemoryStore.load(tmp_path)
        assert loaded.get_node("test") is not None
        assert loaded.get_node("test").content == "hello world"
```

---

## Configuration Reference

```yaml
# ~/.sunwell/config.yaml

memory:
  # RFC-013 settings (unchanged)
  micro_chunk_size: 10
  hot_chunks: 2
  
  # RFC-014: Multi-topology settings
  topology:
    # Spatial
    spatial_extraction: true
    extract_from_markdown: true
    extract_from_python: true
    
    # Structural
    structural_chunking: true
    respect_section_boundaries: true
    min_section_size: 100
    max_section_size: 4000
    
    # Topological
    auto_extract_relationships: true
    relationship_extraction: heuristic  # heuristic | llm
    relationship_model: null            # Override model
    max_relationship_depth: 3           # For dependency traversal (O(d^k) bound)
    
    # Graph pruning (prevents unbounded growth)
    graph_pruning:
      enabled: true
      min_confidence: 0.3              # Remove edges below this
      max_edges_per_node: 50           # Limit fan-out per node
      decay_factor: 0.95               # Auto-extracted edges decay
      decay_interval_days: 7           # How often to apply decay
      prune_on_save: true              # Auto-prune when saving
    
    # Multi-faceted
    auto_faceting: true
    faceting_strategy: heuristic        # heuristic | llm
    default_verification: unverified
    
    # Hybrid retrieval
    default_limit: 10
    combine_strategy: intersection      # intersection | union
    score_aggregation: average          # average | min | max
    
    # Embeddings (integrates with existing InMemoryIndex)
    embedding_dims: 1536                # Match your embedding model
    embedding_provider: local           # local | openai
    embedding_model: all-MiniLM-L6-v2   # For local provider (384 dims)
```

### Complexity-Aware Defaults

| Setting | Default | Rationale |
|---------|---------|-----------|
| `max_relationship_depth` | 3 | Limits `get_neighborhood()` to O(d³) |
| `max_edges_per_node` | 50 | Caps per-node storage, prevents hub explosion |
| `default_limit` | 10 | Bounds result set size |
| `min_confidence` | 0.3 | Prunes ~70% of stale auto-extracted edges |

---

## Tool Integration (RFC-012)

RFC-014's multi-topology memory system integrates with RFC-012's tool calling to give models explicit memory agency. Rather than relying solely on automatic RAG retrieval, models can proactively search, store, and navigate memory.

### Memory Tools

The following tools expose RFC-014 retrieval capabilities to the model:

```python
from sunwell.models.protocol import Tool

MEMORY_TOOLS: dict[str, Tool] = {
    # === Search & Recall ===
    
    "search_memory": Tool(
        name="search_memory",
        description=(
            "Search conversation history, learnings, and indexed content. "
            "Use when you need to recall something discussed earlier, "
            "find related context, or verify what you know."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query (e.g., 'user name', 'caching decision')",
                },
                "content_type": {
                    "type": "string",
                    "description": "Filter by content type",
                    "enum": ["any", "conversation", "learning", "decision", "dead_end"],
                    "default": "any",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    
    "recall_user_info": Tool(
        name="recall_user_info",
        description=(
            "Recall stored information about the user: name, preferences, "
            "context, constraints. Use before answering personal questions."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    
    "find_related": Tool(
        name="find_related",
        description=(
            "Find information that elaborates on, depends on, or relates to a topic. "
            "Uses the concept graph to traverse relationships."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or concept to find related information for",
                },
                "relationship": {
                    "type": "string",
                    "description": "Type of relationship to follow",
                    "enum": ["any", "elaborates", "depends_on", "contradicts", "supersedes"],
                    "default": "any",
                },
            },
            "required": ["topic"],
        },
    ),
    
    "find_contradictions": Tool(
        name="find_contradictions",
        description=(
            "Find information that contradicts or conflicts with a statement. "
            "Use before making claims to check for known issues."
        ),
        parameters={
            "type": "object",
            "properties": {
                "statement": {
                    "type": "string",
                    "description": "Statement to check for contradictions",
                },
            },
            "required": ["statement"],
        },
    ),
    
    # === Store & Track ===
    
    "add_learning": Tool(
        name="add_learning",
        description=(
            "Save an important fact, decision, or insight for future recall. "
            "Use when the user shares personal info, makes a decision, or "
            "when you discover something worth remembering."
        ),
        parameters={
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact or insight to remember",
                },
                "category": {
                    "type": "string",
                    "description": "Category for organization",
                    "enum": ["user_info", "decision", "preference", "constraint", "insight"],
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0.0-1.0",
                    "default": 1.0,
                },
            },
            "required": ["fact", "category"],
        },
    ),
    
    "mark_dead_end": Tool(
        name="mark_dead_end",
        description=(
            "Record that the current approach won't work, with reason. "
            "Prevents revisiting failed paths and helps future retrieval "
            "avoid suggesting the same dead ends."
        ),
        parameters={
            "type": "object",
            "properties": {
                "approach": {
                    "type": "string",
                    "description": "What approach was tried",
                },
                "reason": {
                    "type": "string",
                    "description": "Why it doesn't work",
                },
            },
            "required": ["approach", "reason"],
        },
    ),
}
```

### Tool Handler Implementation

Memory tools require access to the `UnifiedMemoryStore` and `ConversationDAG`:

```python
from sunwell.headspace.dag import ConversationDAG
from sunwell.headspace.turn import Learning

class MemoryToolHandler:
    """Handles memory tool execution.
    
    Bridges RFC-012 tool calls to RFC-014 memory operations.
    """
    
    def __init__(
        self,
        dag: ConversationDAG,
        store: "UnifiedMemoryStore | None" = None,
        embedder: "EmbeddingProtocol | None" = None,
    ):
        self.dag = dag
        self.store = store
        self.embedder = embedder
    
    async def handle(self, tool_name: str, arguments: dict) -> str:
        """Execute a memory tool and return result."""
        
        if tool_name == "search_memory":
            return await self._search_memory(
                query=arguments["query"],
                content_type=arguments.get("content_type", "any"),
                limit=arguments.get("limit", 5),
            )
        
        elif tool_name == "recall_user_info":
            return await self._recall_user_info()
        
        elif tool_name == "find_related":
            return await self._find_related(
                topic=arguments["topic"],
                relationship=arguments.get("relationship", "any"),
            )
        
        elif tool_name == "find_contradictions":
            return await self._find_contradictions(arguments["statement"])
        
        elif tool_name == "add_learning":
            return self._add_learning(
                fact=arguments["fact"],
                category=arguments["category"],
                confidence=arguments.get("confidence", 1.0),
            )
        
        elif tool_name == "mark_dead_end":
            return self._mark_dead_end(
                approach=arguments["approach"],
                reason=arguments["reason"],
            )
        
        else:
            return f"Unknown memory tool: {tool_name}"
    
    async def _search_memory(
        self,
        query: str,
        content_type: str,
        limit: int,
    ) -> str:
        """Search memory using hybrid retrieval."""
        results = []
        
        # Search learnings
        if content_type in ("any", "learning", "user_info"):
            for learning in self.dag.get_active_learnings():
                if query.lower() in learning.fact.lower():
                    results.append(f"[Learning/{learning.category}] {learning.fact}")
        
        # Search conversation history
        if content_type in ("any", "conversation"):
            for turn in self.dag.iter_all_turns():
                if query.lower() in turn.content.lower():
                    prefix = "User" if turn.turn_type.value == "user" else "Assistant"
                    results.append(f"[{prefix}] {turn.content[:200]}...")
                    if len(results) >= limit:
                        break
        
        # Search unified store if available
        if self.store and content_type in ("any", "decision", "dead_end"):
            store_results = self.store.query(text_query=query, limit=limit)
            for node, score in store_results:
                results.append(f"[Memory] {node.content[:200]}...")
        
        if not results:
            return f"No results found for '{query}'"
        
        return "\n".join(results[:limit])
    
    async def _recall_user_info(self) -> str:
        """Recall all user_info category learnings."""
        user_learnings = [
            l for l in self.dag.get_active_learnings()
            if l.category == "user_info"
        ]
        
        if not user_learnings:
            return "No user information stored."
        
        return "\n".join(f"- {l.fact}" for l in user_learnings)
    
    async def _find_related(self, topic: str, relationship: str) -> str:
        """Find related concepts via graph traversal."""
        if not self.store:
            return "Unified memory store not available."
        
        # Find node matching topic
        candidates = self.store.query(text_query=topic, limit=1)
        if not candidates:
            return f"No information found about '{topic}'"
        
        node, _ = candidates[0]
        
        # Get related via graph
        if relationship == "elaborates":
            related = self.store.find_elaborations(node.id)
        elif relationship == "contradicts":
            related = self.store.find_contradictions(node.id)
        elif relationship == "depends_on":
            related = self.store.find_dependencies(node.id)
        else:
            # Get all outgoing edges
            edges = self.store._concept_graph.get_outgoing(node.id)
            related = [
                self.store._nodes[e.target_id]
                for e in edges
                if e.target_id in self.store._nodes
            ]
        
        if not related:
            return f"No related information found for '{topic}'"
        
        return "\n".join(f"- {n.content[:200]}..." for n in related[:5])
    
    async def _find_contradictions(self, statement: str) -> str:
        """Find information contradicting a statement."""
        if not self.store:
            # Fall back to dead ends in DAG
            dead_end_turns = [
                self.dag.turns[tid]
                for tid in self.dag.dead_ends
                if tid in self.dag.turns
            ]
            if dead_end_turns:
                return "Dead ends (may conflict):\n" + "\n".join(
                    f"- {t.content[:200]}..." for t in dead_end_turns[:5]
                )
            return "No contradictions found."
        
        # Search and check for contradictions
        candidates = self.store.query(text_query=statement, limit=5)
        contradictions = []
        
        for node, _ in candidates:
            edges = self.store._concept_graph.find_contradictions(node.id)
            for edge in edges:
                if edge.target_id in self.store._nodes:
                    target = self.store._nodes[edge.target_id]
                    contradictions.append(
                        f"- {target.content[:200]}... (confidence: {edge.confidence:.2f})"
                    )
        
        if not contradictions:
            return "No contradictions found."
        
        return "Potential contradictions:\n" + "\n".join(contradictions[:5])
    
    def _add_learning(self, fact: str, category: str, confidence: float) -> str:
        """Add a learning to the DAG."""
        learning = Learning(
            fact=fact,
            category=category,
            confidence=confidence,
            source_turns=(self.dag.active_head,) if self.dag.active_head else (),
        )
        self.dag.add_learning(learning)
        return f"✓ Learned: [{category}] {fact}"
    
    def _mark_dead_end(self, approach: str, reason: str) -> str:
        """Mark current path as dead end with context."""
        if self.dag.active_head:
            self.dag.mark_dead_end(self.dag.active_head)
            
            # Add learning about the dead end
            learning = Learning(
                fact=f"Dead end: {approach} - {reason}",
                category="dead_end",
                confidence=1.0,
                source_turns=(self.dag.active_head,),
            )
            self.dag.add_learning(learning)
            
            return f"✓ Marked as dead end: {approach}"
        
        return "No active conversation to mark."
```

### Integration with ToolExecutor

The `MemoryToolHandler` integrates with RFC-012's `ToolExecutor`:

```python
# In sunwell/tools/executor.py

class ToolExecutor:
    """Extended with memory tool support."""
    
    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        policy: ToolPolicy | None = None,
        memory_handler: MemoryToolHandler | None = None,  # NEW
    ):
        self.workspace = workspace
        self.sandbox = sandbox
        self.policy = policy or ToolPolicy()
        self.memory_handler = memory_handler
        
        self._handlers = {
            "list_files": ListFilesHandler(workspace),
            "search_files": SearchFilesHandler(workspace),
            "read_file": ReadFileHandler(workspace),
            "write_file": WriteFileHandler(workspace, policy),
            "run_command": RunCommandHandler(sandbox, policy),
        }
        
        # Memory tools (always available, no trust level needed)
        self._memory_tools = {
            "search_memory",
            "recall_user_info", 
            "find_related",
            "find_contradictions",
            "add_learning",
            "mark_dead_end",
        }
    
    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call."""
        # Memory tools handled separately
        if tool_call.name in self._memory_tools:
            if self.memory_handler:
                return await self.memory_handler.handle(
                    tool_call.name,
                    tool_call.arguments,
                )
            return "Memory tools not configured."
        
        # ... existing handler dispatch ...
```

### Trust Levels for Memory Tools

Memory tools have special trust semantics:

| Tool | Trust Level | Rationale |
|------|-------------|-----------|
| `search_memory` | `discovery` | Read-only, no side effects |
| `recall_user_info` | `discovery` | Read-only, no side effects |
| `find_related` | `discovery` | Read-only graph traversal |
| `find_contradictions` | `discovery` | Read-only graph traversal |
| `add_learning` | `read_only` | Writes to session state |
| `mark_dead_end` | `read_only` | Writes to session state |

Memory tools are **always available** regardless of trust level because they only affect session state (not filesystem). They're enabled whenever tools are enabled.

### Usage Flow

```
User: "What's my name?"

1. Model receives query with automatic context (RAG retrieval)
2. RAG may or may not include relevant history
3. Model calls: search_memory(query="user name", content_type="user_info")
4. Handler searches learnings → finds "User's name is lb"
5. Model responds: "Your name is lb."

Alternatively, proactive storage:

User: "My name is Sarah"

1. Model recognizes personal information
2. Model calls: add_learning(fact="User's name is Sarah", category="user_info")
3. Handler stores in DAG learnings
4. Model responds: "Nice to meet you, Sarah!"
5. Future queries can recall via search_memory or recall_user_info
```

### Benefits Over Pure RAG

| Approach | Pros | Cons |
|----------|------|------|
| **Automatic RAG** | Zero-latency, always on | May miss important context |
| **Memory Tools** | Explicit, targeted, traceable | Adds tool call latency |
| **Both (hybrid)** | Best coverage | Most complex |

**Recommendation**: Use both. Automatic RAG provides baseline context; memory tools give the model agency for explicit recall when RAG misses.

---

## Open Questions

### Resolved

1. **Relationship extraction cost**: LLM-based relationship extraction is powerful but expensive.
   
   **Resolution**: ✅ Default to heuristic extraction. LLM extraction opt-in via `relationship_extraction: llm` config. Heuristics detect explicit references, contradiction signals, and topic overlap at O(n²) worst case but typically O(n × k) where k is candidate window.

2. **Graph size management**: Concept graphs can grow large. How to prune?
   
   **Resolution**: ✅ Implemented `ConceptGraph.prune()` method with:
   - Time-based confidence decay (`decay_factor: 0.95` per week)
   - Minimum confidence threshold (`min_confidence: 0.3`)
   - Per-node edge limit (`max_edges_per_node: 50`)
   - Complexity: O(E log E) due to per-node sorting

3. **Cross-session relationships**: Should relationships span sessions?
   
   **Resolution**: ✅ Yes. Graph stored globally in `.sunwell/memory/unified/graph.json`. Session-specific edges tagged with `session_id` in evidence field for debugging.

4. **UI for relationship management**: How do users view/edit relationships?
   
   **Resolution**: ✅ Deferred to CLI implementation phase:
   - `/memory graph [node_id]` — Visualize neighborhood (depth=2)
   - `/memory prune` — Manual pruning trigger
   - `/confirm-link <edge_id>` — Promote auto-extracted edge to confirmed

### Open

5. **Integration with existing `memory.py` types**: How do `MemoryType` and RFC-014 topologies coexist?
   
   **Status**: 🟡 Partially resolved. See "Relationship to Existing Memory Architecture" section. Full integration requires refactoring `SemanticMemory` to use `UnifiedMemoryStore` as backend.

6. **Embedding dimension mismatch**: Different embedding models have different dimensions (384 for MiniLM, 1536 for OpenAI).
   
   **Proposal**: Make `embedding_dims` configurable. Detect mismatch on load and warn/re-embed.

---

## References

### Sunwell
- [RFC-013: Hierarchical Memory](./RFC-013-hierarchical-memory.md)
- [RFC-012: Tool Calling](./RFC-012-tool-calling.md)

### Memory Models
- [Spatial Memory in AI](https://en.wikipedia.org/wiki/Spatial_memory)
- [Concept Graphs](https://en.wikipedia.org/wiki/Concept_map)
- [Knowledge Graphs](https://en.wikipedia.org/wiki/Knowledge_graph)

### Documentation Frameworks
- [Diataxis](https://diataxis.fr/)
- [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)

---

## Changelog

| Date | Change |
|:-----|:-------|
| 2026-01-15 | Initial draft |
| 2026-01-15 | Added spatial memory with document/code position context |
| 2026-01-15 | Added topological memory with concept graph and typed edges |
| 2026-01-15 | Added structural memory with document tree parsing |
| 2026-01-15 | Added multi-faceted memory with Diataxis/persona/verification tags |
| 2026-01-15 | Added unified MemoryNode combining all topologies |
| 2026-01-15 | Added UnifiedMemoryStore with hybrid query support |
| 2026-01-15 | **v2**: Added Big O complexity analysis section |
| 2026-01-15 | **v2**: Added "Relationship to Existing Memory Architecture" section |
| 2026-01-15 | **v2**: Integrated `InMemoryIndex` for embedding storage (replaces dict) |
| 2026-01-15 | **v2**: Added `ConceptGraph.prune()` method with decay and limits |
| 2026-01-15 | **v2**: Added `ConceptGraph.stats` property for monitoring |
| 2026-01-15 | **v2**: Added graph pruning configuration with complexity-aware defaults |
| 2026-01-15 | **v2**: Added test stubs for key operations |
| 2026-01-15 | **v2**: Fixed missing imports (fnmatch, deque, numpy) |
| 2026-01-15 | **v2**: Added storage size estimates and benchmark targets |
| 2026-01-15 | **v2**: Resolved 4/6 open questions with concrete implementations |
| 2026-01-15 | **v3**: Added Tool Integration section (RFC-012 bridge) |
| 2026-01-15 | **v3**: Defined 6 memory tools: search_memory, recall_user_info, find_related, find_contradictions, add_learning, mark_dead_end |
| 2026-01-15 | **v3**: Added MemoryToolHandler implementation |
| 2026-01-15 | **v3**: Documented trust levels and integration with ToolExecutor |