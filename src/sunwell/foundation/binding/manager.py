"""Binding manager with identity system (RFC-101 Phase 2).

Bindings are your attuned instances of lenses - they remember:
- Which lens (expertise)
- Which model (provider, name)
- Which simulacrum (memory)
- Your personal settings

RFC-101 adds:
- URI-based identification (sunwell:binding/namespace/slug)
- Project-scoped storage
- Global binding index for O(1) listing
- lens_uri instead of lens_path
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sunwell.foundation.binding.identity import (
    BindingIndexEntry,
    BindingIndexManager,
    create_binding_identity,
    create_binding_uri,
)
from sunwell.foundation.identity import SunwellURI
from sunwell.foundation.utils import slugify

# Default models per provider (extracted to avoid per-call dict creation)
_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "gemma3:4b",
}


@dataclass(slots=True)
class Binding:
    """Your personal attunement to a lens.

    Stores all the config so you don't need flags:
    - lens: URI or path to the lens
    - provider: LLM provider (openai, anthropic, etc.)
    - model: Model name (gpt-4o, claude-sonnet-4-20250514, etc.)
    - simulacrum: Name of associated simulacrum
    - settings: Personal overrides

    RFC-101: Added uri, id, and lens_uri fields.
    """

    name: str
    """Binding name (e.g., "my-project", "docs-writer")."""

    lens_path: str = ""
    """Path to lens file (deprecated, use lens_uri instead)."""

    # RFC-101: New identity fields
    uri: str | None = None
    """Full URI (e.g., "sunwell:binding/global/my-writer")."""

    id: str | None = None
    """UUID for stable identification."""

    lens_uri: str | None = None
    """URI of the lens (preferred over lens_path)."""

    provider: str = "ollama"
    """LLM provider (default: from config)."""

    model: str = "gemma3:4b"
    """Model name (default: from config)."""

    simulacrum: str | None = None
    """Associated simulacrum name (defaults to binding name)."""

    # Execution settings
    tier: int = 1
    """Default execution tier (0=fast, 1=standard, 2=deep)."""

    stream: bool = True
    """Stream output by default."""

    verbose: bool = False
    """Verbose output by default."""

    auto_learn: bool = True
    """Auto-extract learnings from responses."""

    # Workspace settings
    workspace_patterns: list[str] = field(default_factory=list)
    """File patterns to include as context."""

    index_workspace: bool = True
    """Auto-index workspace for code context."""

    # Tool settings (RFC-012)
    tools_enabled: bool = False
    """Enable tool calling (read/write files, run commands)."""

    trust_level: str = "workspace"
    """Tool trust level: discovery, read_only, workspace, shell."""

    allowed_tools: list[str] = field(default_factory=list)
    """Restrict to specific tools (empty = all allowed by trust level)."""

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_used: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    use_count: int = 0

    def __post_init__(self) -> None:
        """Set simulacrum name if not provided."""
        if self.simulacrum is None:
            self.simulacrum = self.name

    def touch(self) -> None:
        """Update last_used and increment use_count."""
        self.last_used = datetime.now(UTC).isoformat()
        self.use_count += 1

    def get_lens_reference(self) -> str:
        """Get the lens reference (URI or path).

        Returns lens_uri if set, otherwise falls back to lens_path for backwards compatibility.
        """
        if self.lens_uri:
            return self.lens_uri
        # Backwards compatibility: convert old lens_path to URI if it's a slug
        if self.lens_path and "/" not in self.lens_path and "\\" not in self.lens_path:
            return f"sunwell:lens/user/{self.lens_path}"
        return self.lens_path

    def save(self, path: Path) -> None:
        """Save binding to file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "lens_path": self.lens_path,  # Preserved for backwards compatibility
            "uri": self.uri,
            "id": self.id,
            "lens_uri": self.lens_uri,
            "provider": self.provider,
            "model": self.model,
            "simulacrum": self.simulacrum,
            "tier": self.tier,
            "stream": self.stream,
            "verbose": self.verbose,
            "auto_learn": self.auto_learn,
            "workspace_patterns": self.workspace_patterns,
            "index_workspace": self.index_workspace,
            "tools_enabled": self.tools_enabled,
            "trust_level": self.trust_level,
            "allowed_tools": self.allowed_tools,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Binding:
        """Load binding from file."""
        with open(path) as f:
            data = json.load(f)

        # Migration: support old "headspace" field name
        simulacrum = data.get("simulacrum") or data.get("headspace")

        # Use config defaults for backwards compatibility with old bindings
        from sunwell.foundation.config import get_config

        cfg = get_config()
        default_provider = cfg.model.default_provider if cfg else "ollama"
        default_model = cfg.model.default_model if cfg else "gemma3:4b"

        # Migrate lens_path to lens_uri if needed
        lens_uri = data.get("lens_uri")
        lens_path = data.get("lens_path", "")
        if not lens_uri and lens_path:
            # Convert old lens_path to URI if it's a slug
            if "/" not in lens_path and "\\" not in lens_path:
                lens_uri = f"sunwell:lens/user/{lens_path}"

        return cls(
            name=data["name"],
            lens_path=data.get("lens_path", ""),  # Preserved for backwards compatibility
            uri=data.get("uri"),
            id=data.get("id"),
            lens_uri=lens_uri or lens_path,  # Use migrated URI or keep path for file paths
            provider=data.get("provider", default_provider),
            model=data.get("model", default_model),
            simulacrum=simulacrum,
            tier=data.get("tier", 1),
            stream=data.get("stream", True),
            verbose=data.get("verbose", False),
            auto_learn=data.get("auto_learn", True),
            workspace_patterns=data.get("workspace_patterns", []),
            index_workspace=data.get("index_workspace", True),
            tools_enabled=data.get("tools_enabled", False),
            trust_level=data.get("trust_level", "workspace"),
            allowed_tools=data.get("allowed_tools", []),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            last_used=data.get("last_used", datetime.now(UTC).isoformat()),
            use_count=data.get("use_count", 0),
        )


