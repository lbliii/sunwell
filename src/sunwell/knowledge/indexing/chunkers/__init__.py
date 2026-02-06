"""Content-aware chunker registry (RFC-108).

Different content types require different chunking strategies
to preserve semantic meaning:
- Python: AST-aware (functions, classes)
- Prose: Paragraph-aware (sections, natural breaks)
- Scripts: Scene-aware (sluglines, beats)
- Docs: Heading-aware (sections, hierarchy)
"""

from pathlib import Path

from sunwell.knowledge.indexing.project_type import ProjectType, detect_file_type
from sunwell.knowledge.workspace.indexer import CodeChunk


class ChunkerRegistry:
    """Registry of content-type-specific chunkers.

    Automatically selects the appropriate chunking strategy based on
    project type and file extension.
    """

    def __init__(self) -> None:
        """Initialize chunker registry."""
        # Lazy-load chunkers to avoid circular imports
        self._python: object | None = None
        self._prose: object | None = None
        self._screenplay: object | None = None

    @property
    def python_chunker(self):
        """Get Python AST chunker (lazy-loaded)."""
        if self._python is None:
            from sunwell.knowledge.indexing.chunkers.python_ast import PythonASTChunker

            self._python = PythonASTChunker()
        return self._python

    @property
    def prose_chunker(self):
        """Get prose chunker (lazy-loaded)."""
        if self._prose is None:
            from sunwell.knowledge.indexing.chunkers.prose import ProseChunker

            self._prose = ProseChunker()
        return self._prose

    @property
    def screenplay_chunker(self):
        """Get screenplay chunker (lazy-loaded)."""
        if self._screenplay is None:
            from sunwell.knowledge.indexing.chunkers.screenplay import ScreenplayChunker

            self._screenplay = ScreenplayChunker()
        return self._screenplay

    def chunk_file(
        self,
        file_path: Path,
        project_type: ProjectType,
    ) -> list[CodeChunk]:
        """Chunk a file using the appropriate chunker.

        For MIXED projects, detects file type individually.

        Args:
            file_path: Path to the file to chunk.
            project_type: Project type (or MIXED for per-file detection).

        Returns:
            List of code chunks.
        """
        if project_type == ProjectType.MIXED:
            file_type = detect_file_type(file_path)
        else:
            file_type = project_type

        ext = file_path.suffix.lower()

        # Code files
        if ext == ".py":
            return self.python_chunker.chunk(file_path)
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            # JavaScript/TypeScript: Uses generic chunking (line-based)
            # Future: AST-based chunking using tree-sitter or babel parser
            # would provide better function/class boundary detection
            return self._generic_chunk(file_path)
        if ext in {".go", ".rs", ".java", ".kt", ".c", ".cpp"}:
            # Other languages: Uses generic chunking (line-based)
            # Future: tree-sitter parsers for proper AST-based chunking
            return self._generic_chunk(file_path)

        # Screenplay files
        if ext in {".fountain", ".fdx", ".highland"}:
            return self.screenplay_chunker.chunk(file_path)

        # Prose/docs (markdown, text)
        if file_type == ProjectType.PROSE:
            return self.prose_chunker.chunk(file_path)
        if file_type == ProjectType.SCRIPT:
            # Check if it looks like a screenplay
            if self._looks_like_screenplay(file_path):
                return self.screenplay_chunker.chunk(file_path)
            return self.prose_chunker.chunk(file_path)

        # Documentation and default
        return self._generic_chunk(file_path)

    def _looks_like_screenplay(self, file_path: Path) -> bool:
        """Check if a markdown file looks like a screenplay."""
        try:
            content = file_path.read_text()[:1000]
            return "INT." in content or "EXT." in content
        except Exception:
            return False

    def _generic_chunk(self, file_path: Path, chunk_size: int = 50) -> list[CodeChunk]:
        """Generic line-based chunking with overlap.

        Args:
            file_path: Path to the file.
            chunk_size: Lines per chunk.

        Returns:
            List of code chunks.
        """
        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return []

        lines = content.split("\n")
        if len(lines) < 3:
            return []

        chunks: list[CodeChunk] = []
        overlap = 10

        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i : i + chunk_size]
            if len(chunk_lines) < 3:
                continue

            chunk_content = "\n".join(chunk_lines)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=i + len(chunk_lines),
                    content=chunk_content,
                    chunk_type="block",
                )
            )

        return chunks


# Singleton instance
_registry: ChunkerRegistry | None = None


def get_chunker_registry() -> ChunkerRegistry:
    """Get the global chunker registry."""
    global _registry
    if _registry is None:
        _registry = ChunkerRegistry()
    return _registry
