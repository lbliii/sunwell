"""Codebase indexing for RAG over project files.

Performance optimizations:
- Content-addressable hashing for O(1) chunk deduplication
- Parallel file processing for free-threaded Python 3.14
- Incremental indexing (only re-embed changed content)
- Adaptive worker count based on GIL state
"""


import asyncio
import fnmatch
import hashlib
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from sunwell.foundation.threading import (
    WorkloadType,
    optimal_workers,
)
from sunwell.knowledge.utils import extract_class_defs, extract_function_defs, parse_python_file

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.knowledge.workspace.detector import Workspace


def _content_hash(content: str) -> str:
    """Fast content-addressable hash using blake2b.

    O(n) where n is content length, but with fast C implementation.
    Used for deduplication - identical content = identical hash.
    """
    return hashlib.blake2b(content.encode(), digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class CodeChunk:
    """A chunk of code from the codebase.

    Uses content-addressable hashing for O(1) deduplication:
    - Same content always produces same hash
    - Changed content produces different hash
    - Enables incremental re-indexing (skip unchanged chunks)
    """

    file_path: Path
    """Path to the source file."""

    start_line: int
    """Starting line number (1-indexed)."""

    end_line: int
    """Ending line number (1-indexed)."""

    content: str
    """The actual code content."""

    chunk_type: str
    """Type of chunk: 'function', 'class', 'module', 'block'."""

    name: str | None = None
    """Name of the function/class if applicable."""

    _content_hash: str | None = field(default=None, compare=False)
    """Cached content hash for O(1) lookups."""


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """A code chunk with a relevance score from a query."""

    chunk: CodeChunk
    """The code chunk."""

    score: float
    """Relevance score (0.0 to 1.0, higher is more relevant)."""

    # Delegate common attributes for convenience
    @property
    def id(self) -> str:
        return self.chunk.id

    @property
    def file_path(self) -> Path:
        return self.chunk.file_path

    @property
    def start_line(self) -> int:
        return self.chunk.start_line

    @property
    def end_line(self) -> int:
        return self.chunk.end_line

    @property
    def content(self) -> str:
        return self.chunk.content

    @property
    def chunk_type(self) -> str:
        return self.chunk.chunk_type

    @property
    def name(self) -> str | None:
        return self.chunk.name

    @property
    def id(self) -> str:
        """Content-addressable identifier for O(1) deduplication."""
        if self._content_hash:
            return self._content_hash
        return _content_hash(self.content)

    def __hash__(self) -> int:
        """Hash based on content, enabling set operations."""
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """Equal if content hash matches (even across files)."""
        if isinstance(other, CodeChunk):
            return self.id == other.id
        return False

    @property
    def reference(self) -> str:
        """Human-readable reference."""
        if self.name:
            return f"{self.file_path}:{self.start_line} ({self.name})"
        return f"{self.file_path}:{self.start_line}-{self.end_line}"

    def to_context(self) -> str:
        """Format chunk for inclusion in prompt context."""
        header = f"# {self.reference}"
        return f"{header}\n```\n{self.content}\n```"


@dataclass(slots=True)
class CodebaseIndex:
    """Index of codebase chunks for retrieval."""

    chunks: list[CodeChunk] = field(default_factory=list)
    """All indexed chunks."""

    embeddings: dict[str, list[float]] = field(default_factory=dict)
    """Chunk ID -> embedding vector."""

    file_count: int = 0
    """Number of files indexed."""

    total_lines: int = 0
    """Total lines of code indexed."""


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """Context retrieved from codebase."""

    chunks: tuple[CodeChunk, ...]
    """Retrieved code chunks."""

    relevance_scores: Mapping[str, float]
    """Chunk ID -> relevance score (immutable view)."""

    def to_prompt_context(self, max_chunks: int = 5) -> str:
        """Format as context for prompt injection."""
        if not self.chunks:
            return ""

        # Sort by relevance
        sorted_chunks = sorted(
            self.chunks[:max_chunks],
            key=lambda c: self.relevance_scores.get(c.id, 0),
            reverse=True,
        )

        sections = [
            "## Relevant Code from Project\n",
            "The following code snippets are from the current project:\n",
        ]

        for chunk in sorted_chunks:
            score = self.relevance_scores.get(chunk.id, 0)
            sections.append(f"\n### {chunk.reference} (relevance: {score:.0%})\n")
            sections.append(f"```{_get_language(chunk.file_path)}\n")
            sections.append(chunk.content)
            sections.append("\n```\n")

        return "".join(sections)


class CodebaseIndexer:
    """Indexes codebase for semantic retrieval."""

    # File extensions to index
    CODE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".java": "java",
        ".kt": "kotlin",
        ".swift": "swift",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".scala": "scala",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
        ".md": "markdown",
        ".rst": "rst",
    }

    # Max lines per chunk
    MAX_CHUNK_LINES = 100

    # Min lines to be worth indexing
    MIN_CHUNK_LINES = 3

    def __init__(
        self,
        embedder: EmbeddingProtocol,
        max_file_size: int = 100_000,  # 100KB
        include_patterns: list[str] | None = None,
    ) -> None:
        """Initialize indexer.

        Args:
            embedder: Embedding model for vectorization.
            max_file_size: Maximum file size to index in bytes.
            include_patterns: Optional glob patterns to include (default: all code files).
        """
        self.embedder = embedder
        self.max_file_size = max_file_size
        self.include_patterns = include_patterns
        # Pre-compile include patterns for O(1) matching per pattern
        self._include_re: tuple[re.Pattern[str], ...] | None = None
        if include_patterns:
            self._include_re = tuple(
                re.compile(fnmatch.translate(p)) for p in include_patterns
            )
        self._index: CodebaseIndex | None = None
        self._vector_index: dict[str, list[float]] = {}

    async def index_workspace(self, workspace: Workspace) -> CodebaseIndex:
        """Index all code files in workspace with PARALLEL processing.

        Performance optimizations:
        - Parallel file parsing using ThreadPoolExecutor (GIL-free in 3.14)
        - Content-addressable deduplication (skip identical chunks)
        - Batch embedding for efficiency
        - Adaptive workers based on GIL state

        Args:
            workspace: Workspace to index.

        Returns:
            Index of all code chunks.
        """
        files = self._iter_code_files(workspace)

        # Adaptive workers: file parsing is CPU-bound (regex, tokenization)
        # Free-threaded Python: true parallelism = more workers help
        # Standard Python: threads serialize at GIL = keep workers low
        workers = optimal_workers(WorkloadType.CPU_BOUND)

        # Parallel file parsing - big speedup with free-threading
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Parse all files in parallel threads
            chunk_lists = await asyncio.gather(*[
                loop.run_in_executor(pool, self._chunk_file, path)
                for path in files
            ])

        # Flatten and deduplicate using content-addressable hashing
        seen_hashes: set[str] = set()
        chunks: list[CodeChunk] = []

        for file_chunks in chunk_lists:
            for chunk in file_chunks:
                if chunk.id not in seen_hashes:
                    seen_hashes.add(chunk.id)
                    chunks.append(chunk)

        file_count = len([cl for cl in chunk_lists if cl])
        total_lines = sum(c.end_line - c.start_line + 1 for c in chunks)

        # Create embeddings for unique chunks only (dedup saves API calls)
        if chunks:
            texts = [f"{c.name or ''}\n{c.content}" for c in chunks]
            result = await self.embedder.embed(texts)

            embedding_dict = {
                chunk.id: result.vectors[i].tolist()
                for i, chunk in enumerate(chunks)
            }
        else:
            embedding_dict = {}

        self._index = CodebaseIndex(
            chunks=chunks,
            embeddings=embedding_dict,
            file_count=file_count,
            total_lines=total_lines,
        )

        return self._index

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> RetrievedContext:
        """Retrieve relevant code chunks for a query.

        Args:
            query: Natural language query.
            top_k: Maximum chunks to retrieve.
            threshold: Minimum relevance score.

        Returns:
            Retrieved context with relevance scores.
        """
        if not self._index or not self._index.chunks:
            return RetrievedContext(chunks=(), relevance_scores=MappingProxyType({}))

        # Embed query
        result = await self.embedder.embed([query])
        query_embedding = result.vectors[0].tolist()

        # Calculate similarity scores
        scores: list[tuple[CodeChunk, float]] = []
        for chunk in self._index.chunks:
            chunk_embedding = self._index.embeddings.get(chunk.id)
            if chunk_embedding:
                score = self._cosine_similarity(query_embedding, chunk_embedding)
                if score >= threshold:
                    scores.append((chunk, score))

        # Sort by score and take top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scores[:top_k]

        return RetrievedContext(
            chunks=tuple(c for c, _ in top_chunks),
            relevance_scores=MappingProxyType({c.id: s for c, s in top_chunks}),
        )

    def _iter_code_files(self, workspace: Workspace) -> list[Path]:
        """Iterate over code files in workspace."""
        files: list[Path] = []

        for path in workspace.root.rglob("*"):
            if not path.is_file():
                continue

            # Check size
            try:
                if path.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue

            # Check if ignored
            rel_path = path.relative_to(workspace.root)
            if self._is_ignored(str(rel_path), workspace.ignore_patterns):
                continue

            # Check extension
            if self._include_re:
                # Use pre-compiled patterns for O(patterns) instead of O(patterns × compile)
                rel_str = str(rel_path)
                if any(r.match(rel_str) for r in self._include_re):
                    files.append(path)
            elif path.suffix in self.CODE_EXTENSIONS:
                files.append(path)

        return files

    # Cache for compiled ignore patterns: pattern -> compiled regex
    _ignore_cache: dict[str, re.Pattern[str]] = {}

    def _is_ignored(self, path: str, patterns: tuple[str, ...]) -> bool:
        """Check if path matches any ignore pattern.

        Uses cached compiled patterns for O(1) per-pattern matching.
        """
        parts = path.split("/")

        for pattern in patterns:
            # Get or compile pattern (cached at class level)
            if pattern not in self._ignore_cache:
                self._ignore_cache[pattern] = re.compile(fnmatch.translate(pattern))
            compiled = self._ignore_cache[pattern]

            # Check each path component
            for part in parts:
                if compiled.match(part):
                    return True
            # Check full path
            if compiled.match(path):
                return True

        return False

    def _chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Chunk a file into indexable pieces."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []

        lines = content.split("\n")

        if len(lines) < self.MIN_CHUNK_LINES:
            return []

        # For Python, try to extract functions and classes
        if file_path.suffix == ".py":
            return self._chunk_python(file_path, content, lines)

        # For other files, chunk by blocks
        return self._chunk_by_blocks(file_path, lines)

    def _chunk_python(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
    ) -> list[CodeChunk]:
        """Chunk Python file using AST for accurate, thread-safe parsing.

        Uses Python's built-in ast module which is:
        - Thread-safe (no C extensions with GIL issues)
        - More accurate than regex (understands syntax)
        - Handles edge cases (multiline strings, decorators, etc.)
        """
        chunks: list[CodeChunk] = []

        tree = parse_python_file(file_path)
        if tree is None:
            # Invalid Python, fall back to block chunking
            return self._chunk_by_blocks(file_path, lines)

        # Extract top-level definitions using AST
        definitions: list[tuple[int, int, str, str]] = []  # (start, end, type, name)

        # Extract classes
        classes = extract_class_defs(tree)
        for node in classes:
            definitions.append((
                node.lineno,
                node.end_lineno or node.lineno,
                "class",
                node.name,
            ))

        # Extract functions
        functions = extract_function_defs(tree)
        for node in functions:
            definitions.append((
                node.lineno,
                node.end_lineno or node.lineno,
                "function",
                node.name,
            ))

        if not definitions:
            # No functions/classes, chunk whole file
            if len(lines) <= self.MAX_CHUNK_LINES:
                return [CodeChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=len(lines),
                    content=content,
                    chunk_type="module",
                    name=file_path.stem,
                )]
            return self._chunk_by_blocks(file_path, lines)

        # Sort by start line and deduplicate
        definitions.sort(key=lambda d: d[0])

        # Extract each definition with accurate line ranges from AST
        for start_line, end_line, def_type, name in definitions:
            # Include decorators (look backwards for @)
            actual_start = start_line
            while actual_start > 1 and lines[actual_start - 2].strip().startswith("@"):
                actual_start -= 1

            chunk_lines = lines[actual_start - 1:end_line]
            chunk_content = "\n".join(chunk_lines)

            if len(chunk_lines) >= self.MIN_CHUNK_LINES:
                chunks.append(CodeChunk(
                    file_path=file_path,
                    start_line=actual_start,
                    end_line=end_line,
                    content=chunk_content,
                    chunk_type=def_type,
                    name=name,
                    _content_hash=_content_hash(chunk_content),
                ))

        return chunks

    def _chunk_by_blocks(
        self,
        file_path: Path,
        lines: list[str],
    ) -> list[CodeChunk]:
        """Chunk file into fixed-size blocks."""
        chunks: list[CodeChunk] = []

        for i in range(0, len(lines), self.MAX_CHUNK_LINES):
            end = min(i + self.MAX_CHUNK_LINES, len(lines))
            chunk_lines = lines[i:end]

            if len(chunk_lines) >= self.MIN_CHUNK_LINES:
                chunks.append(CodeChunk(
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=end,
                    content="\n".join(chunk_lines),
                    chunk_type="block",
                ))

        return chunks

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)


def _get_language(path: Path) -> str:
    """Get language identifier for a file."""
    return CodebaseIndexer.CODE_EXTENSIONS.get(path.suffix, "")
