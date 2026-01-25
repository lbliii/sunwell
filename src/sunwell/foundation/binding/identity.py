"""Binding identity types (RFC-101 Phase 2).

Provides binding-specific identity types for namespace isolation
and project-scoped storage. Bindings are simpler than lenses:
no versioning, just namespace isolation.

Storage layout:
    ~/.sunwell/bindings/
        index.json              # Global binding index
        global/                 # Global bindings (cross-project)
            default-writer.json
        projects/
            myproject/          # Project-scoped bindings
                writer.json
                reviewer.json
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sunwell.foundation.identity import ResourceIdentity, SunwellURI


@dataclass(frozen=True, slots=True)
class BindingIndexEntry:
    """Lightweight entry for global binding index.

    Attributes:
        uri: Full URI (e.g., "sunwell:binding/myproject/writer")
        id: UUID as string
        display_name: Human-readable name
        namespace: Namespace (global or project slug)
        lens_uri: URI of the associated lens
        provider: LLM provider
        model: Model name
        is_default: Whether this is the default binding
        last_used: ISO timestamp of last use
        use_count: Number of times used
    """

    uri: str
    id: str
    display_name: str
    namespace: str
    lens_uri: str
    provider: str
    model: str
    is_default: bool
    last_used: str
    use_count: int

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> BindingIndexEntry:
        """Create from dictionary representation."""
        return cls(
            uri=str(data["uri"]),
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            namespace=str(data["namespace"]),
            lens_uri=str(data["lens_uri"]),
            provider=str(data["provider"]),
            model=str(data["model"]),
            is_default=bool(data.get("is_default", False)),
            last_used=str(data["last_used"]),
            use_count=int(data.get("use_count", 0)),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "uri": self.uri,
            "id": self.id,
            "display_name": self.display_name,
            "namespace": self.namespace,
            "lens_uri": self.lens_uri,
            "provider": self.provider,
            "model": self.model,
            "is_default": self.is_default,
            "last_used": self.last_used,
            "use_count": self.use_count,
        }


@dataclass(frozen=True, slots=True)
class BindingIndex:
    """Global binding index.

    Attributes:
        version: Index schema version
        updated_at: ISO timestamp of last update
        bindings: URI -> BindingIndexEntry mapping
    """

    version: int
    updated_at: str
    bindings: dict[str, BindingIndexEntry]

    @classmethod
    def empty(cls) -> BindingIndex:
        """Create an empty index."""
        return cls(
            version=1,
            updated_at=datetime.now(UTC).isoformat(),
            bindings={},
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> BindingIndex:
        """Create from dictionary representation."""
        bindings_data = data.get("bindings", {})
        if not isinstance(bindings_data, dict):
            bindings_data = {}
        bindings = {
            uri: BindingIndexEntry.from_dict(entry)
            for uri, entry in bindings_data.items()
            if isinstance(entry, dict)
        }
        return cls(
            version=int(data.get("version", 1)),
            updated_at=str(data.get("updated_at", datetime.now(UTC).isoformat())),
            bindings=bindings,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "bindings": {uri: entry.to_dict() for uri, entry in self.bindings.items()},
        }

    def with_entry(self, entry: BindingIndexEntry) -> BindingIndex:
        """Return new index with added/updated entry."""
        new_bindings = dict(self.bindings)
        new_bindings[entry.uri] = entry
        return BindingIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            bindings=new_bindings,
        )

    def without_entry(self, uri: str) -> BindingIndex:
        """Return new index with entry removed."""
        new_bindings = {k: v for k, v in self.bindings.items() if k != uri}
        return BindingIndex(
            version=self.version,
            updated_at=datetime.now(UTC).isoformat(),
            bindings=new_bindings,
        )


@dataclass(slots=True)
class BindingIndexManager:
    """Manages the global binding index.

    Thread-safe index operations with caching.

    Attributes:
        bindings_dir: Directory for bindings (~/.sunwell/bindings or project/.sunwell/bindings)
    """

    bindings_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "bindings"
    )

    _index: BindingIndex | None = field(default=None, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.bindings_dir.mkdir(parents=True, exist_ok=True)
        (self.bindings_dir / "global").mkdir(exist_ok=True)
        (self.bindings_dir / "projects").mkdir(exist_ok=True)

    @property
    def index_path(self) -> Path:
        """Path to the global index file."""
        return self.bindings_dir / "index.json"

    def get_index(self, *, force_reload: bool = False) -> BindingIndex:
        """Get the current index, loading from disk if needed."""
        with self._lock:
            if self._index is None or force_reload:
                self._index = self._load_index()
            return self._index

    def _load_index(self) -> BindingIndex:
        """Load index from disk."""
        if not self.index_path.exists():
            return BindingIndex.empty()

        try:
            data = json.loads(self.index_path.read_text())
            return BindingIndex.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return self._rebuild_index()

    def _save_index(self, index: BindingIndex) -> None:
        """Save index to disk."""
        self.index_path.write_text(json.dumps(index.to_dict(), indent=2))
        self._index = index

    def list_bindings(
        self,
        *,
        namespace: str | None = None,
        project: str | None = None,
    ) -> list[BindingIndexEntry]:
        """List bindings with optional filtering.

        Args:
            namespace: Filter by namespace (global or project slug)
            project: Filter by project (alias for namespace)

        Returns:
            List of matching index entries, sorted by last_used
        """
        index = self.get_index()
        entries = list(index.bindings.values())

        filter_ns = project or namespace
        if filter_ns:
            entries = [e for e in entries if e.namespace == filter_ns]

        # Sort: defaults first, then by last_used
        entries.sort(
            key=lambda e: (
                not e.is_default,
                e.last_used,
            ),
            reverse=True,
        )

        return entries

    def get_entry(self, uri: str) -> BindingIndexEntry | None:
        """Get index entry by URI."""
        index = self.get_index()
        return index.bindings.get(uri)

    def resolve_slug(self, slug: str, project: str | None = None) -> BindingIndexEntry | None:
        """Resolve a bare slug to an index entry.

        Resolution order: project -> global

        Args:
            slug: Bare binding slug (e.g., "writer")
            project: Project context for scoped lookup

        Returns:
            Index entry or None if not found
        """
        index = self.get_index()

        # Try project namespace first
        if project:
            project_uri = f"sunwell:binding/{project}/{slug}"
            if project_uri in index.bindings:
                return index.bindings[project_uri]

        # Try global namespace
        global_uri = f"sunwell:binding/global/{slug}"
        if global_uri in index.bindings:
            return index.bindings[global_uri]

        return None

    def add_binding(self, entry: BindingIndexEntry) -> None:
        """Add or update a binding in the index."""
        with self._lock:
            index = self.get_index()
            new_index = index.with_entry(entry)
            self._save_index(new_index)

    def remove_binding(self, uri: str) -> bool:
        """Remove a binding from the index."""
        with self._lock:
            index = self.get_index()
            if uri not in index.bindings:
                return False
            new_index = index.without_entry(uri)
            self._save_index(new_index)
            return True

    def set_default(self, uri: str | None, namespace: str = "global") -> bool:
        """Set the default binding for a namespace."""
        with self._lock:
            index = self.get_index()
            new_bindings = {}

            for entry_uri, entry in index.bindings.items():
                # Only affect bindings in the same namespace
                if entry.namespace == namespace:
                    new_entry = BindingIndexEntry(
                        uri=entry.uri,
                        id=entry.id,
                        display_name=entry.display_name,
                        namespace=entry.namespace,
                        lens_uri=entry.lens_uri,
                        provider=entry.provider,
                        model=entry.model,
                        is_default=(entry_uri == uri),
                        last_used=entry.last_used,
                        use_count=entry.use_count,
                    )
                    new_bindings[entry_uri] = new_entry
                else:
                    new_bindings[entry_uri] = entry

            new_index = BindingIndex(
                version=index.version,
                updated_at=datetime.now(UTC).isoformat(),
                bindings=new_bindings,
            )
            self._save_index(new_index)
            return True

    def rebuild_index(self) -> BindingIndex:
        """Force rebuild of the index from filesystem."""
        with self._lock:
            return self._rebuild_index()

    def _rebuild_index(self) -> BindingIndex:
        """Internal rebuild without locking."""
        bindings: dict[str, BindingIndexEntry] = {}

        # Scan global bindings
        global_dir = self.bindings_dir / "global"
        if global_dir.exists():
            for binding_file in global_dir.glob("*.json"):
                entry = self._create_entry_from_file(binding_file, "global")
                if entry:
                    bindings[entry.uri] = entry

        # Scan project bindings
        projects_dir = self.bindings_dir / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    project_slug = project_dir.name
                    for binding_file in project_dir.glob("*.json"):
                        entry = self._create_entry_from_file(binding_file, project_slug)
                        if entry:
                            bindings[entry.uri] = entry

        new_index = BindingIndex(
            version=1,
            updated_at=datetime.now(UTC).isoformat(),
            bindings=bindings,
        )
        self._save_index(new_index)
        return new_index

    def _create_entry_from_file(
        self, binding_file: Path, namespace: str
    ) -> BindingIndexEntry | None:
        """Create an index entry from a binding file."""
        try:
            # Read file once as bytes, decode for JSON
            content = binding_file.read_bytes()
            data = json.loads(content.decode("utf-8"))
            slug = binding_file.stem
            uri = f"sunwell:binding/{namespace}/{slug}"

            # Generate stable UUID from content hash if not present
            if "id" not in data:
                content_hash = hashlib.sha256(content).hexdigest()
                stable_uuid = (
                    f"{content_hash[:8]}-{content_hash[8:12]}-"
                    f"{content_hash[12:16]}-{content_hash[16:20]}-{content_hash[20:32]}"
                )
            else:
                stable_uuid = data["id"]

            # Convert lens_path to lens_uri if needed
            lens_uri = data.get("lens_uri", "")
            if not lens_uri and "lens_path" in data:
                # Convert path to URI
                lens_path = data["lens_path"]
                if "/" in lens_path or "\\" in lens_path:
                    # Path-based, extract slug
                    lens_slug = Path(lens_path).stem
                    lens_uri = f"sunwell:lens/user/{lens_slug}"
                else:
                    # Already a slug
                    lens_uri = f"sunwell:lens/user/{lens_path}"

            return BindingIndexEntry(
                uri=uri,
                id=stable_uuid,
                display_name=data.get("name", slug),
                namespace=namespace,
                lens_uri=lens_uri,
                provider=data.get("provider", "ollama"),
                model=data.get("model", "gemma3:4b"),
                is_default=False,
                last_used=data.get("last_used", datetime.now(UTC).isoformat()),
                use_count=data.get("use_count", 0),
            )
        except (json.JSONDecodeError, KeyError):
            return None


def create_binding_uri(slug: str, project: str | None = None) -> SunwellURI:
    """Create a binding URI.

    Args:
        slug: Binding slug
        project: Project slug (None for global)

    Returns:
        SunwellURI for the binding
    """
    namespace = project or "global"
    return SunwellURI.for_binding(namespace, slug)


def create_binding_identity(uri: SunwellURI) -> ResourceIdentity:
    """Create a new binding identity.

    Args:
        uri: Binding URI

    Returns:
        New ResourceIdentity with generated UUID
    """
    return ResourceIdentity.create(uri)
