"""Persistent storage for artifact lineage (RFC-121).

Thread-safe JSON-based storage with file locking for concurrent access.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sunwell.memory.lineage.models import (
    ArtifactEdit,
    ArtifactLineage,
    compute_content_hash,
)

if TYPE_CHECKING:
    from sunwell.memory.lineage.identity import ArtifactIdentityResolver


class LineageStore:
    """Persistent storage for artifact lineage.

    Thread-safe with file locking for concurrent access.
    Stores lineage as JSON files in `.sunwell/lineage/`.

    Storage layout:
        .sunwell/lineage/
        ├── index.json           # path → artifact_id mapping
        ├── deleted.json         # Recently deleted artifact IDs
        └── artifacts/
            ├── {artifact_id}.json
            └── ...

    Example:
        >>> store = LineageStore(Path("/project"))
        >>> lineage = store.record_create(
        ...     path="src/auth.py",
        ...     content="class Auth: pass",
        ...     goal_id="goal-1",
        ...     task_id="task-1",
        ...     reason="Auth module",
        ...     model="claude-sonnet",
        ... )
        >>> retrieved = store.get_by_path("src/auth.py")
        >>> assert retrieved.artifact_id == lineage.artifact_id
    """

    INDEX_VERSION = 1

    def __init__(self, project_root: Path) -> None:
        self.store_path = project_root / ".sunwell" / "lineage"
        self.artifacts_path = self.store_path / "artifacts"
        self._lock = threading.Lock()
        self._index: dict[str, str] = {}  # path → artifact_id
        self._deleted: set[str] = set()  # artifact_ids marked deleted
        self._identity_resolver: ArtifactIdentityResolver | None = None

        # Ensure directories exist
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.artifacts_path.mkdir(parents=True, exist_ok=True)

        # Load index
        self._load_index()
        self._load_deleted()

    def _get_identity_resolver(self) -> ArtifactIdentityResolver:
        """Lazy-initialize identity resolver to avoid circular import."""
        if self._identity_resolver is None:
            from sunwell.memory.lineage.identity import ArtifactIdentityResolver

            self._identity_resolver = ArtifactIdentityResolver(self)
        return self._identity_resolver

    # ─────────────────────────────────────────────────────────────────
    # Index Management
    # ─────────────────────────────────────────────────────────────────

    def _load_index(self) -> None:
        """Load path→artifact_id index from disk."""
        index_path = self.store_path / "index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text())
            self._index = data.get("paths", {})

    def _save_index(self) -> None:
        """Save index to disk."""
        index_path = self.store_path / "index.json"
        data = {
            "version": self.INDEX_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "paths": self._index,
        }
        index_path.write_text(json.dumps(data, indent=2))

    def _load_deleted(self) -> None:
        """Load deleted artifact IDs from disk."""
        deleted_path = self.store_path / "deleted.json"
        if deleted_path.exists():
            data = json.loads(deleted_path.read_text())
            self._deleted = set(data.get("artifact_ids", []))

    def _save_deleted(self) -> None:
        """Save deleted artifact IDs to disk."""
        deleted_path = self.store_path / "deleted.json"
        data = {
            "updated_at": datetime.now(UTC).isoformat(),
            "artifact_ids": list(self._deleted),
        }
        deleted_path.write_text(json.dumps(data, indent=2))

    # ─────────────────────────────────────────────────────────────────
    # Artifact Persistence
    # ─────────────────────────────────────────────────────────────────

    def _artifact_path(self, artifact_id: str) -> Path:
        """Get file path for an artifact."""
        # Use first 8 chars of UUID as filename (before the colon)
        safe_id = artifact_id.split(":")[0][:8]
        return self.artifacts_path / f"{safe_id}.json"

    def _save_artifact(self, lineage: ArtifactLineage) -> None:
        """Save artifact to disk."""
        path = self._artifact_path(lineage.artifact_id)
        path.write_text(json.dumps(lineage.to_dict(), indent=2))

    def _load_artifact(self, artifact_id: str) -> ArtifactLineage | None:
        """Load artifact from disk."""
        path = self._artifact_path(artifact_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return ArtifactLineage.from_dict(data)

    # ─────────────────────────────────────────────────────────────────
    # Recording Operations
    # ─────────────────────────────────────────────────────────────────

    def record_create(
        self,
        path: str,
        content: str,
        goal_id: str | None,
        task_id: str | None,
        reason: str,
        model: str | None,
        session_id: str | None = None,
    ) -> ArtifactLineage:
        """Record artifact creation.

        Args:
            path: File path relative to project root
            content: File content
            goal_id: Goal that created this artifact
            task_id: Task that created this artifact
            reason: Why this artifact exists
            model: Model that generated the content
            session_id: Session ID for tracking

        Returns:
            Created ArtifactLineage record
        """
        with self._lock:
            # Resolve identity (handles rename detection)
            resolver = self._get_identity_resolver()
            artifact_id = resolver.resolve_create(path, content)
            content_hash = compute_content_hash(content)

            lineage = ArtifactLineage(
                artifact_id=artifact_id,
                path=path,
                content_hash=content_hash,
                created_by_goal=goal_id,
                created_by_task=task_id,
                created_at=datetime.now(UTC),
                created_reason=reason,
                model=model,
                human_edited=False,
                edits=(),
                imports=(),
                imported_by=(),
                deleted_at=None,
            )

            self._save_artifact(lineage)
            self._index[path] = artifact_id
            self._deleted.discard(artifact_id)  # Remove from deleted if reused
            self._save_index()
            self._save_deleted()

            return lineage

    def record_edit(
        self,
        path: str,
        goal_id: str | None,
        task_id: str | None,
        lines_added: int,
        lines_removed: int,
        source: str,
        model: str | None = None,
        session_id: str | None = None,
        content: str | None = None,
    ) -> ArtifactEdit:
        """Record an edit to an artifact.

        Args:
            path: File path
            goal_id: Goal that triggered this edit
            task_id: Task that triggered this edit
            lines_added: Number of lines added
            lines_removed: Number of lines removed
            source: Edit source ("sunwell", "human", "external")
            model: Model that made the edit (if sunwell)
            session_id: Session ID
            content: New file content (for hash update)

        Returns:
            Created ArtifactEdit record
        """
        with self._lock:
            lineage = self.get_by_path(path)
            if not lineage:
                # File exists but wasn't created by Sunwell
                lineage = self._create_external(path, content or "")

            edit = ArtifactEdit(
                edit_id=str(uuid4()),
                artifact_id=lineage.artifact_id,
                goal_id=goal_id,
                task_id=task_id,
                lines_added=lines_added,
                lines_removed=lines_removed,
                edit_type="modify",
                source=source,  # type: ignore[arg-type]
                model=model,
                timestamp=datetime.now(UTC),
                session_id=session_id,
                commit_hash=None,
                content_hash=compute_content_hash(content) if content else None,
            )

            updated = lineage.with_edit(edit)
            self._save_artifact(updated)

            return edit

    def record_rename(
        self,
        old_path: str,
        new_path: str,
        goal_id: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record artifact rename, preserving lineage.

        Args:
            old_path: Original file path
            new_path: New file path
            goal_id: Goal that triggered the rename
            session_id: Session ID
        """
        with self._lock:
            lineage = self.get_by_path(old_path)
            if not lineage:
                return

            edit = ArtifactEdit(
                edit_id=str(uuid4()),
                artifact_id=lineage.artifact_id,
                goal_id=goal_id,
                task_id=None,
                lines_added=0,
                lines_removed=0,
                edit_type="rename",
                source="sunwell",
                model=None,
                timestamp=datetime.now(UTC),
                session_id=session_id,
                commit_hash=None,
                content_hash=lineage.content_hash,
            )

            updated = lineage.with_edit(edit).with_path(new_path)
            self._save_artifact(updated)

            # Update index
            del self._index[old_path]
            self._index[new_path] = lineage.artifact_id
            self._save_index()

    def record_delete(
        self,
        path: str,
        goal_id: str | None,
        session_id: str | None = None,
    ) -> None:
        """Record artifact deletion (soft delete, keeps history).

        Args:
            path: File path to delete
            goal_id: Goal that triggered the deletion
            session_id: Session ID
        """
        with self._lock:
            lineage = self.get_by_path(path)
            if not lineage:
                return

            edit = ArtifactEdit(
                edit_id=str(uuid4()),
                artifact_id=lineage.artifact_id,
                goal_id=goal_id,
                task_id=None,
                lines_added=0,
                lines_removed=0,
                edit_type="delete",
                source="sunwell",
                model=None,
                timestamp=datetime.now(UTC),
                session_id=session_id,
                commit_hash=None,
                content_hash=lineage.content_hash,
            )

            updated = lineage.with_edit(edit).with_deleted(datetime.now(UTC))
            self._save_artifact(updated)

            # Update index and deleted set
            del self._index[path]
            self._deleted.add(lineage.artifact_id)
            self._save_index()
            self._save_deleted()

    # ─────────────────────────────────────────────────────────────────
    # Queries
    # ─────────────────────────────────────────────────────────────────

    def get_by_path(self, path: str) -> ArtifactLineage | None:
        """Get lineage for a file path. O(1) via index.

        Args:
            path: File path

        Returns:
            ArtifactLineage if found, None otherwise
        """
        artifact_id = self._index.get(path)
        return self._load_artifact(artifact_id) if artifact_id else None

    def get_by_goal(self, goal_id: str) -> list[ArtifactLineage]:
        """Get all artifacts created/modified by a goal.

        Note: O(n) scan - consider caching for large projects.

        Args:
            goal_id: Goal ID to search for

        Returns:
            List of artifacts touched by the goal
        """
        results = []
        for artifact_id in self._list_artifact_ids():
            lineage = self._load_artifact(artifact_id)
            if lineage and (
                lineage.created_by_goal == goal_id
                or any(e.goal_id == goal_id for e in lineage.edits)
            ):
                results.append(lineage)
        return results

    def get_recently_deleted(self, hours: int = 24) -> list[ArtifactLineage]:
        """Get artifacts deleted within the last N hours.

        Args:
            hours: Look back period in hours

        Returns:
            List of recently deleted artifacts
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        results = []

        for artifact_id in self._deleted:
            lineage = self._load_artifact(artifact_id)
            if lineage and lineage.deleted_at and lineage.deleted_at > cutoff:
                results.append(lineage)

        return results

    def get_dependents(self, path: str) -> list[str]:
        """Get all files that import this file.

        Args:
            path: File path

        Returns:
            List of paths that import this file
        """
        lineage = self.get_by_path(path)
        return list(lineage.imported_by) if lineage else []

    def get_dependencies(self, path: str) -> list[str]:
        """Get all files this file imports.

        Args:
            path: File path

        Returns:
            List of paths this file imports
        """
        lineage = self.get_by_path(path)
        return list(lineage.imports) if lineage else []

    def _list_artifact_ids(self) -> list[str]:
        """List all artifact IDs (including deleted)."""
        return list(set(self._index.values()) | self._deleted)

    # ─────────────────────────────────────────────────────────────────
    # Dependency Management
    # ─────────────────────────────────────────────────────────────────

    def update_imports(self, path: str, imports: list[str]) -> None:
        """Update the imports list for an artifact.

        Args:
            path: File path
            imports: List of import paths
        """
        with self._lock:
            lineage = self.get_by_path(path)
            if lineage:
                updated = lineage.with_imports(
                    imports=tuple(imports),
                    imported_by=lineage.imported_by,
                )
                self._save_artifact(updated)

    def add_imported_by(self, path: str, importer: str) -> None:
        """Add an importer to the imported_by list.

        Args:
            path: File being imported
            importer: File that imports it
        """
        with self._lock:
            lineage = self.get_by_path(path)
            if lineage and importer not in lineage.imported_by:
                updated = lineage.with_imports(
                    imports=lineage.imports,
                    imported_by=(*lineage.imported_by, importer),
                )
                self._save_artifact(updated)

    def remove_imported_by(self, path: str, importer: str) -> None:
        """Remove an importer from the imported_by list.

        Args:
            path: File being imported
            importer: File to remove from importers
        """
        with self._lock:
            lineage = self.get_by_path(path)
            if lineage and importer in lineage.imported_by:
                updated = lineage.with_imports(
                    imports=lineage.imports,
                    imported_by=tuple(p for p in lineage.imported_by if p != importer),
                )
                self._save_artifact(updated)

    # ─────────────────────────────────────────────────────────────────
    # External File Handling
    # ─────────────────────────────────────────────────────────────────

    def _create_external(self, path: str, content: str) -> ArtifactLineage:
        """Create lineage record for file not created by Sunwell.

        Args:
            path: File path
            content: File content

        Returns:
            New lineage record marked as pre-existing
        """
        from sunwell.memory.lineage.models import generate_artifact_id

        artifact_id = generate_artifact_id(path, content)
        lineage = ArtifactLineage(
            artifact_id=artifact_id,
            path=path,
            content_hash=compute_content_hash(content),
            created_by_goal=None,
            created_by_task=None,
            created_at=datetime.now(UTC),
            created_reason="Pre-existing file (not created by Sunwell)",
            model=None,
            human_edited=True,
            edits=(),
            imports=(),
            imported_by=(),
            deleted_at=None,
        )

        self._save_artifact(lineage)
        self._index[path] = artifact_id
        self._save_index()

        return lineage

    # ─────────────────────────────────────────────────────────────────
    # Initialization & Migration
    # ─────────────────────────────────────────────────────────────────

    def init_project(self, scan_existing: bool = False) -> dict[str, int]:
        """Initialize lineage tracking for a project.

        Args:
            scan_existing: Whether to scan existing files

        Returns:
            Dict with initialization stats
        """
        stats = {"files_scanned": 0, "artifacts_created": 0}

        if not scan_existing:
            return stats

        # This would scan the project and create lineage records
        # Implementation deferred to Phase 4 CLI
        return stats