class BindingManager:
    """Manages bindings with identity system (RFC-101).

    Storage layouts:
    - RFC-101: ~/.sunwell/bindings/global/<name>.json (global)
              ~/.sunwell/bindings/projects/<project>/<name>.json (project-scoped)

    Default: .sunwell/default_binding (contains name of default)
    """

    def __init__(
        self,
        root: Path | None = None,
        project: str | None = None,
        bindings_dir: Path | None = None,
    ) -> None:
        """Initialize binding manager.

        Args:
            root: Project root (defaults to cwd).
            project: Project slug for scoped bindings (None = global).
            bindings_dir: Directory for bindings storage (defaults to ~/.sunwell/bindings).
                          Pass a custom path for test isolation.
        """
        self.root = root or Path.cwd()
        self.project = project
        self._bindings_dir = bindings_dir or Path.home() / ".sunwell" / "bindings"

        # RFC-101: Global binding index
        self._index_manager = BindingIndexManager(
            bindings_dir=self._bindings_dir
        )

    # =========================================================================
    # RFC-101: URI Resolution
    # =========================================================================

    def resolve_uri(self, identifier: str) -> str:
        """Resolve an identifier to a full URI.

        Accepts:
        - Full URI: "sunwell:binding/global/writer" -> passed through
        - Bare slug: "writer" -> resolved to first match (project > global)

        Args:
            identifier: Full URI or bare slug

        Returns:
            Full URI string

        Raises:
            ValueError: If identifier cannot be resolved
        """
        # Already a full URI?
        if identifier.startswith("sunwell:"):
            return identifier

        # Bare slug - resolve via index
        entry = self._index_manager.resolve_slug(identifier, self.project)
        if entry:
            return entry.uri

        raise ValueError(f"Cannot resolve binding: {identifier}")

    def parse_uri(self, uri: str) -> SunwellURI:
        """Parse a URI string to SunwellURI."""
        return SunwellURI.parse(uri)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        name: str,
        lens_path: str | None = None,
        lens_uri: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        project: str | None = None,
        **settings: object,
    ) -> Binding:
        """Create a new binding (attune to a lens).

        RFC-101: Creates binding with proper identity.

        Args:
            name: Binding name
            lens_path: Path to lens file (legacy)
            lens_uri: URI of the lens (preferred)
            provider: LLM provider
            model: Model name
            project: Project slug (None = global)
            **settings: Additional binding settings

        Returns:
            Created Binding
        """
        from sunwell.foundation.config import get_config

        cfg = get_config()

        # Resolve provider from config if not specified
        if provider is None:
            provider = cfg.model.default_provider if cfg else "ollama"

        # Auto-select model based on provider if not specified
        # Priority: explicit model > provider-specific default > config default
        if model is None:
            model = _DEFAULT_MODELS.get(provider, cfg.model.default_model if cfg else "gpt-4o")

        # Create identity
        namespace = project or self.project or "global"
        slug = slugify(name)
        uri = create_binding_uri(slug, namespace if namespace != "global" else None)
        identity = create_binding_identity(uri)

        # Determine lens reference
        effective_lens_uri = lens_uri
        if (
            not effective_lens_uri
            and lens_path
            and "/" not in lens_path
            and "\\" not in lens_path
        ):
            # Convert path to URI if it looks like a slug
            effective_lens_uri = f"sunwell:lens/user/{lens_path}"
        elif not effective_lens_uri and lens_path:
            # Keep file path as-is for actual file paths
            effective_lens_uri = lens_path

        binding = Binding(
            name=name,
            lens_path=lens_path or "",  # Preserved for backwards compatibility
            uri=str(uri),
            id=str(identity.id),
            lens_uri=effective_lens_uri,
            provider=provider,
            model=model,
            **settings,  # type: ignore[arg-type]
        )

        self._save(binding, namespace)

        # Update index
        self._update_index(binding, namespace)

        return binding

    def get(self, name: str) -> Binding | None:
        """Get a binding by name or URI.

        RFC-101: Accepts full URI or bare slug.
        """
        # Try to resolve as URI
        try:
            uri = self.resolve_uri(name)
            parsed = SunwellURI.parse(uri)
            path = self._get_binding_path(parsed.namespace, parsed.slug)
            if path and path.exists():
                return Binding.load(path)
        except ValueError:
            pass

        return None

    def get_or_default(self, name: str | None = None) -> Binding | None:
        """Get binding by name, or default if no name provided."""
        if name:
            return self.get(name)
        return self.get_default()

    def get_default(self) -> Binding | None:
        """Get the default binding.

        Resolution order:
        1. Project config: .sunwell/config.yaml -> binding.default
        2. User config: ~/.sunwell/config.yaml -> binding.default
        4. Legacy: Global index is_default flag (deprecated)
        """
        from sunwell.foundation.config import get_config

        # Try config first (project-local → user-global)
        try:
            config = get_config()
            if config.binding.default:
                binding = self.get(config.binding.default)
                if binding:
                    return binding
        except Exception:
            pass  # Config not available, continue

        # Fall back to global index is_default flag
        entries = self._index_manager.list_bindings(namespace="global")
        for entry in entries:
            if entry.is_default:
                return self.get(entry.uri)

        return None

    def set_default(self, name: str) -> bool:
        """Set the default binding.

        RFC-101: Updates both file and index.
        """
        binding = self.get(name)
        if not binding:
            return False

        # Default binding is stored in config, not file

        # Update index
        if binding.uri:
            parsed = SunwellURI.parse(binding.uri)
            self._index_manager.set_default(binding.uri, parsed.namespace)

        return True

    def list_all(self, project: str | None = None) -> list[Binding]:
        """List all bindings.

        RFC-101: Uses index for fast listing.

        Args:
            project: Filter by project (None = all)

        Returns:
            List of bindings sorted by last_used
        """
        # Get from index
        entries = self._index_manager.list_bindings(project=project or self.project)

        bindings = []
        indexed_slugs: set[str] = set()  # Build during first pass to avoid duplicate parsing

        for entry in entries:
            parsed = SunwellURI.parse(entry.uri)
            indexed_slugs.add(parsed.slug)
            path = self._get_binding_path(parsed.namespace, parsed.slug)
            if path and path.exists():
                try:
                    bindings.append(Binding.load(path))
                except (json.JSONDecodeError, KeyError):
                    continue

        return sorted(bindings, key=lambda b: b.last_used, reverse=True)

    def delete(self, name: str) -> bool:
        """Delete a binding.

        RFC-101: Removes from both filesystem and index.

        Returns:
            True if binding was found and deleted, False otherwise.
        """
        # Try to resolve URI
        try:
            uri = self.resolve_uri(name)
            parsed = SunwellURI.parse(uri)
            path = self._get_binding_path(parsed.namespace, parsed.slug)
            deleted = False
            if path and path.exists():
                path.unlink()
                deleted = True
            # Also remove from index (may succeed even if file wasn't found)
            index_removed = self._index_manager.remove_binding(uri)
            return deleted or index_removed
        except ValueError:
            return False

    def use(self, name: str) -> Binding | None:
        """Get a binding and mark it as used."""
        binding = self.get(name)
        if binding:
            binding.touch()

            # Determine namespace from URI or default
            namespace = "global"
            if binding.uri:
                parsed = SunwellURI.parse(binding.uri)
                namespace = parsed.namespace

            self._save(binding, namespace)
            self._update_index(binding, namespace)
        return binding

    # =========================================================================
    # Index Management
    # =========================================================================

    def rebuild_index(self) -> None:
        """Force rebuild of the binding index."""
        self._index_manager.rebuild_index()

    def get_index_entry(self, uri: str) -> BindingIndexEntry | None:
        """Get index entry for a binding."""
        return self._index_manager.get_entry(uri)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _get_binding_path(self, namespace: str, slug: str) -> Path | None:
        """Get filesystem path for a binding."""
        if namespace == "global":
            # Use global path
            return self._bindings_dir / "global" / f"{slug}.json"
        else:
            # Project-scoped binding
            return self._bindings_dir / "projects" / namespace / f"{slug}.json"

    def _save(self, binding: Binding, namespace: str = "global") -> None:
        """Save a binding to the appropriate location."""
        slug = slugify(binding.name)

        if namespace == "global":
            # Save to global location
            new_path = self._bindings_dir / "global" / f"{slug}.json"
            new_path.parent.mkdir(parents=True, exist_ok=True)
            binding.save(new_path)
        else:
            # Project-scoped binding
            path = self._bindings_dir / "projects" / namespace / f"{slug}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            binding.save(path)

    def _update_index(self, binding: Binding, namespace: str) -> None:
        """Update the index with a binding."""
        uri = binding.uri or f"sunwell:binding/{namespace}/{slugify(binding.name)}"
        entry = BindingIndexEntry(
            uri=uri,
            id=binding.id or "",
            display_name=binding.name,
            namespace=namespace,
            lens_uri=binding.get_lens_reference(),
            provider=binding.provider,
            model=binding.model,
            is_default=False,
            last_used=binding.last_used,
            use_count=binding.use_count,
        )
        self._index_manager.add_binding(entry)


