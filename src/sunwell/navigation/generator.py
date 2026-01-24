"""ToC generation from codebase analysis (RFC-124).

Builds hierarchical Table of Contents from directory structure and
Python AST analysis. No LLM calls - deterministic generation.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.navigation.toc import NodeType, ProjectToc, TocNode, node_id_from_path

# Directories to skip during scanning
SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".sunwell",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "venv",
    "dist",
    "build",
    ".tox",
    ".nox",
    "htmlcov",
    ".coverage",
    "eggs",
    "*.egg-info",
})

# File extensions to include as file nodes (non-Python)
INCLUDE_EXTENSIONS: frozenset[str] = frozenset({
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
})

# Concept keyword mappings for deterministic classification
CONCEPT_KEYWORDS: dict[str, frozenset[str]] = {
    "auth": frozenset({
        "auth", "authentication", "authorization", "token", "session",
        "login", "logout", "permission", "role", "credential", "oauth",
        "jwt", "password", "security",
    }),
    "api": frozenset({
        "api", "endpoint", "route", "handler", "request", "response",
        "rest", "http", "websocket", "graphql", "rpc", "server", "client",
    }),
    "data": frozenset({
        "model", "schema", "database", "query", "orm", "entity",
        "repository", "store", "table", "record", "field", "migration",
    }),
    "config": frozenset({
        "config", "settings", "configuration", "environment", "options",
        "env", "setup", "initialize", "bootstrap",
    }),
    "test": frozenset({
        "test", "mock", "fixture", "assert", "spec", "integration",
        "unit", "e2e", "pytest", "unittest",
    }),
    "util": frozenset({
        "util", "utility", "helper", "common", "shared", "tools",
        "utils", "misc", "support",
    }),
    "core": frozenset({
        "core", "base", "protocol", "interface", "abstract", "main",
        "engine", "kernel", "foundation",
    }),
    "cli": frozenset({
        "cli", "command", "arg", "parser", "console", "terminal",
        "shell", "repl",
    }),
}

# Cross-reference patterns in comments
SEE_PATTERN = re.compile(r"#\s*[Ss]ee:?\s+([a-zA-Z0-9_./]+)", re.IGNORECASE)
TODO_PATTERN = re.compile(r"#\s*TODO:?\s+(.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass
class GeneratorConfig:
    """Configuration for ToC generation."""

    max_depth: int = 10
    """Maximum directory depth to scan."""

    include_private: bool = False
    """Include private modules/functions (starting with _)."""

    include_dunder: bool = False
    """Include dunder methods (__init__, __call__, etc.)."""

    min_function_lines: int = 3
    """Minimum lines for a function to be included."""

    max_file_size: int = 100_000
    """Maximum file size in bytes to parse."""


@dataclass
class TocGenerator:
    """Generate hierarchical ToC from codebase analysis.

    Process:
    1. Scan directory structure → module tree
    2. Parse Python AST → classes, functions
    3. Extract docstrings → summaries
    4. Detect cross-references → links
    5. Classify concepts → semantic tags

    All operations are deterministic (no LLM calls).
    """

    root: Path
    """Project root directory."""

    config: GeneratorConfig = field(default_factory=GeneratorConfig)
    """Generator configuration."""

    def generate(self) -> ProjectToc:
        """Full ToC generation.

        Scans the entire project and builds a complete ToC.
        Time: ~1-5 seconds for typical project (<1000 files).

        Returns:
            Complete ProjectToc with all nodes and indexes.
        """
        root_id = self.root.name or "project"
        toc = ProjectToc(root_id=root_id)

        # Create root node
        root_node = TocNode(
            node_id=root_id,
            title=root_id,
            node_type="directory",
            summary=self._infer_project_summary(),
            path=".",
            children=(),  # Will be updated
        )
        toc.add_node(root_node)

        # Build directory and file nodes
        self._build_directory_tree(toc, self.root, root_id, depth=0)

        # Parse Python files for code nodes
        self._build_code_nodes(toc)

        # Update parent-child relationships
        self._link_children(toc)

        # Extract cross-references
        self._extract_cross_refs(toc)

        # Classify concepts
        self._classify_concepts(toc)

        # Set metadata
        toc.generated_at = datetime.now()
        toc.file_count = sum(
            1 for n in toc.nodes.values() if n.node_type in ("file", "module")
        )

        return toc

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped.

        Args:
            path: Path to check.

        Returns:
            True if path should be skipped.
        """
        name = path.name

        # Skip hidden files/directories
        if name.startswith(".") and name not in (".sunwell",):
            return True

        # Skip known directories
        if path.is_dir() and name in SKIP_DIRS:
            return True

        # Skip pattern matches (e.g., *.egg-info)
        return any("*" in pattern and path.match(pattern) for pattern in SKIP_DIRS)

    def _infer_project_summary(self) -> str:
        """Infer project summary from README or pyproject.toml.

        Returns:
            Project summary string.
        """
        # Try README
        for readme_name in ("README.md", "README.rst", "README.txt", "README"):
            readme = self.root / readme_name
            if readme.exists():
                try:
                    content = readme.read_text(errors="ignore")[:500]
                    # Get first non-empty, non-header line
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("="):
                            return line[:100]
                except OSError:
                    pass

        # Try pyproject.toml description
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(errors="ignore")
                match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)[:100]
            except OSError:
                pass

        return f"Project root: {self.root.name}"

    def _build_directory_tree(
        self,
        toc: ProjectToc,
        directory: Path,
        parent_id: str,
        depth: int,
    ) -> None:
        """Build ToC nodes from directory structure.

        Args:
            toc: ProjectToc to populate.
            directory: Directory to scan.
            parent_id: Parent node ID.
            depth: Current depth.
        """
        if depth > self.config.max_depth:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        for entry in entries:
            if self._should_skip(entry):
                continue

            if entry.is_dir():
                # Check if it's a Python package or regular directory
                is_package = (entry / "__init__.py").exists()
                node_type: NodeType = "module" if is_package else "directory"

                node_id = node_id_from_path(entry, self.root)
                try:
                    rel_path = str(entry.relative_to(self.root))
                except ValueError:
                    rel_path = str(entry)

                summary = self._infer_directory_summary(entry, is_package)

                node = TocNode(
                    node_id=node_id,
                    title=entry.name,
                    node_type=node_type,
                    summary=summary,
                    path=rel_path,
                )
                toc.add_node(node)

                # Recurse into directory
                self._build_directory_tree(toc, entry, node_id, depth + 1)

            elif entry.suffix == ".py":
                # Python files are handled in _build_code_nodes
                pass

            elif entry.suffix in INCLUDE_EXTENSIONS:
                # Non-Python files (docs, config)
                node_id = node_id_from_path(entry, self.root)
                try:
                    rel_path = str(entry.relative_to(self.root))
                except ValueError:
                    rel_path = str(entry)

                summary = self._infer_file_summary(entry)

                node = TocNode(
                    node_id=node_id,
                    title=entry.name,
                    node_type="file",
                    summary=summary,
                    path=rel_path,
                )
                toc.add_node(node)

    def _infer_directory_summary(self, directory: Path, is_package: bool) -> str:
        """Infer directory/package summary.

        Args:
            directory: Directory path.
            is_package: Whether it's a Python package.

        Returns:
            Summary string.
        """
        if is_package:
            # Try to get docstring from __init__.py
            init_file = directory / "__init__.py"
            if init_file.exists():
                try:
                    content = init_file.read_text(errors="ignore")
                    tree = ast.parse(content)
                    docstring = ast.get_docstring(tree)
                    if docstring:
                        return self._first_sentence(docstring)
                except (SyntaxError, OSError):
                    pass

        # Count contents
        try:
            py_count = len(list(directory.glob("*.py")))
            subdirs = [d for d in directory.iterdir() if d.is_dir() and not self._should_skip(d)]
            subdir_count = len(subdirs)

            parts = []
            if py_count:
                parts.append(f"{py_count} modules")
            if subdir_count:
                parts.append(f"{subdir_count} packages")

            if parts:
                return f"Contains {', '.join(parts)}"
        except OSError:
            pass

        return f"Directory: {directory.name}"

    def _infer_file_summary(self, file_path: Path) -> str:
        """Infer summary for non-Python files.

        Args:
            file_path: File path.

        Returns:
            Summary string.
        """
        suffix = file_path.suffix.lower()

        if suffix in (".md", ".rst", ".txt"):
            try:
                content = file_path.read_text(errors="ignore")[:300]
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("="):
                        return line[:80]
            except OSError:
                pass
            return f"Documentation: {file_path.name}"

        if suffix in (".yaml", ".yml"):
            return f"YAML configuration: {file_path.name}"

        if suffix == ".toml":
            return f"TOML configuration: {file_path.name}"

        if suffix == ".json":
            return f"JSON data: {file_path.name}"

        return f"File: {file_path.name}"

    def _build_code_nodes(self, toc: ProjectToc) -> None:
        """Build ToC nodes from Python AST analysis.

        Args:
            toc: ProjectToc to populate.
        """
        for py_file in self.root.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            # Skip large files
            try:
                if py_file.stat().st_size > self.config.max_file_size:
                    continue
            except OSError:
                continue

            self._parse_python_file(toc, py_file)

    def _parse_python_file(self, toc: ProjectToc, file_path: Path) -> None:
        """Parse a Python file and extract code nodes.

        Args:
            toc: ProjectToc to populate.
            file_path: Python file to parse.
        """
        try:
            content = file_path.read_text(errors="ignore")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, OSError):
            return

        try:
            rel_path = str(file_path.relative_to(self.root))
        except ValueError:
            rel_path = str(file_path)

        module_id = node_id_from_path(file_path, self.root)

        # Module node
        module_docstring = ast.get_docstring(tree)
        module_summary = (
            self._first_sentence(module_docstring)
            if module_docstring
            else f"Module: {file_path.stem}"
        )

        module_node = TocNode(
            node_id=module_id,
            title=file_path.stem,
            node_type="module",
            summary=module_summary,
            path=rel_path,
            line_range=(1, len(content.splitlines())),
        )
        toc.add_node(module_node)

        # Extract classes and top-level functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._extract_class(toc, node, module_id, rel_path)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self._extract_function(toc, node, module_id, rel_path, is_method=False)

    def _extract_class(
        self,
        toc: ProjectToc,
        node: ast.ClassDef,
        parent_id: str,
        file_path: str,
    ) -> None:
        """Extract class node from AST.

        Args:
            toc: ProjectToc to populate.
            node: AST ClassDef node.
            parent_id: Parent module ID.
            file_path: Source file path.
        """
        name = node.name

        # Skip private classes unless configured
        if name.startswith("_") and not self.config.include_private:
            return

        class_id = f"{parent_id}.{name}"
        docstring = ast.get_docstring(node)
        summary = self._first_sentence(docstring) if docstring else f"Class: {name}"

        # Get line range
        end_line = node.end_lineno if hasattr(node, "end_lineno") else node.lineno
        line_range = (node.lineno, end_line or node.lineno)

        class_node = TocNode(
            node_id=class_id,
            title=name,
            node_type="class",
            summary=summary,
            path=file_path,
            line_range=line_range,
        )
        toc.add_node(class_node)

        # Extract methods
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                self._extract_function(toc, child, class_id, file_path, is_method=True)

    def _extract_function(
        self,
        toc: ProjectToc,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_id: str,
        file_path: str,
        is_method: bool,
    ) -> None:
        """Extract function/method node from AST.

        Args:
            toc: ProjectToc to populate.
            node: AST FunctionDef node.
            parent_id: Parent module/class ID.
            file_path: Source file path.
            is_method: Whether this is a method.
        """
        name = node.name

        # Skip dunder methods unless configured
        if name.startswith("__") and name.endswith("__") and not self.config.include_dunder:
            return

        # Skip private functions unless configured
        if name.startswith("_") and not name.startswith("__") and not self.config.include_private:
            return

        # Skip small functions
        end_line = node.end_lineno if hasattr(node, "end_lineno") else node.lineno
        if end_line and (end_line - node.lineno) < self.config.min_function_lines:
            return

        func_id = f"{parent_id}.{name}"
        docstring = ast.get_docstring(node)

        if docstring:
            summary = self._first_sentence(docstring)
        elif is_method:
            summary = f"Method: {name}"
        else:
            summary = f"Function: {name}"

        line_range = (node.lineno, end_line or node.lineno)

        func_node = TocNode(
            node_id=func_id,
            title=name,
            node_type="function",
            summary=summary,
            path=file_path,
            line_range=line_range,
        )
        toc.add_node(func_node)

    def _link_children(self, toc: ProjectToc) -> None:
        """Update parent-child relationships based on node IDs.

        Args:
            toc: ProjectToc to update.
        """
        # Build parent → children mapping
        parent_children: dict[str, list[str]] = {}

        for node_id in toc.nodes:
            # Find parent by removing last segment
            if "." in node_id:
                parent_id = node_id.rsplit(".", 1)[0]
                if parent_id in toc.nodes:
                    if parent_id not in parent_children:
                        parent_children[parent_id] = []
                    parent_children[parent_id].append(node_id)

        # Also link directories based on path
        for node_id, node in list(toc.nodes.items()):
            if node.node_type in ("directory", "module") and node.path != ".":
                parent_path = str(Path(node.path).parent)
                parent_id = toc.root_id if parent_path == "." else toc.path_to_node.get(parent_path)

                if parent_id and parent_id in toc.nodes:
                    if parent_id not in parent_children:
                        parent_children[parent_id] = []
                    if node_id not in parent_children[parent_id]:
                        parent_children[parent_id].append(node_id)

        # Update nodes with children
        for parent_id, children in parent_children.items():
            parent_node = toc.nodes[parent_id]
            # Sort children: directories first, then alphabetically
            sorted_children = sorted(
                children,
                key=lambda cid: (
                    toc.nodes[cid].node_type not in ("directory", "module"),
                    toc.nodes[cid].title.lower(),
                ),
            )
            # Create new node with updated children
            updated_node = TocNode(
                node_id=parent_node.node_id,
                title=parent_node.title,
                node_type=parent_node.node_type,
                summary=parent_node.summary,
                path=parent_node.path,
                line_range=parent_node.line_range,
                children=tuple(sorted_children),
                cross_refs=parent_node.cross_refs,
                concepts=parent_node.concepts,
            )
            toc.nodes[parent_id] = updated_node

    def _extract_cross_refs(self, toc: ProjectToc) -> None:
        """Detect and link cross-references.

        Extracts references from:
        1. Comment patterns: '# See: path/to/file.py'
        2. Import statements: 'from sunwell.auth import TokenValidator'
        3. Type annotations: 'def validate(token: auth.Token) -> bool'

        Args:
            toc: ProjectToc to update.
        """
        for node_id, node in list(toc.nodes.items()):
            if node.node_type != "module":
                continue

            file_path = self.root / node.path
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(errors="ignore")
            except OSError:
                continue

            refs: set[str] = set()

            # Strategy 1: Comment patterns (# See: ...)
            for match in SEE_PATTERN.finditer(content):
                ref = match.group(1)
                refs.add(f"see:{ref}")

            # Strategy 2: Import statements
            try:
                tree = ast.parse(content)
                for ast_node in ast.walk(tree):
                    if isinstance(ast_node, ast.Import):
                        for alias in ast_node.names:
                            # Only track local imports
                            if alias.name.startswith(toc.root_id.split(".")[0]):
                                refs.add(f"import:{alias.name}")
                    elif isinstance(ast_node, ast.ImportFrom) and ast_node.module:
                        module = ast_node.module
                        if module.startswith(toc.root_id.split(".")[0]):
                            refs.add(f"import:{module}")
            except SyntaxError:
                pass

            # Strategy 3: Type annotations (module.Type patterns)
            type_pattern = re.compile(r":\s*([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)")
            for match in type_pattern.finditer(content):
                type_ref = match.group(1)
                # Filter to likely local types
                if not type_ref.startswith(("typing.", "collections.")):
                    refs.add(f"type:{type_ref}")

            if refs:
                updated_node = TocNode(
                    node_id=node.node_id,
                    title=node.title,
                    node_type=node.node_type,
                    summary=node.summary,
                    path=node.path,
                    line_range=node.line_range,
                    children=node.children,
                    cross_refs=tuple(sorted(refs)),
                    concepts=node.concepts,
                )
                toc.nodes[node_id] = updated_node

    def _classify_concepts(self, toc: ProjectToc) -> None:
        """Classify nodes by semantic concept using keyword extraction.

        Algorithm (deterministic, no LLM):
        1. Extract keywords from: node title, path components, summary
        2. Map keywords to predefined concept categories
        3. Build reverse index: concept → [node_ids]

        Args:
            toc: ProjectToc to update.
        """
        for node_id, node in list(toc.nodes.items()):
            # Build searchable text from title, path, and summary
            text = f"{node.title} {node.path} {node.summary}".lower()
            words = set(re.findall(r"[a-z]+", text))

            # Match to concepts
            matched_concepts: list[str] = []
            for concept, keywords in CONCEPT_KEYWORDS.items():
                if words & keywords:
                    matched_concepts.append(concept)

            if matched_concepts:
                # Update concept index
                for concept in matched_concepts:
                    if concept not in toc.concept_index:
                        toc.concept_index[concept] = []
                    if node_id not in toc.concept_index[concept]:
                        toc.concept_index[concept].append(node_id)

                # Update node with concepts
                updated_node = TocNode(
                    node_id=node.node_id,
                    title=node.title,
                    node_type=node.node_type,
                    summary=node.summary,
                    path=node.path,
                    line_range=node.line_range,
                    children=node.children,
                    cross_refs=node.cross_refs,
                    concepts=tuple(sorted(matched_concepts)),
                )
                toc.nodes[node_id] = updated_node

    def _first_sentence(self, text: str) -> str:
        """Extract first sentence from text.

        Args:
            text: Text to extract from.

        Returns:
            First sentence, truncated to 100 chars.
        """
        # Clean up whitespace
        text = " ".join(text.split())

        # Find sentence end
        for end in (".", "!", "?"):
            idx = text.find(end)
            if 0 < idx < 100:
                return text[: idx + 1]

        # No sentence end found, truncate
        if len(text) > 100:
            return text[:97] + "..."
        return text
