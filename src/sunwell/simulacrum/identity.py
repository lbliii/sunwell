"""Session identity types (RFC-101 Phase 2).

Provides session-specific identity types for project-scoped storage.
Sessions need project scoping to prevent collisions.

Storage layout:
    ~/.sunwell/memory/
        index.json              # Session index
        projects/
            myproject/
                debug_dag.json
                debug_meta.json
            otherproject/
                debug_dag.json  # No collision!
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sunwell.core.identity import ResourceIdentity, SunwellURI


@dataclass(frozen=True, slots=True)
class SessionIndexEntry:
    """Lightweight entry for session index.

    Attributes:
        uri: Full URI (e.g., "sunwell:session/myproject/debug")
        id: UUID as string
        display_name: Human-readable session name
        namespace: Project slug
        turn_count: Number of turns in session
        learning_count: Number of learnings extracted
        created_at: ISO timestamp of creation
        last_accessed: ISO timestamp of last access
    """

    uri: str
    id: str
    display_name: str
    namespace: str
    turn_count: int
    learning_count: int
    created_at: str
    last_accessed: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SessionIndexEntry:
        """Create from dictionary representation."""
        return cls(
            uri=str(data["uri"]),
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            namespace=str(data["namespace"]),
            turn_count=int(data.get("turn_count", 0)),
            learning_count=int(data.get("learning_count", 0)),
            created_at=str(data["created_at"]),
            last_accessed=str(data["last_accessed"]),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "uri": self.uri,
            "id": self.id,
            "display_name": self.display_name,
            "namespace": self.namespace,
            "turn_count": self.turn_count,
            "learning_count": self.learning_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
        }


@dataclass(frozen=True, slots=True)
class SessionManifest:
    """Session identity metadata.

    Attributes:
        identity: UUID and URI for stable identification
        display_name: Human-readable session name
        turn_count: Number of turns in session
        learning_count: Number of learnings extracted
        created_at: ISO timestamp of creation
        last_accessed: ISO timestamp of last access
        dag_path: Path to DAG file (relative to session dir)
    """

    identity: ResourceIdentity
    display_name: str
    turn_count: int
    learning_count: int
    created_at: str
    last_accessed: str
    dag_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SessionManifest:
        """Create from dictionary representation."""
        identity_data = data.get("identity", {})
        if not isinstance(identity_data, dict):
            # Create identity from legacy fields
            uri = str(data.get("uri", "sunwell:session/default/unnamed"))
            identity = ResourceIdentity.create(SunwellURI.parse(uri))
        else:
            identity = ResourceIdentity.from_dict(
                {k: str(v) for k, v in identity_data.items()}
            )

        return cls(
            identity=identity,
            display_name=str(data.get("display_name", data.get("name", ""))),
            turn_count=int(data.get("turn_count", 0)),
            learning_count=int(data.get("learning_count", 0)),
            created_at=str(data.get("created_at", datetime.now(UTC).isoformat())),
            last_accessed=str(data.get("last_accessed", datetime.now(UTC).isoformat())),
            dag_path=str(data["dag_path"]) if data.get("dag_path") else None,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "identity": self.identity.to_dict(),
            "display_name": self.display_name,
            "turn_count": self.turn_count,
            "learning_count": self.learning_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "dag_path": self.dag_path,
        }

    def with_updated_stats(
        self,
        turn_count: int | None = None,
        learning_count: int | None = None,
    ) -> SessionManifest:
        """Return manifest with updated stats."""
        return SessionManifest(
            identity=self.identity,
            display_name=self.display_name,
            turn_count=turn_count if turn_count is not None else self.turn_count,
            learning_count=learning_count if learning_count is not None else self.learning_count,
            created_at=self.created_at,
            last_accessed=datetime.now(UTC).isoformat(),
            dag_path=self.dag_path,
        )


@dataclass(frozen=True, slots=True)
class SessionIndex:
    """Global session index.

    Attributes:
        version: Index schema version
        updated_at: ISO timestamp of last update
        sessions: URI -> SessionIndexEntry mapping
    """

    version: int
    updated_at: str
    sessions: dict[str, SessionIndexEntry]

    @classmethod
    def empty(cls) -> SessionIndex:
        """Create an empty index."""
        return cls(
            version=1,
            updated_at=datetime.now(UTC).isoformat(),
            sessions={},
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SessionIndex:
        """Create from dictionary representation."""
        sessions_data = data.get("sessions", {})
        if not isinstance(sessions_data, dict):
            sessions_data = {}
        sessions = {
            uri: SessionIndexEntry.from_dict(entry)
            for uri, entry in sessions_data.items()
            if isinstance(entry, dict)
        }
        return cls(
            version=int(data.get("version", 1)),
            updated_at=str(data.get("updated_at", datetime.now(UTC).isoformat())),
            sessions=sessions,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "sessions": {uri: entry.to_dict() for uri, entry in self.sessions.items()},
        }

    def with_entry(self, entry: SessionIndexEntry) -> SessionIndex:
        """Return new index with added/updated entry."""
        new_sessions = dict(self.sessions)
        new_sessions[entry.uri] = entry
        return SessionIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            sessions=new_sessions,
        )

    def without_entry(self, uri: str) -> SessionIndex:
        """Return new index with entry removed."""
        new_sessions = {k: v for k, v in self.sessions.items() if k != uri}
        return SessionIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            sessions=new_sessions,
        )


@dataclass(slots=True)
class SessionIndexManager:
    """Manages the global session index.

    Thread-safe index operations with caching.

    Attributes:
        memory_dir: Base directory for memory storage (~/.sunwell/memory)
    """

    memory_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "memory"
    )

    _index: SessionIndex | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "projects").mkdir(exist_ok=True)

    @property
    def index_path(self) -> Path:
        """Path to the global index file."""
        return self.memory_dir / "index.json"

    def get_index(self, *, force_reload: bool = False) -> SessionIndex:
        """Get the current index, loading from disk if needed."""
        with self._lock:
            if self._index is None or force_reload:
                self._index = self._load_index()
            return self._index

    def _load_index(self) -> SessionIndex:
        """Load index from disk."""
        if not self.index_path.exists():
            return SessionIndex.empty()

        try:
            data = json.loads(self.index_path.read_text())
            return SessionIndex.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return self._rebuild_index()

    def _save_index(self, index: SessionIndex) -> None:
        """Save index to disk."""
        self.index_path.write_text(json.dumps(index.to_dict(), indent=2))
        self._index = index

    def list_sessions(
        self,
        *,
        project: str | None = None,
    ) -> list[SessionIndexEntry]:
        """List sessions with optional filtering.

        Args:
            project: Filter by project slug

        Returns:
            List of matching index entries, sorted by last_accessed
        """
        index = self.get_index()
        entries = list(index.sessions.values())

        if project:
            entries = [e for e in entries if e.namespace == project]

        # Sort by last_accessed descending
        entries.sort(key=lambda e: e.last_accessed, reverse=True)

        return entries

    def get_entry(self, uri: str) -> SessionIndexEntry | None:
        """Get index entry by URI."""
        index = self.get_index()
        return index.sessions.get(uri)

    def resolve_slug(
        self, slug: str, project: str = "default"
    ) -> SessionIndexEntry | None:
        """Resolve a bare slug to an index entry.

        Args:
            slug: Session slug (e.g., "debug")
            project: Project context for scoped lookup

        Returns:
            Index entry or None if not found
        """
        index = self.get_index()
        uri = f"sunwell:session/{project}/{slug}"
        return index.sessions.get(uri)

    def add_session(self, entry: SessionIndexEntry) -> None:
        """Add or update a session in the index."""
        with self._lock:
            index = self.get_index()
            new_index = index.with_entry(entry)
            self._save_index(new_index)

    def update_session(
        self,
        uri: str,
        *,
        turn_count: int | None = None,
        learning_count: int | None = None,
    ) -> None:
        """Update session stats in the index."""
        with self._lock:
            index = self.get_index()
            entry = index.sessions.get(uri)
            if not entry:
                return

            updated = SessionIndexEntry(
                uri=entry.uri,
                id=entry.id,
                display_name=entry.display_name,
                namespace=entry.namespace,
                turn_count=turn_count if turn_count is not None else entry.turn_count,
                learning_count=(
                    learning_count if learning_count is not None else entry.learning_count
                ),
                created_at=entry.created_at,
                last_accessed=datetime.now(UTC).isoformat(),
            )
            new_index = index.with_entry(updated)
            self._save_index(new_index)

    def remove_session(self, uri: str) -> bool:
        """Remove a session from the index."""
        with self._lock:
            index = self.get_index()
            if uri not in index.sessions:
                return False
            new_index = index.without_entry(uri)
            self._save_index(new_index)
            return True

    def rebuild_index(self) -> SessionIndex:
        """Force rebuild of the index from filesystem."""
        with self._lock:
            return self._rebuild_index()

    def _rebuild_index(self) -> SessionIndex:
        """Internal rebuild without locking."""
        sessions: dict[str, SessionIndexEntry] = {}

        # Scan project directories
        projects_dir = self.memory_dir / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    project_slug = project_dir.name
                    for meta_file in project_dir.glob("*.json"):
                        # Skip DAG files
                        if meta_file.stem.endswith("_dag"):
                            continue
                        entry = self._create_entry_from_file(meta_file, project_slug)
                        if entry:
                            sessions[entry.uri] = entry

        # Scan legacy sessions directory
        legacy_sessions_dir = self.memory_dir / "sessions"
        if legacy_sessions_dir.exists():
            for meta_file in legacy_sessions_dir.glob("*.json"):
                if meta_file.stem.endswith("_dag"):
                    continue
                entry = self._create_entry_from_file(meta_file, "default")
                if entry and entry.uri not in sessions:
                    sessions[entry.uri] = entry

        new_index = SessionIndex(
            version=1,
            updated_at=datetime.now(UTC).isoformat(),
            sessions=sessions,
        )
        self._save_index(new_index)
        return new_index

    def _create_entry_from_file(
        self, meta_file: Path, namespace: str
    ) -> SessionIndexEntry | None:
        """Create an index entry from a session metadata file."""
        try:
            data = json.loads(meta_file.read_text())
            slug = meta_file.stem
            uri = f"sunwell:session/{namespace}/{slug}"

            # Generate stable UUID from content hash if not present
            if "id" not in data:
                content_hash = hashlib.sha256(meta_file.read_bytes()).hexdigest()
                stable_uuid = (
                    f"{content_hash[:8]}-{content_hash[8:12]}-"
                    f"{content_hash[12:16]}-{content_hash[16:20]}-{content_hash[20:32]}"
                )
            else:
                stable_uuid = data["id"]

            return SessionIndexEntry(
                uri=uri,
                id=stable_uuid,
                display_name=data.get("name", slug),
                namespace=namespace,
                turn_count=data.get("turn_count", 0),
                learning_count=data.get("stats", {}).get("total_learnings", 0)
                if isinstance(data.get("stats"), dict)
                else 0,
                created_at=data.get("created", datetime.now(UTC).isoformat()),
                last_accessed=data.get("created", datetime.now(UTC).isoformat()),
            )
        except (json.JSONDecodeError, KeyError):
            return None


def create_session_uri(slug: str, project: str = "default") -> SunwellURI:
    """Create a session URI.

    Args:
        slug: Session slug
        project: Project slug

    Returns:
        SunwellURI for the session
    """
    return SunwellURI.for_session(project, slug)


def create_session_identity(uri: SunwellURI) -> ResourceIdentity:
    """Create a new session identity.

    Args:
        uri: Session URI

    Returns:
        New ResourceIdentity with generated UUID
    """
    return ResourceIdentity.create(uri)


def create_session_manifest(
    slug: str,
    project: str = "default",
    display_name: str | None = None,
) -> SessionManifest:
    """Create a new session manifest.

    Args:
        slug: Session slug
        project: Project slug
        display_name: Optional display name (defaults to slug)

    Returns:
        New SessionManifest
    """
    uri = create_session_uri(slug, project)
    identity = create_session_identity(uri)

    now = datetime.now(UTC).isoformat()

    return SessionManifest(
        identity=identity,
        display_name=display_name or slug,
        turn_count=0,
        learning_count=0,
        created_at=now,
        last_accessed=now,
        dag_path=f"{slug}_dag.json",
    )
