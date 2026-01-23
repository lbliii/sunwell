"""AST-aware chunking for Python files (RFC-108).

This is what makes Sunwell better than generic RAG:
- Chunks align with semantic boundaries (functions, classes)
- Docstrings extracted for better embedding quality
- Signatures included for precise retrieval
- Decorators kept with their functions
"""

import ast
from dataclasses import dataclass
from pathlib import Path

from sunwell.workspace.indexer import CodeChunk, _content_hash


@dataclass(frozen=True, slots=True)
class PythonChunk(CodeChunk):
    """Extended chunk with Python-specific metadata."""

    docstring: str | None = None
    """Extracted docstring for embedding boost."""

    signature: str | None = None
    """Function/method signature."""

    decorators: tuple[str, ...] = ()
    """Decorator names (e.g., '@dataclass', '@property')."""

    def to_embedding_text(self) -> str:
        """Text optimized for embedding (includes docstring prominently)."""
        parts: list[str] = []
        if self.name:
            parts.append(f"# {self.name}")
        if self.docstring:
            parts.append(f'"""{self.docstring}"""')
        if self.signature:
            parts.append(self.signature)
        parts.append(self.content)
        return "\n".join(parts)


class PythonASTChunker:
    """Chunk Python by semantic boundaries, not line counts.

    Extracts:
    - Functions (standalone)
    - Classes (with methods as one chunk, or summarized if large)
    - Module-level code (if no definitions found)
    """

    MIN_LINES = 3
    MAX_LINES = 150  # Allow larger chunks for classes

    def chunk(self, file_path: Path) -> list[CodeChunk]:
        """Parse and chunk a Python file.

        Args:
            file_path: Path to Python file.

        Returns:
            List of PythonChunk objects.
        """
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return []  # Invalid Python, skip

        lines = content.split("\n")
        chunks: list[CodeChunk] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                chunk = self._chunk_class(node, file_path, lines)
                if chunk:
                    chunks.append(chunk)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip methods (handled by class chunker)
                if not self._is_method(node, tree):
                    chunk = self._chunk_function(node, file_path, lines)
                    if chunk:
                        chunks.append(chunk)

        # If no definitions found, chunk the whole module
        if not chunks and len(lines) >= self.MIN_LINES:
            chunks.append(self._chunk_module(file_path, content, lines))

        return chunks

    def _chunk_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk | None:
        """Extract a function as a chunk."""
        # Find actual start (including decorators)
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)

        end_line = node.end_lineno or node.lineno

        if end_line - start_line + 1 < self.MIN_LINES:
            return None

        chunk_lines = lines[start_line - 1 : end_line]
        content = "\n".join(chunk_lines)

        return PythonChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            chunk_type="function",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=ast.get_docstring(node),
            signature=self._extract_signature(node, lines),
            decorators=tuple(self._decorator_name(d) for d in node.decorator_list),
        )

    def _chunk_class(
        self,
        node: ast.ClassDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk | None:
        """Extract a class as a chunk."""
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)

        end_line = node.end_lineno or node.lineno

        # For very large classes, chunk just the signature + docstring + method names
        if end_line - start_line > self.MAX_LINES:
            return self._chunk_class_summary(node, file_path, lines)

        chunk_lines = lines[start_line - 1 : end_line]
        content = "\n".join(chunk_lines)

        return PythonChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            chunk_type="class",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=ast.get_docstring(node),
            signature=f"class {node.name}",
            decorators=tuple(self._decorator_name(d) for d in node.decorator_list),
        )

    def _chunk_class_summary(
        self,
        node: ast.ClassDef,
        file_path: Path,
        lines: list[str],
    ) -> PythonChunk:
        """For large classes, create a summary chunk."""
        # Extract class definition line + docstring + method signatures
        summary_parts: list[str] = [lines[node.lineno - 1]]  # class Foo(Bar):

        docstring = ast.get_docstring(node)
        if docstring:
            summary_parts.append(f'    """{docstring}"""')

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._extract_signature(item, lines)
                if sig:
                    summary_parts.append(f"    {sig}")
                    summary_parts.append("        ...")

        content = "\n".join(summary_parts)

        return PythonChunk(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            content=content,
            chunk_type="class",
            name=node.name,
            _content_hash=_content_hash(content),
            docstring=docstring,
            signature=f"class {node.name} (summary)",
        )

    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
    ) -> str | None:
        """Extract function signature from source."""
        sig_lines: list[str] = []
        for i in range(node.lineno - 1, min(node.lineno + 5, len(lines))):
            line = lines[i]
            sig_lines.append(line)
            if line.rstrip().endswith(":"):
                break
        return "\n".join(sig_lines).strip() if sig_lines else None

    def _decorator_name(self, node: ast.expr) -> str:
        """Extract decorator name."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return "unknown"

    def _is_method(self, node: ast.FunctionDef, tree: ast.Module) -> bool:
        """Check if function is a method inside a class."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return True
        return False

    def _chunk_module(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
    ) -> PythonChunk:
        """Chunk entire module (no definitions found)."""
        return PythonChunk(
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            content=content,
            chunk_type="module",
            name=file_path.stem,
            _content_hash=_content_hash(content),
            docstring=None,
        )