# Convenience function for CLI
def get_binding_or_create_temp(
    binding_name: str | None,
    lens_path: str | None,
    provider: str | None,
    model: str | None,
    simulacrum: str | None,
    *,
    bindings_dir: Path | None = None,
) -> tuple[Binding | None, bool]:
    """Get existing binding or create temporary one from CLI args.

    Args:
        binding_name: Name of existing binding to load.
        lens_path: Path to lens file for temp binding.
        provider: LLM provider override.
        model: Model name override.
        simulacrum: Simulacrum name override.
        bindings_dir: Custom bindings directory (for test isolation).

    Returns:
        Tuple of (binding, is_temporary).
    """
    manager = BindingManager(bindings_dir=bindings_dir)

    # If binding name provided, try to load it
    if binding_name:
        binding = manager.use(binding_name)
        if binding:
            # Override with any CLI args provided
            if provider:
                binding.provider = provider
            if model:
                binding.model = model
            if simulacrum:
                binding.simulacrum = simulacrum
            return binding, False

    # Try default binding
    if not lens_path:
        default = manager.get_default()
        if default:
            default.touch()
            if provider:
                default.provider = provider
            if model:
                default.model = model
            if simulacrum:
                default.simulacrum = simulacrum
            return default, False

    # Create temporary binding (not saved)
    if lens_path:
        # Convert path to URI if it's a slug, otherwise keep as file path
        lens_uri = lens_path
        if "/" not in lens_path and "\\" not in lens_path:
            lens_uri = f"sunwell:lens/user/{lens_path}"
        temp = Binding(
            name="_temp",
            lens_path=lens_path,  # Preserved for backwards compatibility
            lens_uri=lens_uri,
            provider=provider or "ollama",
            model=model or "gemma3:4b",
            simulacrum=simulacrum,
        )
        return temp, True

    return None, False
