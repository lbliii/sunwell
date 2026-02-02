"""Codebase Graph - RFC-045 Phase 2.

Semantic understanding of the codebase, not just file contents.

Enhanced with structural graph for task decomposition and goal analysis.
"""


import ast
import pickle
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.knowledge.utils import extract_class_defs, is_python_file, parse_python_file

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


# =============================================================================
# Structural Graph Types (for task decomposition / goal analysis)
# =============================================================================


class NodeType(Enum):
    """Types of nodes in the structural graph."""

    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    VARIABLE = auto()


class EdgeType(Enum):
    """Types of edges (relationships) in the structural graph."""

    CONTAINS = auto()  # Module contains Class/Function
    DEFINES = auto()  # Class defines Method
    CALLS = auto()  # Function calls Function
    IMPORTS = auto()  # Module imports Module
    INHERITS = auto()  # Class inherits from Class
    USES = auto()  # Function uses Class/Variable


@dataclass(frozen=True, slots=True)
class StructuralNode:
    """A node in the structural graph representing a code entity.

    Contains rich metadata for task analysis:
    - Location (file, line) for context retrieval
    - Signature for understanding contracts
    - Docstring for semantic understanding
    """

    id: str  # Unique identifier (e.g., "class:BindingManager:path/to/file.py")
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
class StructuralEdge:
    """An edge in the structural graph representing a relationship.

    Typed edges enable different traversal strategies:
    - CALLS: for impact analysis and call tracing
    - IMPORTS: for dependency ordering
    - INHERITS: for class hierarchy analysis
    - CONTAINS/DEFINES: for structural decomposition
    """

    source_id: str
    target_id: str
    edge_type: EdgeType
    line: int | None = None  # Line where relationship occurs

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.edge_type))


# =============================================================================
# Original Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class CodeLocation:
    """A location in the codebase."""

    file: Path
    line_start: int
    line_end: int
    symbol: str | None = None  # Function/class name if applicable


@dataclass(frozen=True, slots=True)
class CodePath:
    """A path through the codebase (e.g., a call chain)."""

    nodes: tuple[str, ...]  # Function names
    frequency: float  # How often this path is taken
    latency_p50: float | None = None  # Median latency if available


