"""Core types for magnetic research.

Extracted from the magnetic_search_experiment.py script and extended
with research-specific types.
"""

from __future__ import annotations

import ast
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Graph Data Structures
# =============================================================================


class NodeType(Enum):
    """Types of nodes in the code graph."""

    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    VARIABLE = auto()


class EdgeType(Enum):
    """Types of edges (relationships) in the code graph."""

    CONTAINS = auto()  # Module contains Class/Function
    DEFINES = auto()  # Class defines Method
    CALLS = auto()  # Function calls Function
    IMPORTS = auto()  # Module imports Module
    INHERITS = auto()  # Class inherits from Class
    USES = auto()  # Function uses Class/Variable


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the code graph representing a code entity."""

    id: str  # Unique identifier (e.g., "module:path" or "class:name:path")
    node_type: NodeType
    name: str
    file_path: Path | None = None
    line: int | None = None
    end_line: int | None = None
    signature: str | None = None
    docstring: str | None = None

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """An edge in the code graph representing a relationship."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    line: int | None = None  # Line where relationship occurs

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.edge_type))


@dataclass(slots=True)
class CodeGraph:
    """A directed graph representing code structure and relationships.

    Uses adjacency lists for efficient traversal:
    - outgoing: node_id → list of (target_id, edge)
    - incoming: node_id → list of (source_id, edge)
    """

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    outgoing: dict[str, list[tuple[str, GraphEdge]]] = field(default_factory=dict)
    incoming: dict[str, list[tuple[str, GraphEdge]]] = field(default_factory=dict)
    file_to_nodes: dict[Path, set[str]] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self.outgoing:
            self.outgoing[node.id] = []
        if node.id not in self.incoming:
            self.incoming[node.id] = []
        if node.file_path:
            if node.file_path not in self.file_to_nodes:
                self.file_to_nodes[node.file_path] = set()
            self.file_to_nodes[node.file_path].add(node.id)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        if edge.source_id not in self.outgoing:
            self.outgoing[edge.source_id] = []
        if edge.target_id not in self.incoming:
            self.incoming[edge.target_id] = []
        self.outgoing[edge.source_id].append((edge.target_id, edge))
        self.incoming[edge.target_id].append((edge.source_id, edge))

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def find_nodes(self, name: str, node_type: NodeType | None = None) -> list[GraphNode]:
        """Find nodes by name (case-insensitive partial match)."""
        name_lower = name.lower()
        results: list[GraphNode] = []
        for node in self.nodes.values():
            if name_lower in node.name.lower():
                if node_type is None or node.node_type == node_type:
                    results.append(node)
        return results

    def get_outgoing(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Get all outgoing edges from a node."""
        results: list[tuple[GraphNode, GraphEdge]] = []
        for target_id, edge in self.outgoing.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                target = self.nodes.get(target_id)
                if target:
                    results.append((target, edge))
        return results

    def get_incoming(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Get all incoming edges to a node."""
        results: list[tuple[GraphNode, GraphEdge]] = []
        for source_id, edge in self.incoming.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                source = self.nodes.get(source_id)
                if source:
                    results.append((source, edge))
        return results

    def get_callers(self, name: str) -> list[GraphNode]:
        """Get all functions that call the given function/method."""
        callers: list[GraphNode] = []
        for node in self.find_nodes(name):
            for source, _ in self.get_incoming(node.id, EdgeType.CALLS):
                callers.append(source)
        return callers

    def get_callees(self, name: str) -> list[GraphNode]:
        """Get all functions called by the given function/method."""
        callees: list[GraphNode] = []
        for node in self.find_nodes(name):
            for target, _ in self.get_outgoing(node.id, EdgeType.CALLS):
                callees.append(target)
        return callees

    def get_subgraph(self, name: str, depth: int = 1) -> CodeGraph:
        """Extract a subgraph around a node (BFS to given depth)."""
        subgraph = CodeGraph()
        start_nodes = self.find_nodes(name)

        if not start_nodes:
            return subgraph

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for node in start_nodes:
            queue.append((node.id, 0))
            visited.add(node.id)

        while queue:
            node_id, current_depth = queue.popleft()
            node = self.nodes.get(node_id)
            if node:
                subgraph.add_node(node)

            if current_depth >= depth:
                continue

            for target_id, edge in self.outgoing.get(node_id, []):
                subgraph.add_edge(edge)
                if target_id not in visited:
                    visited.add(target_id)
                    queue.append((target_id, current_depth + 1))

            for source_id, edge in self.incoming.get(node_id, []):
                if edge.edge_type in (EdgeType.CONTAINS, EdgeType.DEFINES):
                    subgraph.add_edge(edge)
                    if source_id not in visited:
                        visited.add(source_id)
                        queue.append((source_id, current_depth + 1))

        return subgraph

    def get_impact(self, name: str, max_depth: int = 5) -> set[GraphNode]:
        """Get all nodes transitively reachable from the given node."""
        impacted: set[GraphNode] = set()
        start_nodes = self.find_nodes(name)

        if not start_nodes:
            return impacted

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for node in start_nodes:
            queue.append((node.id, 0))
            visited.add(node.id)
            impacted.add(node)

        while queue:
            node_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            for source_id, edge in self.incoming.get(node_id, []):
                if edge.edge_type in (EdgeType.CALLS, EdgeType.USES, EdgeType.INHERITS):
                    if source_id not in visited:
                        visited.add(source_id)
                        source = self.nodes.get(source_id)
                        if source:
                            impacted.add(source)
                            queue.append((source_id, depth + 1))

        return impacted

    def stats(self) -> dict[str, int]:
        """Return statistics about the graph."""
        edge_count = sum(len(edges) for edges in self.outgoing.values())
        return {
            "nodes": len(self.nodes),
            "edges": edge_count,
            "files": len(self.file_to_nodes),
            "modules": sum(1 for n in self.nodes.values() if n.node_type == NodeType.MODULE),
            "classes": sum(1 for n in self.nodes.values() if n.node_type == NodeType.CLASS),
            "functions": sum(
                1 for n in self.nodes.values() if n.node_type in (NodeType.FUNCTION, NodeType.METHOD)
            ),
        }


# =============================================================================
# Intent Classification
# =============================================================================


class Intent(Enum):
    """Query intent categories that determine extraction strategy."""

    DEFINITION = auto()  # "where is X defined"
    USAGE = auto()  # "where is X used/called"
    STRUCTURE = auto()  # "what methods does X have"
    CONTRACT = auto()  # "what does X expect/return"
    FLOW = auto()  # "how does X connect to Y"
    IMPACT = auto()  # "what's affected if I change X"
    UNKNOWN = auto()  # Fallback


class ResearchIntent(Enum):
    """Research-specific intent categories."""

    ARCHITECTURE = auto()  # "how is X structured"
    PATTERNS = auto()  # "common patterns for X"
    EXAMPLES = auto()  # "examples of X"
    BEST_PRACTICES = auto()  # "best practices for X"
    COMPARISON = auto()  # "compare approaches to X"


# =============================================================================
# Extraction Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class ExtractionPattern:
    """Pattern that defines what to extract from code."""

    intent: Intent
    entities: tuple[str, ...]
    node_types: tuple[type[ast.AST], ...] = ()
    name_matcher: str | None = None
    extract_body: bool = True
    extract_docstring: bool = True
    extract_signature: bool = True
    context_lines: int = 0


@dataclass(frozen=True, slots=True)
class CodeFragment:
    """A fragment of code extracted by magnetic search."""

    file_path: Path
    start_line: int
    end_line: int
    content: str
    fragment_type: str  # "class", "function", "call_site", etc.
    name: str | None = None
    docstring: str | None = None
    signature: str | None = None


@dataclass(slots=True)
class ExtractionResult:
    """Result of magnetic extraction."""

    fragments: list[CodeFragment] = field(default_factory=list)
    files_parsed: int = 0
    total_file_lines: int = 0
    parse_time_ms: float = 0.0


# =============================================================================
# Research Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class RepoResult:
    """A repository found via GitHub search."""

    full_name: str  # "owner/repo"
    description: str | None
    stars: int
    language: str | None
    updated_at: datetime
    clone_url: str
    default_branch: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FetchedRepo:
    """A repository that has been cloned locally."""

    repo: RepoResult
    local_path: Path
    files: tuple[Path, ...]  # Discovered source files


@dataclass(frozen=True, slots=True)
class RepoAnalysis:
    """Analysis results for a single repository."""

    repo: FetchedRepo
    graph: CodeGraph
    structure: tuple[CodeFragment, ...]  # Class/module skeletons
    key_files: tuple[Path, ...]  # Entry points, configs
    patterns: tuple[str, ...]  # Detected patterns


@dataclass(frozen=True, slots=True)
class ClassifiedPatterns:
    """Semantic grouping of functions across repos.

    Groups functions by their purpose (CRUD, handlers, predicates, etc.)
    and tracks which patterns appear across multiple repositories.
    """

    # category -> [(repo_name, func_name), ...]
    by_category: dict[str, list[tuple[str, str]]]
    # Cross-repo insights like "3/3 repos have CRUD operations"
    cross_repo_patterns: tuple[str, ...]
    # Top representative code examples
    key_examples: tuple[CodeFragment, ...]


@dataclass(frozen=True, slots=True)
class SynthesizedPatterns:
    """Patterns synthesized across multiple repositories."""

    common_structure: dict[str, int]  # path pattern -> count
    common_components: tuple[str, ...]  # component names in 2+ repos
    common_dependencies: tuple[str, ...]  # shared dependencies
    architecture_summary: str  # Summary of common architecture
    recommendations: tuple[str, ...]  # Suggested patterns to follow
    classified_patterns: ClassifiedPatterns | None = None  # Semantic function grouping


# =============================================================================
# Intent Classification
# =============================================================================


@dataclass(frozen=True, slots=True)
class ClassifiedQuery:
    """Result of intent classification."""

    intent: Intent
    entities: tuple[str, ...]
    confidence: float  # 0.0 - 1.0
    raw_query: str


class IntentClassifier:
    """Classify queries into intent categories using rule-based patterns."""

    INTENT_PATTERNS: list[tuple[Intent, re.Pattern[str], float]] = [
        # DEFINITION patterns
        (Intent.DEFINITION, re.compile(r"where\s+is\s+(\w+)\s+defined", re.I), 0.95),
        (Intent.DEFINITION, re.compile(r"find\s+(?:the\s+)?(\w+)\s+(?:class|function|def)", re.I), 0.9),
        (Intent.DEFINITION, re.compile(r"(?:class|function|def)\s+(\w+)", re.I), 0.85),
        (Intent.DEFINITION, re.compile(r"definition\s+of\s+(\w+)", re.I), 0.9),
        # USAGE patterns
        (Intent.USAGE, re.compile(r"where\s+is\s+(\w+)\s+(?:used|called)", re.I), 0.95),
        (Intent.USAGE, re.compile(r"what\s+(?:calls|uses)\s+(\w+)", re.I), 0.9),
        # STRUCTURE patterns
        (Intent.STRUCTURE, re.compile(r"what\s+methods?\s+does\s+(\w+)\s+have", re.I), 0.95),
        (Intent.STRUCTURE, re.compile(r"what(?:'s| is)\s+in\s+(\w+)", re.I), 0.85),
        (Intent.STRUCTURE, re.compile(r"(?:structure|outline|skeleton)\s+of\s+(\w+)", re.I), 0.9),
        # CONTRACT patterns
        (Intent.CONTRACT, re.compile(r"what\s+does\s+(\w+)\s+(?:expect|return|take)", re.I), 0.95),
        (Intent.CONTRACT, re.compile(r"signature\s+of\s+(\w+)", re.I), 0.95),
        # FLOW patterns
        (Intent.FLOW, re.compile(r"how\s+does\s+(\w+)\s+(?:connect|flow|reach)\s+(?:to\s+)?(\w+)", re.I), 0.9),
        # IMPACT patterns
        (Intent.IMPACT, re.compile(r"what(?:'s| is)\s+(?:affected|impacted)", re.I), 0.95),
        (Intent.IMPACT, re.compile(r"what\s+depends\s+on\s+(\w+)", re.I), 0.9),
    ]

    ENTITY_PATTERN = re.compile(r"\b([A-Z][a-zA-Z0-9_]+)\b")

    def classify(self, query: str) -> ClassifiedQuery:
        """Classify a query into intent + entities."""
        query = query.strip()

        for intent, pattern, confidence in self.INTENT_PATTERNS:
            match = pattern.search(query)
            if match:
                entities = tuple(g for g in match.groups() if g)
                return ClassifiedQuery(
                    intent=intent,
                    entities=entities,
                    confidence=confidence,
                    raw_query=query,
                )

        entities = tuple(set(self.ENTITY_PATTERN.findall(query)))
        return ClassifiedQuery(
            intent=Intent.UNKNOWN,
            entities=entities,
            confidence=0.3,
            raw_query=query,
        )


class PatternGenerator:
    """Generate extraction patterns from classified queries."""

    def generate(self, classified: ClassifiedQuery) -> ExtractionPattern:
        """Generate an extraction pattern from a classified query."""
        match classified.intent:
            case Intent.DEFINITION:
                return self._definition_pattern(classified)
            case Intent.USAGE:
                return self._usage_pattern(classified)
            case Intent.STRUCTURE:
                return self._structure_pattern(classified)
            case Intent.CONTRACT:
                return self._contract_pattern(classified)
            case Intent.FLOW:
                return self._flow_pattern(classified)
            case _:
                return self._fallback_pattern(classified)

    def _definition_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.DEFINITION,
            entities=classified.entities,
            node_types=(ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _usage_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.USAGE,
            entities=classified.entities,
            node_types=(ast.Call, ast.Attribute, ast.Name),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,
            extract_docstring=False,
            extract_signature=False,
            context_lines=3,
        )

    def _structure_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.STRUCTURE,
            entities=classified.entities,
            node_types=(ast.ClassDef,),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,
            extract_docstring=True,
            extract_signature=True,
        )

    def _contract_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.CONTRACT,
            entities=classified.entities,
            node_types=(ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=False,
            extract_docstring=True,
            extract_signature=True,
        )

    def _flow_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.FLOW,
            entities=classified.entities,
            node_types=(ast.Call, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _fallback_pattern(self, classified: ClassifiedQuery) -> ExtractionPattern:
        return ExtractionPattern(
            intent=Intent.UNKNOWN,
            entities=classified.entities,
            node_types=(ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            name_matcher=self._entity_regex(classified.entities),
            extract_body=True,
            extract_docstring=True,
            extract_signature=True,
        )

    def _entity_regex(self, entities: tuple[str, ...]) -> str:
        """Build regex pattern that matches any entity (case-insensitive)."""
        if not entities:
            return r".*"
        escaped = [re.escape(e) for e in entities]
        return r"(?i)(?:" + "|".join(escaped) + ")"
