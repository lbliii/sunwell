"""Magnetic analyzer for repository analysis.

Wraps the magnetic search extractors and graph builders for research.
"""

from __future__ import annotations

import ast
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rosettes import tokenize
from rosettes._types import TokenType

from sunwell.research.types import (
    CodeFragment,
    CodeGraph,
    EdgeType,
    ExtractionPattern,
    ExtractionResult,
    FetchedRepo,
    GraphEdge,
    GraphNode,
    Intent,
    NodeType,
    RepoAnalysis,
    ResearchIntent,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Python Graph Builder
# =============================================================================


class PythonGraphBuilder:
    """Build a code graph from Python source files."""

    def __init__(self) -> None:
        self._current_file: Path | None = None
        self._current_module_id: str | None = None

    def build_from_files(self, files: list[Path]) -> CodeGraph:
        """Build a graph from multiple Python files."""
        graph = CodeGraph()
        for file_path in files:
            self._add_file_to_graph(file_path, graph)
        return graph

    def _add_file_to_graph(self, file_path: Path, graph: CodeGraph) -> None:
        """Parse a file and add its nodes/edges to the graph."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, OSError, UnicodeDecodeError):
            return

        self._current_file = file_path
        lines = content.split("\n")

        module_id = f"module:{file_path}"
        self._current_module_id = module_id
        module_node = GraphNode(
            id=module_id,
            node_type=NodeType.MODULE,
            name=file_path.stem,
            file_path=file_path,
            line=1,
            end_line=len(lines),
        )
        graph.add_node(module_node)

        for node in tree.body:
            self._process_node(node, graph, lines, parent_id=module_id)

    def _process_node(
        self,
        node: ast.AST,
        graph: CodeGraph,
        lines: list[str],
        parent_id: str,
        parent_class_id: str | None = None,
    ) -> None:
        """Process an AST node and add to graph."""
        if isinstance(node, ast.ClassDef):
            self._process_class(node, graph, lines, parent_id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._process_function(node, graph, lines, parent_id, parent_class_id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self._process_import(node, graph, parent_id)

    def _process_class(
        self,
        node: ast.ClassDef,
        graph: CodeGraph,
        lines: list[str],
        parent_id: str,
    ) -> None:
        """Process a class definition."""
        class_id = f"class:{node.name}:{self._current_file}"
        class_node = GraphNode(
            id=class_id,
            node_type=NodeType.CLASS,
            name=node.name,
            file_path=self._current_file,
            line=node.lineno,
            end_line=node.end_lineno,
            signature=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None,
            docstring=ast.get_docstring(node),
        )
        graph.add_node(class_node)

        graph.add_edge(
            GraphEdge(
                source_id=parent_id,
                target_id=class_id,
                edge_type=EdgeType.CONTAINS,
                line=node.lineno,
            )
        )

        for base in node.bases:
            base_name = self._get_name(base)
            if base_name:
                base_id = f"class:{base_name}:external"
                if base_id not in graph.nodes:
                    graph.add_node(
                        GraphNode(
                            id=base_id,
                            node_type=NodeType.CLASS,
                            name=base_name,
                        )
                    )
                graph.add_edge(
                    GraphEdge(
                        source_id=class_id,
                        target_id=base_id,
                        edge_type=EdgeType.INHERITS,
                        line=node.lineno,
                    )
                )

        for item in node.body:
            self._process_node(item, graph, lines, parent_id=class_id, parent_class_id=class_id)

    def _process_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        graph: CodeGraph,
        lines: list[str],
        parent_id: str,
        parent_class_id: str | None = None,
    ) -> None:
        """Process a function or method definition."""
        is_method = parent_class_id is not None
        node_type = NodeType.METHOD if is_method else NodeType.FUNCTION

        func_id = f"{'method' if is_method else 'func'}:{node.name}:{self._current_file}:{node.lineno}"
        func_node = GraphNode(
            id=func_id,
            node_type=node_type,
            name=node.name,
            file_path=self._current_file,
            line=node.lineno,
            end_line=node.end_lineno,
            signature=self._extract_signature(node, lines),
            docstring=ast.get_docstring(node),
        )
        graph.add_node(func_node)

        if is_method:
            graph.add_edge(
                GraphEdge(
                    source_id=parent_class_id,
                    target_id=func_id,
                    edge_type=EdgeType.DEFINES,
                    line=node.lineno,
                )
            )
        else:
            graph.add_edge(
                GraphEdge(
                    source_id=parent_id,
                    target_id=func_id,
                    edge_type=EdgeType.CONTAINS,
                    line=node.lineno,
                )
            )

        self._extract_calls(node, graph, func_id)

    def _process_import(
        self,
        node: ast.Import | ast.ImportFrom,
        graph: CodeGraph,
        parent_id: str,
    ) -> None:
        """Process import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                target_id = f"module:{module_name}:external"
                if target_id not in graph.nodes:
                    graph.add_node(
                        GraphNode(
                            id=target_id,
                            node_type=NodeType.MODULE,
                            name=module_name,
                        )
                    )
                graph.add_edge(
                    GraphEdge(
                        source_id=parent_id,
                        target_id=target_id,
                        edge_type=EdgeType.IMPORTS,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            target_id = f"module:{node.module}:external"
            if target_id not in graph.nodes:
                graph.add_node(
                    GraphNode(
                        id=target_id,
                        node_type=NodeType.MODULE,
                        name=node.module,
                    )
                )
            graph.add_edge(
                GraphEdge(
                    source_id=parent_id,
                    target_id=target_id,
                    edge_type=EdgeType.IMPORTS,
                    line=node.lineno,
                )
            )

    def _extract_calls(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        graph: CodeGraph,
        func_id: str,
    ) -> None:
        """Extract function calls from a function body."""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name:
                    target_id = f"func:{call_name}:unknown"
                    if target_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=target_id,
                                node_type=NodeType.FUNCTION,
                                name=call_name,
                            )
                        )
                    graph.add_edge(
                        GraphEdge(
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

    def _get_name(self, node: ast.AST) -> str | None:
        """Get name from a Name or Attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
    ) -> str:
        """Extract function signature from source lines."""
        sig_lines: list[str] = []
        for i in range(node.lineno - 1, min(node.lineno + 10, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break
        return "\n".join(sig_lines).strip()


# =============================================================================
# Language Extractor Protocol
# =============================================================================


@runtime_checkable
class LanguageExtractor(Protocol):
    """Protocol for language-specific extractors."""

    def can_handle(self, file_path: Path) -> bool:
        """Return True if this extractor handles this file type."""
        ...

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a file."""
        ...


# =============================================================================
# Python Extractor
# =============================================================================


class PythonExtractor:
    """Extract code fragments from Python files using ast module."""

    EXTENSIONS = {".py", ".pyi"}

    def __init__(self) -> None:
        self._ast_cache: dict[Path, ast.Module | None] = {}

    def can_handle(self, file_path: Path) -> bool:
        """Return True for Python files."""
        return file_path.suffix.lower() in self.EXTENSIONS

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract matching code fragments from a Python file."""
        result = ExtractionResult()
        start_time = time.perf_counter()

        tree = self._parse_file(file_path)
        if tree is None:
            return result

        result.files_parsed = 1

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return result

        lines = content.split("\n")
        result.total_file_lines = len(lines)

        match pattern.intent:
            case Intent.DEFINITION | Intent.UNKNOWN:
                result.fragments = self._extract_definitions(tree, lines, file_path, pattern)
            case Intent.STRUCTURE:
                result.fragments = self._extract_structure(tree, lines, file_path, pattern)
            case Intent.CONTRACT:
                result.fragments = self._extract_contracts(tree, lines, file_path, pattern)
            case _:
                result.fragments = self._extract_definitions(tree, lines, file_path, pattern)

        result.parse_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _parse_file(self, file_path: Path) -> ast.Module | None:
        """Parse a Python file to AST (cached)."""
        if file_path in self._ast_cache:
            return self._ast_cache[file_path]

        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))
            self._ast_cache[file_path] = tree
            return tree
        except (SyntaxError, OSError, UnicodeDecodeError):
            self._ast_cache[file_path] = None
            return None

    def _extract_definitions(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract class and function definitions."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if name_re and not name_re.search(node.name):
                    continue

                fragment = self._node_to_fragment(node, lines, file_path, pattern)
                if fragment:
                    fragments.append(fragment)

        return fragments

    def _extract_structure(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract class skeleton (signatures only, no bodies)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if name_re and not name_re.search(node.name):
                    continue

                skeleton = self._class_skeleton(node, lines)
                skeleton_lines = len(skeleton.split("\n"))
                fragments.append(
                    CodeFragment(
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.lineno + skeleton_lines - 1,
                        content=skeleton,
                        fragment_type="class_skeleton",
                        name=node.name,
                        docstring=ast.get_docstring(node),
                        signature=f"class {node.name}",
                    )
                )

        return fragments

    def _extract_contracts(
        self,
        tree: ast.Module,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract function contracts (signature + docstring only)."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if name_re and not name_re.search(node.name):
                    continue

                signature = self._extract_signature(node, lines)
                docstring = ast.get_docstring(node)

                parts = [signature]
                if docstring:
                    parts.append(f'    """{docstring}"""')

                fragments.append(
                    CodeFragment(
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.lineno + (5 if docstring else 1),
                        content="\n".join(parts),
                        fragment_type="contract",
                        name=node.name,
                        docstring=docstring,
                        signature=signature,
                    )
                )

        return fragments

    def _node_to_fragment(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> CodeFragment | None:
        """Convert an AST node to a CodeFragment."""
        start_line = node.lineno

        if hasattr(node, "decorator_list") and node.decorator_list:
            for dec in node.decorator_list:
                start_line = min(start_line, dec.lineno)

        end_line = node.end_lineno or node.lineno

        if pattern.extract_body:
            content = "\n".join(lines[start_line - 1 : end_line])
        else:
            content = self._extract_signature(node, lines)
            docstring = ast.get_docstring(node)
            if pattern.extract_docstring and docstring:
                indent = "    " if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
                content += f'\n{indent}"""{docstring}"""'

        fragment_type = "class" if isinstance(node, ast.ClassDef) else "function"

        return CodeFragment(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            fragment_type=fragment_type,
            name=node.name,
            docstring=ast.get_docstring(node),
            signature=self._extract_signature(node, lines),
        )

    def _class_skeleton(self, node: ast.ClassDef, lines: list[str]) -> str:
        """Extract class skeleton - signatures only, no bodies."""
        parts: list[str] = []

        parts.append(lines[node.lineno - 1])

        docstring = ast.get_docstring(node)
        if docstring:
            parts.append(f'    """{docstring}"""')

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._extract_signature(item, lines)
                parts.append(f"    {sig}")
                parts.append("        ...")

        return "\n".join(parts)

    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        lines: list[str],
    ) -> str:
        """Extract signature from source lines."""
        if isinstance(node, ast.ClassDef):
            return lines[node.lineno - 1].strip()

        sig_lines: list[str] = []
        for i in range(node.lineno - 1, min(node.lineno + 10, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break

        return "\n".join(sig_lines).strip()


# =============================================================================
# Rosettes Extractor (JS/TS/Svelte via tokenization)
# =============================================================================


class RosettesExtractor:
    """Extract code fragments from JS/TS/Svelte using rosettes tokenization.

    Uses rosettes lexers to tokenize files and extract:
    - Function names and signatures
    - Class names
    - Import statements
    - Component names (Svelte)

    Not as rich as a full AST, but works on 3.14t and is sufficient
    for pattern discovery in the research tool.
    """

    EXTENSIONS: dict[str, str] = {
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".svelte": "javascript",  # Svelte script blocks are JS/TS
        ".vue": "javascript",
        ".mjs": "javascript",
        ".mts": "typescript",
    }

    def can_handle(self, file_path: Path) -> bool:
        """Return True for JS/TS/Svelte files."""
        return file_path.suffix.lower() in self.EXTENSIONS

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract code fragments using rosettes tokenization."""
        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return result

        result.files_parsed = 1
        lines = content.split("\n")
        result.total_file_lines = len(lines)

        lang = self.EXTENSIONS.get(file_path.suffix.lower(), "javascript")

        # For Svelte, extract script content
        if file_path.suffix.lower() == ".svelte":
            content = self._extract_svelte_script(content)
            if not content:
                result.parse_time_ms = (time.perf_counter() - start_time) * 1000
                return result

        # Tokenize with rosettes
        try:
            tokens = list(tokenize(content, lang))
        except Exception:
            logger.debug("Failed to tokenize %s", file_path)
            result.parse_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        # Extract based on intent
        match pattern.intent:
            case Intent.DEFINITION | Intent.UNKNOWN:
                result.fragments = self._extract_definitions(
                    tokens, lines, file_path, pattern
                )
            case Intent.STRUCTURE:
                result.fragments = self._extract_structure(
                    tokens, lines, file_path, pattern
                )
            case _:
                result.fragments = self._extract_definitions(
                    tokens, lines, file_path, pattern
                )

        result.parse_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _extract_svelte_script(self, content: str) -> str:
        """Extract script content from Svelte file."""
        # Simple regex extraction of <script> content
        import re

        match = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _extract_definitions(
        self,
        tokens: list,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract function and class definitions from tokens."""
        fragments: list[CodeFragment] = []
        name_re = re.compile(pattern.name_matcher) if pattern.name_matcher else None

        # Token types that indicate declarations in rosettes
        declaration_types = {TokenType.KEYWORD, TokenType.KEYWORD_DECLARATION}

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Look for function definitions (rosettes uses KEYWORD_DECLARATION)
            if token.type in declaration_types and token.value in (
                "function",
                "async",
            ):
                frag = self._extract_function_at(tokens, i, lines, file_path, pattern)
                if frag and (not name_re or name_re.search(frag.name or "")):
                    fragments.append(frag)

            # Look for class definitions
            elif token.type in declaration_types and token.value == "class":
                frag = self._extract_class_at(tokens, i, lines, file_path, pattern)
                if frag and (not name_re or name_re.search(frag.name or "")):
                    fragments.append(frag)

            # Look for const/let/var arrow functions (rosettes uses KEYWORD_DECLARATION)
            elif token.type in declaration_types and token.value in (
                "const",
                "let",
                "var",
            ):
                frag = self._extract_arrow_at(tokens, i, lines, file_path, pattern)
                if frag and (not name_re or name_re.search(frag.name or "")):
                    fragments.append(frag)

            i += 1

        return fragments

    def _extract_structure(
        self,
        tokens: list,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> list[CodeFragment]:
        """Extract imports and exports for structural overview."""
        fragments: list[CodeFragment] = []

        # Token types for namespace keywords (import/export)
        namespace_types = {TokenType.KEYWORD, TokenType.KEYWORD_NAMESPACE}

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Import statements (rosettes uses KEYWORD_NAMESPACE for import/export)
            if token.type in namespace_types and token.value == "import":
                frag = self._extract_import_at(tokens, i, lines, file_path)
                if frag:
                    fragments.append(frag)

            # Export statements
            elif token.type in namespace_types and token.value == "export":
                frag = self._extract_export_at(tokens, i, lines, file_path)
                if frag:
                    fragments.append(frag)

            i += 1

        return fragments

    def _extract_function_at(
        self,
        tokens: list,
        start_idx: int,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> CodeFragment | None:
        """Extract function definition starting at token index."""
        token = tokens[start_idx]
        line_num = token.line

        # Skip 'async' to get to 'function'
        i = start_idx
        if tokens[i].value == "async":
            i += 1
            while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
                i += 1
            if i >= len(tokens) or tokens[i].value != "function":
                return None

        # Move past 'function' keyword
        i += 1
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        # Get function name
        if i >= len(tokens):
            return None

        name = None
        if tokens[i].type == TokenType.NAME:
            name = tokens[i].value

        if not name:
            return None

        # Extract the line as signature
        if 0 < line_num <= len(lines):
            signature = lines[line_num - 1].strip()
        else:
            signature = f"function {name}(...)"

        content = signature if not pattern.extract_body else self._extract_block(
            lines, line_num
        )

        return CodeFragment(
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            content=content,
            fragment_type="function",
            name=name,
            signature=signature,
        )

    def _extract_class_at(
        self,
        tokens: list,
        start_idx: int,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> CodeFragment | None:
        """Extract class definition starting at token index."""
        token = tokens[start_idx]
        line_num = token.line

        i = start_idx + 1
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        if i >= len(tokens):
            return None

        name = None
        if tokens[i].type == TokenType.NAME:
            name = tokens[i].value

        if not name:
            return None

        if 0 < line_num <= len(lines):
            signature = lines[line_num - 1].strip()
        else:
            signature = f"class {name}"

        content = signature if not pattern.extract_body else self._extract_block(
            lines, line_num
        )

        return CodeFragment(
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            content=content,
            fragment_type="class",
            name=name,
            signature=signature,
        )

    def _extract_arrow_at(
        self,
        tokens: list,
        start_idx: int,
        lines: list[str],
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> CodeFragment | None:
        """Extract arrow function (const foo = () => ...) at token index."""
        token = tokens[start_idx]
        line_num = token.line

        i = start_idx + 1
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        if i >= len(tokens):
            return None

        name = None
        if tokens[i].type == TokenType.NAME:
            name = tokens[i].value

        if not name:
            return None

        # Check if there's an arrow (=>) on the SAME line indicating arrow function
        # This prevents false positives like "const X = 13" when next line has "=>"
        has_arrow = False
        for j in range(i, min(i + 30, len(tokens))):
            if tokens[j].line > line_num:  # Only check same line
                break
            if tokens[j].type == TokenType.OPERATOR and tokens[j].value == "=>":
                has_arrow = True
                break

        if not has_arrow:
            return None

        if 0 < line_num <= len(lines):
            signature = lines[line_num - 1].strip()
        else:
            signature = f"const {name} = ..."

        content = signature if not pattern.extract_body else self._extract_block(
            lines, line_num
        )

        return CodeFragment(
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            content=content,
            fragment_type="arrow_function",
            name=name,
            signature=signature,
        )

    def _extract_import_at(
        self,
        tokens: list,
        start_idx: int,
        lines: list[str],
        file_path: Path,
    ) -> CodeFragment | None:
        """Extract import statement."""
        token = tokens[start_idx]
        line_num = token.line

        if 0 < line_num <= len(lines):
            content = lines[line_num - 1].strip()
        else:
            content = "import ..."

        return CodeFragment(
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            content=content,
            fragment_type="import",
            name=None,
            signature=content,
        )

    def _extract_export_at(
        self,
        tokens: list,
        start_idx: int,
        lines: list[str],
        file_path: Path,
    ) -> CodeFragment | None:
        """Extract export statement."""
        token = tokens[start_idx]
        line_num = token.line

        if 0 < line_num <= len(lines):
            content = lines[line_num - 1].strip()
        else:
            content = "export ..."

        return CodeFragment(
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            content=content,
            fragment_type="export",
            name=None,
            signature=content,
        )

    def _extract_block(self, lines: list[str], start_line: int) -> str:
        """Extract a code block starting at line (basic brace matching)."""
        if start_line < 1 or start_line > len(lines):
            return ""

        result_lines: list[str] = []
        brace_count = 0
        started = False

        for i in range(start_line - 1, min(start_line + 100, len(lines))):
            line = lines[i]
            result_lines.append(line)

            brace_count += line.count("{") - line.count("}")

            if "{" in line:
                started = True

            if started and brace_count <= 0:
                break

        return "\n".join(result_lines)


# =============================================================================
# Extractor Registry
# =============================================================================


class ExtractorRegistry:
    """Registry that maps file types to extractors."""

    def __init__(self) -> None:
        self._extractors: list[LanguageExtractor] = []

    def register(self, extractor: LanguageExtractor) -> None:
        """Register an extractor."""
        self._extractors.append(extractor)

    def get_extractor(self, file_path: Path) -> LanguageExtractor | None:
        """Get the appropriate extractor for a file."""
        for extractor in self._extractors:
            if extractor.can_handle(file_path):
                return extractor
        return None

    def extract(
        self,
        file_path: Path,
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract from a file using the appropriate extractor."""
        extractor = self.get_extractor(file_path)
        if extractor is None:
            return ExtractionResult()
        return extractor.extract(file_path, pattern)

    def extract_multi(
        self,
        file_paths: list[Path],
        pattern: ExtractionPattern,
    ) -> ExtractionResult:
        """Extract from multiple files."""
        combined = ExtractionResult()
        for path in file_paths:
            result = self.extract(path, pattern)
            combined.fragments.extend(result.fragments)
            combined.files_parsed += result.files_parsed
            combined.total_file_lines += result.total_file_lines
            combined.parse_time_ms += result.parse_time_ms
        return combined


# =============================================================================
# Magnetic Analyzer
# =============================================================================


class MagneticAnalyzer:
    """Analyze repositories using magnetic search techniques.

    Wraps graph builders and extractors to produce comprehensive analysis.
    Supports Python (via ast) and JS/TS/Svelte (via rosettes tokenization).
    """

    # File extensions handled by each extractor
    PYTHON_EXTENSIONS = {".py", ".pyi"}
    JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".svelte", ".vue", ".mjs", ".mts"}

    def __init__(self) -> None:
        self._graph_builder = PythonGraphBuilder()
        self._py_extractor = PythonExtractor()
        self._js_extractor = RosettesExtractor()
        self._registry = ExtractorRegistry()
        self._registry.register(self._py_extractor)
        self._registry.register(self._js_extractor)

    def analyze(
        self,
        repo: FetchedRepo,
        intent: ResearchIntent = ResearchIntent.ARCHITECTURE,
    ) -> RepoAnalysis:
        """Analyze a fetched repository.

        Args:
            repo: Repository with local clone.
            intent: Research intent guiding extraction.

        Returns:
            Analysis results including graph and patterns.
        """
        # Separate files by language
        python_files = [
            f for f in repo.files if f.suffix.lower() in self.PYTHON_EXTENSIONS
        ]
        js_files = [f for f in repo.files if f.suffix.lower() in self.JS_EXTENSIONS]

        # Build code graph from Python (JS graph building not implemented yet)
        graph = self._graph_builder.build_from_files(python_files)

        # Extract structure based on intent from ALL supported files
        pattern = self._intent_to_pattern(intent)
        all_files = python_files + js_files
        extraction = self._registry.extract_multi(all_files, pattern)

        # Identify key files
        key_files = self._identify_key_files(repo)

        # Detect patterns
        patterns = self._detect_patterns(repo, graph)

        return RepoAnalysis(
            repo=repo,
            graph=graph,
            structure=tuple(extraction.fragments),
            key_files=tuple(key_files),
            patterns=tuple(patterns),
        )

    def _intent_to_pattern(self, intent: ResearchIntent) -> ExtractionPattern:
        """Convert research intent to extraction pattern."""
        match intent:
            case ResearchIntent.ARCHITECTURE:
                # Use DEFINITION to get functions/classes in JS/TS/Svelte
                # (STRUCTURE only extracts imports/exports there)
                return ExtractionPattern(
                    intent=Intent.DEFINITION,
                    entities=(),
                    extract_body=False,  # Just signatures for architecture
                    extract_docstring=True,
                    extract_signature=True,
                )
            case ResearchIntent.PATTERNS:
                return ExtractionPattern(
                    intent=Intent.DEFINITION,
                    entities=(),
                    extract_body=True,
                    extract_docstring=True,
                    extract_signature=True,
                )
            case ResearchIntent.EXAMPLES:
                return ExtractionPattern(
                    intent=Intent.DEFINITION,
                    entities=(),
                    extract_body=True,
                    extract_docstring=True,
                    extract_signature=True,
                )
            case _:
                return ExtractionPattern(
                    intent=Intent.STRUCTURE,
                    entities=(),
                    extract_body=False,
                    extract_docstring=True,
                    extract_signature=True,
                )

    def _identify_key_files(self, repo: FetchedRepo) -> list[Path]:
        """Identify key/entry point files in the repository."""
        key_files: list[Path] = []
        key_names = {
            "main.py",
            "app.py",
            "__main__.py",
            "cli.py",
            "server.py",
            "index.py",
            "setup.py",
            "pyproject.toml",
            "package.json",
            "index.ts",
            "index.js",
            "main.ts",
            "main.js",
            "app.ts",
            "app.js",
            "+page.svelte",
            "App.svelte",
        }

        for file_path in repo.files:
            if file_path.name in key_names:
                key_files.append(file_path)
            elif file_path.name == "__init__.py" and file_path.parent == repo.local_path / "src":
                key_files.append(file_path)

        return key_files

    def _detect_patterns(self, repo: FetchedRepo, graph: CodeGraph) -> list[str]:
        """Detect common patterns in the repository."""
        patterns: list[str] = []

        # Check for common directory structures
        dirs_present = {f.parent.name for f in repo.files}

        if "stores" in dirs_present or "store" in dirs_present:
            patterns.append("state-management:store-pattern")

        if "components" in dirs_present:
            patterns.append("ui:component-based")

        if "routes" in dirs_present:
            patterns.append("routing:file-based")

        if "api" in dirs_present:
            patterns.append("backend:api-layer")

        if "tests" in dirs_present or "test" in dirs_present:
            patterns.append("quality:has-tests")

        if "lib" in dirs_present:
            patterns.append("structure:lib-pattern")

        # Check graph for patterns
        stats = graph.stats()
        if stats["classes"] > 5:
            patterns.append("paradigm:oop")
        if stats["functions"] > 20 and stats["classes"] < 3:
            patterns.append("paradigm:functional")

        return patterns