@dataclass(slots=True)
class CodebaseGraph:
    """Semantic understanding of a codebase.

    Storage: `.sunwell/intelligence/codebase/graph.pickle`
    """

    # === Static Analysis (built from AST) ===

    call_graph: dict[str, list[str]] = field(default_factory=dict)
    """Function A calls function B. {func_a: [func_b, func_c]}"""

    import_graph: dict[str, list[str]] = field(default_factory=dict)
    """Module A imports module B. {module_a: [module_b, module_c]}"""

    class_hierarchy: dict[str, list[str]] = field(default_factory=dict)
    """Class A inherits from class B. {class_a: [base_class]}"""

    # === Semantic Clustering (built from embeddings) ===

    concept_clusters: dict[str, list[CodeLocation]] = field(default_factory=dict)
    """Concept → locations. 'authentication' → [auth.py, middleware.py]"""

    similar_functions: dict[str, list[str]] = field(default_factory=dict)
    """Function → similar functions. Detect potential duplication."""

    # === Dynamic Analysis (from execution traces) ===

    hot_paths: list[CodePath] = field(default_factory=list)
    """Most frequently executed paths. From profiling or trace sampling."""

    error_prone: list[CodeLocation] = field(default_factory=list)
    """Locations that have caused errors historically."""

    # === Metadata ===

    file_ownership: dict[Path, str] = field(default_factory=dict)
    """File → owner (from git blame or explicit)."""

    change_frequency: dict[Path, float] = field(default_factory=dict)
    """File → change rate. High churn = risky to modify."""

    coupling_scores: dict[tuple[str, str], float] = field(default_factory=dict)
    """(Module A, Module B) → coupling score. High = tightly coupled."""

    # === Structural Graph (for task decomposition) ===

    structural_nodes: dict[str, StructuralNode] = field(default_factory=dict)
    """All nodes in the structural graph. {node_id: StructuralNode}"""

    structural_edges_out: dict[str, list[tuple[str, StructuralEdge]]] = field(
        default_factory=dict
    )
    """Outgoing edges. {source_id: [(target_id, edge), ...]}"""

    structural_edges_in: dict[str, list[tuple[str, StructuralEdge]]] = field(
        default_factory=dict
    )
    """Incoming edges. {target_id: [(source_id, edge), ...]}"""

    file_to_nodes: dict[Path, set[str]] = field(default_factory=dict)
    """Map files to their nodes for incremental updates. {file_path: {node_ids}}"""

    # === Structural Graph Methods ===

    def add_structural_node(self, node: StructuralNode) -> None:
        """Add a node to the structural graph."""
        self.structural_nodes[node.id] = node
        if node.id not in self.structural_edges_out:
            self.structural_edges_out[node.id] = []
        if node.id not in self.structural_edges_in:
            self.structural_edges_in[node.id] = []
        # Track file → nodes mapping for incremental updates
        if node.file_path:
            if node.file_path not in self.file_to_nodes:
                self.file_to_nodes[node.file_path] = set()
            self.file_to_nodes[node.file_path].add(node.id)

    def add_structural_edge(self, edge: StructuralEdge) -> None:
        """Add an edge to the structural graph."""
        if edge.source_id not in self.structural_edges_out:
            self.structural_edges_out[edge.source_id] = []
        if edge.target_id not in self.structural_edges_in:
            self.structural_edges_in[edge.target_id] = []
        self.structural_edges_out[edge.source_id].append((edge.target_id, edge))
        self.structural_edges_in[edge.target_id].append((edge.source_id, edge))

    def get_structural_node(self, node_id: str) -> StructuralNode | None:
        """Get a node by ID."""
        return self.structural_nodes.get(node_id)

    def find_structural_nodes(
        self,
        name: str,
        node_type: NodeType | None = None,
    ) -> list[StructuralNode]:
        """Find nodes by name (case-insensitive partial match)."""
        name_lower = name.lower()
        results: list[StructuralNode] = []
        for node in self.structural_nodes.values():
            if name_lower in node.name.lower():
                if node_type is None or node.node_type == node_type:
                    results.append(node)
        return results

    def get_outgoing_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[tuple[StructuralNode, StructuralEdge]]:
        """Get all outgoing edges from a node."""
        results: list[tuple[StructuralNode, StructuralEdge]] = []
        for target_id, edge in self.structural_edges_out.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                target = self.structural_nodes.get(target_id)
                if target:
                    results.append((target, edge))
        return results

    def get_incoming_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[tuple[StructuralNode, StructuralEdge]]:
        """Get all incoming edges to a node."""
        results: list[tuple[StructuralNode, StructuralEdge]] = []
        for source_id, edge in self.structural_edges_in.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                source = self.structural_nodes.get(source_id)
                if source:
                    results.append((source, edge))
        return results

    def remove_file_nodes(self, file_path: Path) -> None:
        """Remove all nodes and edges from a file (for incremental updates)."""
        if file_path not in self.file_to_nodes:
            return

        node_ids = self.file_to_nodes[file_path].copy()
        for node_id in node_ids:
            # Remove from nodes
            if node_id in self.structural_nodes:
                del self.structural_nodes[node_id]

            # Remove outgoing edges
            if node_id in self.structural_edges_out:
                for target_id, _ in self.structural_edges_out[node_id]:
                    if target_id in self.structural_edges_in:
                        self.structural_edges_in[target_id] = [
                            (s, e)
                            for s, e in self.structural_edges_in[target_id]
                            if s != node_id
                        ]
                del self.structural_edges_out[node_id]

            # Remove incoming edges
            if node_id in self.structural_edges_in:
                for source_id, _ in self.structural_edges_in[node_id]:
                    if source_id in self.structural_edges_out:
                        self.structural_edges_out[source_id] = [
                            (t, e)
                            for t, e in self.structural_edges_out[source_id]
                            if t != node_id
                        ]
                del self.structural_edges_in[node_id]

        del self.file_to_nodes[file_path]

    def structural_stats(self) -> dict[str, int]:
        """Return statistics about the structural graph."""
        edge_count = sum(len(edges) for edges in self.structural_edges_out.values())
        return {
            "nodes": len(self.structural_nodes),
            "edges": edge_count,
            "files": len(self.file_to_nodes),
            "modules": sum(
                1
                for n in self.structural_nodes.values()
                if n.node_type == NodeType.MODULE
            ),
            "classes": sum(
                1
                for n in self.structural_nodes.values()
                if n.node_type == NodeType.CLASS
            ),
            "functions": sum(
                1
                for n in self.structural_nodes.values()
                if n.node_type in (NodeType.FUNCTION, NodeType.METHOD)
            ),
        }

    def save(self, base_path: Path) -> None:
        """Save codebase graph to disk."""
        graph_path = base_path / "codebase" / "graph.pickle"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        with open(graph_path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, base_path: Path) -> CodebaseGraph:
        """Load codebase graph from disk."""
        graph_path = base_path / "codebase" / "graph.pickle"
        if graph_path.exists():
            try:
                with open(graph_path, "rb") as f:
                    return pickle.load(f)
            except (pickle.PickleError, OSError):
                pass
        return cls()


