"""Background codebase indexing service (RFC-108).

Provides always-on semantic search without blocking user interaction.

Supports tiered indexing for multi-project workspaces:
- L0: Manifest - Project list, roles, dependencies (instant)
- L1: Signatures - Exports, public APIs, types (lightweight)
- L2: Full - Everything in active project (on focus)
- L3: Deep - Cross-project detailed search (on demand)
"""

import asyncio
import hashlib
import pickle
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.knowledge.embedding import EmbeddingProtocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sunwell.foundation.utils import safe_json_dumps, safe_json_loads
from sunwell.knowledge.indexing.chunkers import ChunkerRegistry
from sunwell.knowledge.indexing.metrics import IndexMetrics
from sunwell.knowledge.indexing.priority import get_priority_files
from sunwell.knowledge.indexing.project_type import ProjectType, detect_project_type
from sunwell.knowledge.workspace.indexer import CodebaseIndex, CodeChunk
from sunwell.knowledge.workspace.types import IndexTier


class IndexState(Enum):
    """Index service state machine."""

    NO_INDEX = "no_index"
    CHECKING = "checking"
    LOADING = "loading"
    BUILDING = "building"
    VERIFYING = "verifying"
    READY = "ready"
    UPDATING = "updating"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass(slots=True)
class IndexStatus:
    """Current status of the indexing service."""

    state: IndexState
    project_type: ProjectType = ProjectType.UNKNOWN
    progress: int = 0  # 0-100
    current_file: str | None = None
    chunk_count: int = 0
    file_count: int = 0
    last_updated: datetime | None = None
    error: str | None = None
    fallback_reason: str | None = None
    priority_complete: bool = False
    estimated_time_ms: int | None = None
    tier: IndexTier = IndexTier.L2_FULL
    """Current indexing tier (L0-L3)."""

    def to_json(self) -> dict[str, str | int | bool | None]:
        """Export status as JSON-serializable dict."""
        return {
            "state": self.state.value,
            "project_type": self.project_type.value,
            "progress": self.progress,
            "current_file": self.current_file,
            "chunk_count": self.chunk_count,
            "file_count": self.file_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "error": self.error,
            "fallback_reason": self.fallback_reason,
            "priority_complete": self.priority_complete,
            "estimated_time_ms": self.estimated_time_ms,
            "tier": self.tier.value,
        }


