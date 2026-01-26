"""Workspace-level L1 signature index.

Aggregates lightweight signatures across all projects in a workspace.
Used for fast cross-project awareness without full indexing overhead.

Storage: ~/.sunwell/workspaces/{workspace_id}/index/signatures.db
"""

import asyncio
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.knowledge.indexing.signature_extractor import Signature, SignatureExtractor
from sunwell.knowledge.workspace.types import (
    IndexTier,
    ProjectRole,
    Workspace,
    WorkspaceProject,
)

logger = logging.getLogger(__name__)

__all__ = [
    "WorkspaceSignatureIndex",
    "SignatureMatch",
    "get_workspace_index_dir",
]


def get_workspace_index_dir(workspace_id: str) -> Path:
    """Get the index directory for a workspace.

    Returns:
        Path to ~/.sunwell/workspaces/{workspace_id}/index/
    """
    index_dir = Path.home() / ".sunwell" / "workspaces" / workspace_id / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    return index_dir


@dataclass(frozen=True, slots=True)
class SignatureMatch:
    """A matched signature from cross-project search."""

    project_id: str
    """Which project this came from."""

    signature: Signature
    """The matched signature."""

    score: float
    """Relevance score (0.0 - 1.0)."""


@dataclass(slots=True)
class WorkspaceSignatureIndex:
    """Cross-project L1 signature index.

    Aggregates signatures from all projects in a workspace for fast
    cross-project awareness. Uses SQLite for efficient persistent storage.

    Example:
        >>> index = WorkspaceSignatureIndex(workspace)
        >>> await index.scan_all()  # Build index
        >>> matches = await index.search("authentication", top_k=10)
        >>> for match in matches:
        ...     print(f"[{match.project_id}] {match.signature.name}")
    """

    workspace: Workspace
    """The workspace to index."""

    # Internal state
    _db_path: Path = field(init=False)
    _extractor: SignatureExtractor = field(init=False)
    _lock: threading.Lock = field(init=False)
    _initialized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Initialize index."""
        self._db_path = get_workspace_index_dir(self.workspace.id) / "signatures.db"
        self._extractor = SignatureExtractor()
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS signatures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        line INTEGER NOT NULL,
                        docstring TEXT,
                        indexed_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_project ON signatures(project_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_name ON signatures(name)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kind ON signatures(kind)
                """)
                conn.commit()
            finally:
                conn.close()

        self._initialized = True

    async def scan_all(self) -> dict[str, int]:
        """Scan all projects and build the index.

        Returns:
            Dict of project_id -> signature count.
        """
        results: dict[str, int] = {}

        for project in self.workspace.projects:
            count = await self.scan_project(project)
            results[project.id] = count

        return results

    async def scan_project(self, project: WorkspaceProject) -> int:
        """Scan a single project for signatures.

        Args:
            project: Project to scan.

        Returns:
            Number of signatures extracted.
        """
        # Clear existing signatures for this project
        await asyncio.to_thread(self._clear_project, project.id)

        # Find source files
        source_files = await asyncio.to_thread(self._find_source_files, project.path)

        # Extract signatures
        signatures: list[tuple[str, Signature]] = []
        for file_path in source_files:
            try:
                file_sigs = await asyncio.to_thread(self._extractor.extract, file_path)
                for sig in file_sigs:
                    signatures.append((project.id, sig))
            except Exception as e:
                logger.debug(f"Failed to extract signatures from {file_path}: {e}")

        # Store signatures
        if signatures:
            await asyncio.to_thread(self._store_signatures, signatures)

        logger.info(f"Indexed {len(signatures)} signatures for {project.id}")
        return len(signatures)

    def _clear_project(self, project_id: str) -> None:
        """Clear signatures for a project."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("DELETE FROM signatures WHERE project_id = ?", (project_id,))
                conn.commit()
            finally:
                conn.close()

    def _find_source_files(self, root: Path) -> list[Path]:
        """Find source files to index."""
        extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
        skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

        files: list[Path] = []
        try:
            for item in root.rglob("*"):
                if item.is_file() and item.suffix in extensions:
                    # Check if in skip directory
                    if not any(skip in item.parts for skip in skip_dirs):
                        files.append(item)
        except (OSError, PermissionError) as e:
            logger.warning(f"Error scanning {root}: {e}")

        return files

    def _store_signatures(self, signatures: list[tuple[str, Signature]]) -> None:
        """Store signatures in database."""
        now = datetime.now().isoformat()

        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.executemany(
                    """
                    INSERT INTO signatures 
                    (project_id, name, kind, signature, file_path, line, docstring, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            project_id,
                            sig.name,
                            sig.kind,
                            sig.signature,
                            str(sig.file_path),
                            sig.line,
                            sig.docstring,
                            now,
                        )
                        for project_id, sig in signatures
                    ],
                )
                conn.commit()
            finally:
                conn.close()

    async def search(
        self,
        query: str,
        top_k: int = 10,
        project_ids: list[str] | None = None,
    ) -> list[SignatureMatch]:
        """Search for signatures matching query.

        Uses simple text matching on name, signature, and docstring.
        For semantic search, use the full WorkspaceSearch.

        Args:
            query: Search query.
            top_k: Maximum results.
            project_ids: Optional filter to specific projects.

        Returns:
            List of matching signatures.
        """
        return await asyncio.to_thread(
            self._search_sync, query, top_k, project_ids
        )

    def _search_sync(
        self,
        query: str,
        top_k: int,
        project_ids: list[str] | None,
    ) -> list[SignatureMatch]:
        """Synchronous search implementation."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                # Build SQL query
                sql = """
                    SELECT project_id, name, kind, signature, file_path, line, docstring
                    FROM signatures
                """
                params: list = []

                if project_ids:
                    placeholders = ",".join("?" for _ in project_ids)
                    sql += f" WHERE project_id IN ({placeholders})"
                    params.extend(project_ids)

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
            finally:
                conn.close()

        # Score and sort results
        matches: list[SignatureMatch] = []
        for row in rows:
            # Calculate simple text match score
            searchable = f"{row['name']} {row['signature']} {row['docstring'] or ''}".lower()

            # Exact name match is highest score
            if query_lower == row["name"].lower():
                score = 1.0
            # Name contains query
            elif query_lower in row["name"].lower():
                score = 0.8
            # Signature contains query
            elif query_lower in searchable:
                score = 0.6
            # Word overlap
            else:
                searchable_words = set(searchable.split())
                overlap = len(query_words & searchable_words)
                if overlap > 0:
                    score = 0.3 * (overlap / len(query_words))
                else:
                    continue  # No match

            sig = Signature(
                name=row["name"],
                kind=row["kind"],
                signature=row["signature"],
                file_path=Path(row["file_path"]),
                line=row["line"],
                docstring=row["docstring"],
            )

            matches.append(
                SignatureMatch(
                    project_id=row["project_id"],
                    signature=sig,
                    score=score,
                )
            )

        # Sort by score and return top_k
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    async def get_project_signatures(self, project_id: str) -> list[Signature]:
        """Get all signatures for a project.

        Args:
            project_id: Project to get signatures for.

        Returns:
            List of signatures.
        """
        return await asyncio.to_thread(self._get_project_signatures_sync, project_id)

    def _get_project_signatures_sync(self, project_id: str) -> list[Signature]:
        """Synchronous get project signatures."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    """
                    SELECT name, kind, signature, file_path, line, docstring
                    FROM signatures WHERE project_id = ?
                    """,
                    (project_id,),
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

        return [
            Signature(
                name=row["name"],
                kind=row["kind"],
                signature=row["signature"],
                file_path=Path(row["file_path"]),
                line=row["line"],
                docstring=row["docstring"],
            )
            for row in rows
        ]

    def get_stats(self) -> dict[str, int]:
        """Get index statistics.

        Returns:
            Dict with total_signatures, project_count, etc.
        """
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                total = conn.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
                projects = conn.execute(
                    "SELECT COUNT(DISTINCT project_id) FROM signatures"
                ).fetchone()[0]
                by_kind = dict(
                    conn.execute(
                        "SELECT kind, COUNT(*) FROM signatures GROUP BY kind"
                    ).fetchall()
                )
            finally:
                conn.close()

        return {
            "total_signatures": total,
            "project_count": projects,
            **by_kind,
        }