class CodebaseAnalyzer:
    """Builds and maintains the codebase graph.

    Builds both the legacy simple graphs (call_graph, import_graph, class_hierarchy)
    and the new structural graph with full metadata for task analysis.
    """

    def __init__(
        self,
        embedder: EmbeddingProtocol | None = None,
    ):
        """Initialize codebase analyzer.

        Args:
            embedder: Optional embedder for semantic analysis
        """
        self._embedder = embedder
        self._current_file: Path | None = None
        self._current_module_id: str | None = None
        self._root: Path | None = None

    async def full_scan(self, root: Path) -> CodebaseGraph:
        """Full codebase scan. Run once on first use or after major changes.

        Builds both legacy graphs and the new structural graph.

        Args:
            root: Project root directory

        Returns:
            CodebaseGraph with static analysis results
        """
        graph = CodebaseGraph()
        self._root = root

        # Find all Python files
        python_files = list(root.rglob("*.py"))
        python_files = [f for f in python_files if not self._should_skip(f)]

        # Build both legacy and structural graphs
        for file_path in python_files:
            tree = parse_python_file(file_path)
            if tree is None:
                continue

            try:
                content = file_path.read_text()
                lines = content.split("\n")
            except (OSError, UnicodeDecodeError):
                lines = []

            # Extract imports
            module_name = self._get_module_name(file_path, root)
            imports = self._extract_imports(tree)
            graph.import_graph[module_name] = imports

            # Extract function calls (legacy)
            calls = self._extract_calls(tree, module_name)
            for func, called_funcs in calls.items():
                if func not in graph.call_graph:
                    graph.call_graph[func] = []
                graph.call_graph[func].extend(called_funcs)

            # Extract class hierarchy (legacy)
            classes = self._extract_classes(tree, module_name)
            for class_name, bases in classes.items():
                graph.class_hierarchy[class_name] = bases

            # Build structural graph with full metadata
            self._build_structural_graph(file_path, tree, lines, graph, module_name)

        return graph

    def _build_structural_graph(
        self,
        file_path: Path,
        tree: ast.Module,
        lines: list[str],
        graph: CodebaseGraph,
        module_name: str,
    ) -> None:
        """Build structural graph with full metadata from AST.

        Extracts:
        - Nodes: modules, classes, functions, methods with signatures/docstrings
        - Edges: contains, defines, calls, imports, inherits
        """
        self._current_file = file_path
        self._current_module_id = f"module:{file_path}"

        # Create module node
        module_node = StructuralNode(
            id=self._current_module_id,
            node_type=NodeType.MODULE,
            name=module_name,
            file_path=file_path,
            line=1,
            end_line=len(lines),
        )
        graph.add_structural_node(module_node)

        # Process top-level statements
        for node in tree.body:
            self._process_ast_node(node, graph, lines, self._current_module_id, None)

    def _process_ast_node(
        self,
        node: ast.AST,
        graph: CodebaseGraph,
        lines: list[str],
        parent_id: str,
        parent_class_id: str | None,
    ) -> None:
        """Process an AST node and add to structural graph."""
        if isinstance(node, ast.ClassDef):
            self._process_class_def(node, graph, lines, parent_id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._process_function_def(node, graph, lines, parent_id, parent_class_id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self._process_import_node(node, graph, parent_id)
        elif isinstance(node, ast.Assign):
            self._process_assignment(node, graph, lines, parent_id)

    def _process_class_def(
        self,
        node: ast.ClassDef,
        graph: CodebaseGraph,
        lines: list[str],
        parent_id: str,
    ) -> None:
        """Process a class definition."""
        class_id = f"class:{node.name}:{self._current_file}"
        class_node = StructuralNode(
            id=class_id,
            node_type=NodeType.CLASS,
            name=node.name,
            file_path=self._current_file,
            line=node.lineno,
            end_line=node.end_lineno,
            signature=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None,
            docstring=ast.get_docstring(node),
        )
        graph.add_structural_node(class_node)

        # CONTAINS edge from parent
        graph.add_structural_edge(
            StructuralEdge(
                source_id=parent_id,
                target_id=class_id,
                edge_type=EdgeType.CONTAINS,
                line=node.lineno,
            )
        )

        # INHERITS edges for base classes
        for base in node.bases:
            base_name = self._get_name_from_node(base)
            if base_name:
                # Create placeholder node for base (may be external)
                base_id = f"class:{base_name}:external"
                if base_id not in graph.structural_nodes:
                    graph.add_structural_node(
                        StructuralNode(
                            id=base_id,
                            node_type=NodeType.CLASS,
                            name=base_name,
                        )
                    )
                graph.add_structural_edge(
                    StructuralEdge(
                        source_id=class_id,
                        target_id=base_id,
                        edge_type=EdgeType.INHERITS,
                        line=node.lineno,
                    )
                )

        # Process class body
        for item in node.body:
            self._process_ast_node(item, graph, lines, class_id, class_id)

    def _process_function_def(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        graph: CodebaseGraph,
        lines: list[str],
        parent_id: str,
        parent_class_id: str | None,
    ) -> None:
        """Process a function or method definition."""
        is_method = parent_class_id is not None
        node_type = NodeType.METHOD if is_method else NodeType.FUNCTION

        func_id = (
            f"{'method' if is_method else 'func'}:{node.name}:"
            f"{self._current_file}:{node.lineno}"
        )
        func_node = StructuralNode(
            id=func_id,
            node_type=node_type,
            name=node.name,
            file_path=self._current_file,
            line=node.lineno,
            end_line=node.end_lineno,
            signature=self._extract_function_signature(node, lines),
            docstring=ast.get_docstring(node),
        )
        graph.add_structural_node(func_node)

        # CONTAINS or DEFINES edge
        if is_method and parent_class_id:
            graph.add_structural_edge(
                StructuralEdge(
                    source_id=parent_class_id,
                    target_id=func_id,
                    edge_type=EdgeType.DEFINES,
                    line=node.lineno,
                )
            )
        else:
            graph.add_structural_edge(
                StructuralEdge(
                    source_id=parent_id,
                    target_id=func_id,
                    edge_type=EdgeType.CONTAINS,
                    line=node.lineno,
                )
            )

        # Extract CALLS edges from function body
        self._extract_calls_from_function(node, graph, func_id)

    def _process_import_node(
        self,
        node: ast.Import | ast.ImportFrom,
        graph: CodebaseGraph,
        parent_id: str,
    ) -> None:
        """Process import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                target_id = f"module:{module_name}:external"
                if target_id not in graph.structural_nodes:
                    graph.add_structural_node(
                        StructuralNode(
                            id=target_id,
                            node_type=NodeType.MODULE,
                            name=module_name,
                        )
                    )
                graph.add_structural_edge(
                    StructuralEdge(
                        source_id=parent_id,
                        target_id=target_id,
                        edge_type=EdgeType.IMPORTS,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            target_id = f"module:{node.module}:external"
            if target_id not in graph.structural_nodes:
                graph.add_structural_node(
                    StructuralNode(
                        id=target_id,
                        node_type=NodeType.MODULE,
                        name=node.module,
                    )
                )
            graph.add_structural_edge(
                StructuralEdge(
                    source_id=parent_id,
                    target_id=target_id,
                    edge_type=EdgeType.IMPORTS,
                    line=node.lineno,
                )
            )

    def _process_assignment(
        self,
        node: ast.Assign,
        graph: CodebaseGraph,
        lines: list[str],
        parent_id: str,
    ) -> None:
        """Process top-level variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_id = f"var:{target.id}:{self._current_file}:{node.lineno}"
                var_node = StructuralNode(
                    id=var_id,
                    node_type=NodeType.VARIABLE,
                    name=target.id,
                    file_path=self._current_file,
                    line=node.lineno,
                )
                graph.add_structural_node(var_node)
                graph.add_structural_edge(
                    StructuralEdge(
                        source_id=parent_id,
                        target_id=var_id,
                        edge_type=EdgeType.CONTAINS,
                        line=node.lineno,
                    )
                )

    def _extract_calls_from_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        graph: CodebaseGraph,
        func_id: str,
    ) -> None:
        """Extract function calls from a function body."""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name:
                    # Create placeholder for called function
                    target_id = f"func:{call_name}:unknown"
                    if target_id not in graph.structural_nodes:
                        graph.add_structural_node(
                            StructuralNode(
                                id=target_id,
                                node_type=NodeType.FUNCTION,
                                name=call_name,
                            )
                        )
                    graph.add_structural_edge(
                        StructuralEdge(
                            source_id=func_id,
                            target_id=target_id,
                            edge_type=EdgeType.CALLS,
                            line=node.lineno,
                        )
                    )

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name being called."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _get_name_from_node(self, node: ast.AST) -> str | None:
        """Get name from a Name or Attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _extract_function_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
    ) -> str:
        """Extract function signature from source lines."""
        if node.lineno > len(lines):
            return ""

        sig_lines: list[str] = []
        for i in range(node.lineno - 1, min(node.lineno + 10, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break
        return "\n".join(sig_lines).strip()

    def _should_skip(self, path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".pytest_cache",
        ]
        return any(pattern in str(path) for pattern in skip_patterns)

    def _get_module_name(self, file_path: Path, root: Path) -> str:
        """Get module name from file path."""
        relative = file_path.relative_to(root)
        return str(relative.with_suffix("")).replace("/", ".")

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
        return imports

    def _extract_calls(self, tree: ast.AST, module: str) -> dict[str, list[str]]:
        """Extract function calls from AST."""
        calls: dict[str, list[str]] = {}
        current_function = None

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                current_function = f"{module}.{node.name}"
                calls[current_function] = []
            elif isinstance(node, ast.Call) and current_function:
                if isinstance(node.func, ast.Name):
                    calls[current_function].append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls[current_function].append(node.func.attr)

        return calls

    def _extract_classes(self, tree: ast.AST, module: str) -> dict[str, list[str]]:
        """Extract class hierarchy from AST."""
        classes: dict[str, list[str]] = {}
        for node in extract_class_defs(tree):
            class_name = f"{module}.{node.name}"
            bases = [
                base.id if isinstance(base, ast.Name) else str(base)
                for base in node.bases
            ]
            classes[class_name] = bases
        return classes

    async def incremental_update(
        self,
        changed_files: list[Path],
        graph: CodebaseGraph,
        root: Path,
    ) -> CodebaseGraph:
        """Update graph incrementally after file changes.

        Removes old nodes/edges for changed files and rebuilds them.

        Args:
            changed_files: List of files that changed
            graph: Existing codebase graph
            root: Project root directory

        Returns:
            Updated codebase graph
        """
        self._root = root

        # Re-scan changed files and update graph
        for file_path in changed_files:
            if not is_python_file(file_path):
                continue

            # Remove old structural graph data for this file
            graph.remove_file_nodes(file_path)

            tree = parse_python_file(file_path)
            if tree is None:
                continue

            try:
                content = file_path.read_text()
                lines = content.split("\n")
            except (OSError, UnicodeDecodeError):
                lines = []

            module_name = self._get_module_name(file_path, root)

            # Update imports (legacy)
            imports = self._extract_imports(tree)
            graph.import_graph[module_name] = imports

            # Update calls (legacy)
            calls = self._extract_calls(tree, module_name)
            for func, called_funcs in calls.items():
                graph.call_graph[func] = called_funcs

            # Rebuild structural graph for this file
            self._build_structural_graph(file_path, tree, lines, graph, module_name)

        return graph

    async def add_execution_trace(
        self,
        trace: dict,
        graph: CodebaseGraph,
    ) -> CodebaseGraph:
        """Incorporate runtime trace data (hot paths, error locations).

        Args:
            trace: Execution trace data
            graph: Existing codebase graph

        Returns:
            Updated codebase graph
        """
        # Extract hot paths from trace
        if "paths" in trace:
            for path_nodes in trace["paths"]:
                if len(path_nodes) >= 2:
                    code_path = CodePath(
                        nodes=tuple(path_nodes),
                        frequency=1.0,  # Default frequency
                    )
                    graph.hot_paths.append(code_path)

        # Extract error-prone locations
        if "errors" in trace:
            for error_info in trace["errors"]:
                if "file" in error_info and "line" in error_info:
                    location = CodeLocation(
                        file=Path(error_info["file"]),
                        line_start=error_info["line"],
                        line_end=error_info.get("line_end", error_info["line"]),
                    )
                    graph.error_prone.append(location)

        return graph
