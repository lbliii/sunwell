"""Codebase Graph - RFC-045 Phase 2.

Semantic understanding of the codebase, not just file contents.
"""


import ast
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.knowledge.utils import extract_class_defs, is_python_file, parse_python_file

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


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
    """Builds and maintains the codebase graph."""

    def __init__(
        self,
        embedder: EmbeddingProtocol | None = None,
    ):
        """Initialize codebase analyzer.

        Args:
            embedder: Optional embedder for semantic analysis
        """
        self._embedder = embedder

    async def full_scan(self, root: Path) -> CodebaseGraph:
        """Full codebase scan. Run once on first use or after major changes.

        Args:
            root: Project root directory

        Returns:
            CodebaseGraph with static analysis results
        """
        graph = CodebaseGraph()

        # Find all Python files
        python_files = list(root.rglob("*.py"))
        python_files = [f for f in python_files if not self._should_skip(f)]

        # Build call graph and import graph
        for file_path in python_files:
            tree = parse_python_file(file_path)
            if tree is None:
                continue

            # Extract imports
            module_name = self._get_module_name(file_path, root)
            imports = self._extract_imports(tree)
            graph.import_graph[module_name] = imports

            # Extract function calls
            calls = self._extract_calls(tree, module_name)
            for func, called_funcs in calls.items():
                if func not in graph.call_graph:
                    graph.call_graph[func] = []
                graph.call_graph[func].extend(called_funcs)

            # Extract class hierarchy
            classes = self._extract_classes(tree, module_name)
            for class_name, bases in classes.items():
                graph.class_hierarchy[class_name] = bases

        return graph

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

        Args:
            changed_files: List of files that changed
            graph: Existing codebase graph
            root: Project root directory

        Returns:
            Updated codebase graph
        """
        # Re-scan changed files and update graph
        for file_path in changed_files:
            if not is_python_file(file_path):
                continue

            tree = parse_python_file(file_path)
            if tree is None:
                continue

            module_name = self._get_module_name(file_path, root)

            # Update imports
            imports = self._extract_imports(tree)
            graph.import_graph[module_name] = imports

            # Update calls
            calls = self._extract_calls(tree, module_name)
            for func, called_funcs in calls.items():
                graph.call_graph[func] = called_funcs

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