@dataclass(slots=True)
class IndexingService:
    """Background codebase indexing service.

    Lifecycle:
    1. start() → Check cache → Load or build
    2. watch_files() → Queue changes → Debounce → Update
    3. query() → Search index → Return results
    4. stop() → Cleanup

    Features:
    - Priority indexing (hot files first)
    - AST-aware chunking (Python)
    - Graceful fallback (grep when no embeddings)
    - File watching (incremental updates)
    - Tiered indexing (L0-L3) for multi-project scalability

    Index Tiers:
    - L0_MANIFEST: No embedding, just metadata (instant)
    - L1_SIGNATURES: Only public APIs, exports, types (lightweight)
    - L2_FULL: Complete indexing of all code (default for active project)
    - L3_DEEP: Cross-project deep search (on-demand)
    """

    workspace_root: Path
    cache_dir: Path = field(init=False)

    # Optional injected embedder (if None, creates one internally)
    embedder: object | None = None

    # Indexing tier (determines depth of indexing)
    tier: IndexTier = IndexTier.L2_FULL
    """Indexing tier: L0=manifest, L1=signatures, L2=full, L3=deep."""

    # Configuration
    debounce_ms: int = 500
    max_file_size: int = 100_000
    priority_file_limit: int = 200

    # Supported extensions (code + prose + scripts + docs)
    index_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            # Code
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
            ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs",
            # Config
            ".yaml", ".yml", ".toml", ".json",
            # Documentation
            ".md", ".rst", ".mdx", ".adoc",
            # Prose
            ".txt", ".rtf",
            # Screenplays
            ".fountain", ".fdx", ".highland",
        })
    )

    # Extensions for L1 signature-only indexing (just code, not docs)
    signature_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
            ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs",
        })
    )

    # State
    _status: IndexStatus = field(
        default_factory=lambda: IndexStatus(state=IndexState.NO_INDEX)
    )
    _index: CodebaseIndex | None = field(default=None, init=False)
    _embedder: object | None = field(default=None, init=False)
    _ready: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _pending_updates: set[Path] = field(default_factory=set, init=False)
    _update_task: asyncio.Task | None = field(default=None, init=False)
    _watch_task: asyncio.Task | None = field(default=None, init=False)

    # Project detection
    _project_type: ProjectType = field(default=ProjectType.UNKNOWN, init=False)

    # Content-aware chunking
    _chunker_registry: ChunkerRegistry = field(
        default_factory=ChunkerRegistry, init=False
    )

    # Metrics
    _metrics: IndexMetrics = field(default_factory=IndexMetrics, init=False)

    # Callbacks
    on_status_change: Callable[[IndexStatus], None] | None = None

    def __post_init__(self) -> None:
        """Initialize computed fields."""
        self.cache_dir = self.workspace_root / ".sunwell" / "index"

    @property
    def status(self) -> IndexStatus:
        """Get current status."""
        return self._status

    def get_status(self) -> IndexStatus:
        """Get current status (method variant for compatibility)."""
        return self._status

    @property
    def metrics(self) -> IndexMetrics:
        """Get metrics."""
        return self._metrics

    @property
    def project_type(self) -> ProjectType:
        """Get detected project type."""
        return self._project_type

    @property
    def is_ready(self) -> bool:
        """Check if index is ready for queries."""
        return self._status.state in (IndexState.READY, IndexState.UPDATING)

    def _update_status(self, **kwargs) -> None:
        """Update status and notify listeners."""
        for key, value in kwargs.items():
            if hasattr(self._status, key):
                setattr(self._status, key, value)
        if self.on_status_change:
            self.on_status_change(self._status)

    async def start(self) -> None:
        """Start the indexing service.

        Behavior varies by tier:
        - L0_MANIFEST: No indexing, just loads metadata (instant)
        - L1_SIGNATURES: Index only public APIs/exports (lightweight, no file watching)
        - L2_FULL: Full indexing with file watching (default)
        - L3_DEEP: Same as L2 but may include cross-project context
        """
        self._update_status(state=IndexState.CHECKING, tier=self.tier)

        # L0: Manifest tier - no actual indexing needed
        if self.tier == IndexTier.L0_MANIFEST:
            self._update_status(state=IndexState.READY)
            self._ready.set()
            return

        # 0. Detect project type (code, prose, script, docs, mixed)
        self._project_type = detect_project_type(self.workspace_root)
        self._update_status(project_type=self._project_type)

        # 1. Try to load cached index
        if await self._load_cached_index():
            self._update_status(state=IndexState.VERIFYING)
            if await self._verify_cache_fresh():
                self._update_status(state=IndexState.READY)
                self._ready.set()
                self._metrics.record_cache_hit()
            else:
                # Cache stale, rebuild
                self._metrics.record_cache_miss()
                asyncio.create_task(self._background_index())
        else:
            # No cache, build from scratch
            asyncio.create_task(self._background_index())

        # 2. Start file watcher (only for L2/L3 - L1 is one-shot)
        if self.tier in (IndexTier.L2_FULL, IndexTier.L3_DEEP):
            self._watch_task = asyncio.create_task(self._watch_files())

    async def stop(self) -> None:
        """Stop the indexing service."""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for index to be ready (at least priority files).

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if ready, False if timeout.
        """
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
            return True
        except TimeoutError:
            return False

    async def query(
        self,
        text: str,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[CodeChunk]:
        """Query the index for relevant code.

        Args:
            text: Query text.
            top_k: Maximum chunks to return.
            threshold: Minimum relevance score.

        Returns:
            List of relevant code chunks.
        """
        import time

        start = time.perf_counter()

        if not self._index or not self._embedder:
            return []

        # Embed query
        result = await self._embedder.embed([text])
        query_vector = result.vectors[0].tolist()

        # Search
        scores: list[tuple[CodeChunk, float]] = []
        for chunk in self._index.chunks:
            chunk_embedding = self._index.embeddings.get(chunk.id)
            if chunk_embedding:
                score = self._cosine_similarity(query_vector, chunk_embedding)
                if score >= threshold:
                    scores.append((chunk, score))

        # Sort by score and take top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        chunks = [c for c, _ in scores[:top_k]]

        # Record metrics
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._metrics.record_query(elapsed_ms)

        return chunks

    async def _background_index(self) -> None:
        """Build index in background with priority files first.

        Behavior varies by tier:
        - L1_SIGNATURES: Only index signature files (public APIs)
        - L2_FULL: Full indexing (priority + remaining)
        - L3_DEEP: Same as L2 for single project
        """
        import time

        build_start = time.perf_counter()
        self._update_status(state=IndexState.BUILDING, progress=0)

        try:
            self._embedder = self.embedder or await self._create_embedder()

            if self._embedder:
                if self.tier == IndexTier.L1_SIGNATURES:
                    # L1: Only index signatures (public APIs, exports)
                    await self._index_signatures_only()
                    self._update_status(priority_complete=True)
                    self._ready.set()
                else:
                    # L2/L3: Full indexing
                    # Phase 1: Priority files (fast)
                    await self._index_priority_files()
                    self._update_status(priority_complete=True)
                    self._ready.set()  # Usable after priority phase

                    # Phase 2: Remaining files (background)
                    await self._index_remaining_files()

                await self._save_cache()

                # Record build time
                self._metrics.build_time_ms = int(
                    (time.perf_counter() - build_start) * 1000
                )
                self._metrics.last_build = datetime.now()
                self._metrics.chunk_count = self._status.chunk_count
                self._metrics.file_count = self._status.file_count

                self._update_status(
                    state=IndexState.READY,
                    last_updated=datetime.now(),
                )
            else:
                # No embedder available, use degraded mode
                self._update_status(
                    state=IndexState.DEGRADED,
                    fallback_reason="Embedder not available (install Ollama)",
                )
                self._ready.set()

        except Exception as e:
            self._update_status(
                state=IndexState.ERROR,
                error=str(e),
            )
            self._metrics.record_error(str(e))

    async def _index_signatures_only(self) -> None:
        """Index only public signatures (L1 tier).

        This is lightweight indexing for cross-project awareness.
        Only indexes public APIs, exports, and type definitions.
        """
        # Only index code files (not docs, prose, etc.)
        signature_files = [
            f for f in self._iter_indexable_files()
            if f.suffix in self.signature_extensions
        ]

        if not signature_files:
            return

        total = len(signature_files)
        chunks: list[CodeChunk] = []

        for i, file_path in enumerate(signature_files):
            try:
                rel_path = file_path.relative_to(self.workspace_root)
            except ValueError:
                rel_path = file_path

            self._update_status(
                progress=int((i / total) * 100),
                current_file=str(rel_path),
            )

            # Use signature-only chunking (public functions, classes, exports)
            file_chunks = self._chunk_file_signatures(file_path)
            chunks.extend(file_chunks)

            # Batch embed every 100 chunks for L1 (smaller batches than L2)
            if len(chunks) >= 100:
                await self._embed_chunks(chunks)
                chunks = []

        # Embed final batch
        if chunks and self._embedder:
            await self._embed_chunks(chunks)

    def _chunk_file_signatures(self, file_path: Path) -> list[CodeChunk]:
        """Extract only public signatures from a file.

        For L1 indexing - much lighter than full chunking.
        Only extracts:
        - Function/method signatures (not bodies)
        - Class definitions (not full implementation)
        - Exported constants and types
        """
        # For now, use the regular chunker but filter to functions/classes only
        # A dedicated signature extractor will be implemented in the next phase
        all_chunks = self._chunk_file(file_path)

        # Filter to only function and class chunks (signatures)
        return [
            c for c in all_chunks
            if c.chunk_type in ("function", "class", "module")
        ]

    async def _index_priority_files(self) -> None:
        """Index priority files first for fast startup.

        Priority files vary by project type:
        - Code: README, entry points, config files
        - Prose: outline, characters, first chapters
        - Scripts: treatment, beat sheet, script file
        - Docs: index, getting-started, overview
        """
        priority_files = get_priority_files(
            self.workspace_root,
            project_type=self._project_type,
            max_files=self.priority_file_limit,
        )

        if not priority_files:
            return

        total = len(priority_files)
        chunks: list[CodeChunk] = []

        for i, file_path in enumerate(priority_files):
            try:
                rel_path = file_path.relative_to(self.workspace_root)
            except ValueError:
                rel_path = file_path

            self._update_status(
                progress=int((i / total) * 50),  # 0-50% for priority
                current_file=str(rel_path),
            )

            file_chunks = self._chunk_file(file_path)
            chunks.extend(file_chunks)

        # Embed priority chunks
        if chunks and self._embedder:
            await self._embed_chunks(chunks)

    async def _index_remaining_files(self) -> None:
        """Index remaining files in background."""
        all_files = list(self._iter_indexable_files())
        priority_paths = set(
            get_priority_files(
                self.workspace_root,
                project_type=self._project_type,
                max_files=self.priority_file_limit,
            )
        )
        remaining = [f for f in all_files if f not in priority_paths]

        if not remaining:
            return

        total = len(remaining)
        chunks: list[CodeChunk] = []

        for i, file_path in enumerate(remaining):
            try:
                rel_path = file_path.relative_to(self.workspace_root)
            except ValueError:
                rel_path = file_path

            self._update_status(
                progress=50 + int((i / total) * 50),  # 50-100% for remaining
                current_file=str(rel_path),
            )

            file_chunks = self._chunk_file(file_path)
            chunks.extend(file_chunks)

            # Batch embed every 500 chunks to show progress
            if len(chunks) >= 500:
                await self._embed_chunks(chunks)
                chunks = []

        # Embed final batch
        if chunks and self._embedder:
            await self._embed_chunks(chunks)

    def _chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Chunk a file using the appropriate content-aware chunker.

        Automatically selects chunking strategy based on project type and file type:
        - Python: AST-aware (functions, classes)
        - Prose: Paragraph-aware (sections, natural breaks)
        - Scripts: Scene-aware (sluglines, beats)
        - Docs: Heading-aware (sections, hierarchy)
        """
        return self._chunker_registry.chunk_file(file_path, self._project_type)

    async def _embed_chunks(self, chunks: list[CodeChunk]) -> None:
        """Embed chunks and add to index."""
        import time

        if not self._embedder or not chunks:
            return

        embed_start = time.perf_counter()

        # Use embedding-optimized text for Python chunks
        texts: list[str] = []
        for c in chunks:
            if hasattr(c, "to_embedding_text"):
                texts.append(c.to_embedding_text())
            else:
                texts.append(c.content)

        result = await self._embedder.embed(texts)

        # Track embedding time
        self._metrics.embedding_time_ms += int(
            (time.perf_counter() - embed_start) * 1000
        )

        if self._index is None:
            self._index = CodebaseIndex()

        for chunk, vector in zip(chunks, result.vectors, strict=True):
            self._index.chunks.append(chunk)
            self._index.embeddings[chunk.id] = vector.tolist()

        # Update file count (unique files)
        unique_files = {c.file_path for c in self._index.chunks}
        self._index.file_count = len(unique_files)

        self._update_status(
            chunk_count=len(self._index.chunks),
            file_count=self._index.file_count,
        )

    async def _watch_files(self) -> None:
        """Watch for file changes."""
        ignore_dirs = {
            ".git",
            ".sunwell",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
        }

        try:
            from watchfiles import awatch

            async for changes in awatch(
                self.workspace_root,
                recursive=True,
            ):
                for _change_type, path_str in changes:
                    path = Path(path_str)

                    # Skip ignored directories
                    if any(d in path.parts for d in ignore_dirs):
                        continue

                    # Filter to indexable files
                    if path.suffix not in self.index_extensions:
                        continue

                    self._pending_updates.add(path)

                # Debounce: schedule batch update
                if self._update_task is None or self._update_task.done():
                    self._update_task = asyncio.create_task(self._debounced_update())
        except ImportError:
            # watchfiles not available, fall back to no watching
            pass
        except Exception:
            # Watch failed, continue without watching
            pass

    async def _debounced_update(self) -> None:
        """Apply pending updates after debounce period."""
        await asyncio.sleep(self.debounce_ms / 1000)

        if not self._pending_updates:
            return

        paths = list(self._pending_updates)
        self._pending_updates.clear()

        prev_state = self._status.state
        self._update_status(state=IndexState.UPDATING)

        await self._update_files(paths)

        self._update_status(state=prev_state, last_updated=datetime.now())

    async def _update_files(self, paths: list[Path]) -> None:
        """Incrementally update index for changed files."""
        if not self._index or not self._embedder:
            return

        for path in paths:
            # Remove old chunks for this file
            self._index.chunks = [
                c for c in self._index.chunks if c.file_path != path
            ]
            # Remove old embeddings
            for chunk_id in list(self._index.embeddings.keys()):
                # Chunk IDs include file info, so we filter
                if not any(c.id == chunk_id for c in self._index.chunks):
                    del self._index.embeddings[chunk_id]

            # Re-chunk and embed if file exists
            if path.exists():
                chunks = self._chunk_file(path)
                if chunks:
                    await self._embed_chunks(chunks)

        await self._save_cache()

    async def _create_embedder(self) -> EmbeddingProtocol | None:
        """Create embedder with graceful fallback."""
        try:
            from sunwell.knowledge.embedding import create_embedder

            return create_embedder(prefer_local=True, fallback=True)
        except Exception:
            return None

    def _iter_indexable_files(self) -> Iterator[Path]:
        """Iterate over files to index."""
        ignore_dirs = {
            ".git",
            ".sunwell",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        }

        for path in self.workspace_root.rglob("*"):
            if path.is_file() and path.suffix in self.index_extensions:
                if not any(d in path.parts for d in ignore_dirs):
                    try:
                        if path.stat().st_size <= self.max_file_size:
                            yield path
                    except OSError:
                        continue

    async def _load_cached_index(self) -> bool:
        """Try to load index from cache."""
        cache_file = self.cache_dir / "index.pickle"
        meta_file = self.cache_dir / "meta.json"

        if not cache_file.exists() or not meta_file.exists():
            return False

        try:
            with open(cache_file, "rb") as f:
                self._index = pickle.load(f)

            meta = safe_json_loads(meta_file.read_text())
            self._update_status(
                chunk_count=meta.get("chunk_count", 0),
                file_count=meta.get("file_count", 0),
                last_updated=datetime.fromisoformat(meta.get("updated_at", "")),
            )

            self._embedder = self.embedder or await self._create_embedder()
            return True
        except Exception:
            return False

    async def _verify_cache_fresh(self) -> bool:
        """Check if cached index is still fresh."""
        meta_file = self.cache_dir / "meta.json"

        try:
            meta = safe_json_loads(meta_file.read_text())
            cached_hash = meta.get("content_hash")
            current_hash = self._compute_content_hash()
            return cached_hash == current_hash
        except Exception:
            return False

    def _compute_content_hash(self) -> str:
        """Compute hash of all indexable file mtimes."""
        mtimes: list[str] = []
        for path in sorted(self._iter_indexable_files()):
            try:
                mtimes.append(f"{path}:{path.stat().st_mtime}")
            except OSError:
                continue

        return hashlib.md5("\n".join(mtimes).encode()).hexdigest()

    async def _save_cache(self) -> None:
        """Save index to cache."""
        if not self._index:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Save index
        with open(self.cache_dir / "index.pickle", "wb") as f:
            pickle.dump(self._index, f)

        # Save metadata
        meta = {
            "content_hash": self._compute_content_hash(),
            "chunk_count": len(self._index.chunks),
            "file_count": self._index.file_count,
            "updated_at": datetime.now().isoformat(),
            "project_type": self._project_type.value,
        }
        (self.cache_dir / "meta.json").write_text(safe_json_dumps(meta, indent=2))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)
