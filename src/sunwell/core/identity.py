"""Unified identity system for Sunwell resources (RFC-101).

Provides canonical URI-based identification for lenses, bindings, and sessions.
Prevents name clashes, enables cross-device sync, and provides efficient resolution.

URI Format:
    sunwell:<resource_type>/<namespace>/<slug>[@<version>]

Examples:
    sunwell:lens/builtin/tech-writer@2.0.0
    sunwell:lens/user/my-custom-writer@latest
    sunwell:binding/myproject/writer
    sunwell:session/myproject/debug
"""

import re
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

ResourceType = Literal["lens", "binding", "session"]
Namespace = Literal["builtin", "user", "project", "global"]

# Regex for valid slug: lowercase alphanumeric with hyphens
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Regex for semver
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?$")


class URIParseError(ValueError):
    """Error parsing a SunwellURI."""


@dataclass(frozen=True, slots=True)
class SunwellURI:
    """Canonical resource identifier.

    Format: sunwell:<resource_type>/<namespace>/<slug>[@<version>]

    Attributes:
        resource_type: Type of resource (lens, binding, session)
        namespace: Resource namespace (builtin, user, project, global, or project slug)
        slug: Resource slug (filesystem-safe identifier)
        version: Optional version (semver, "latest", or "sha:" prefix). Only for lenses.
    """

    resource_type: ResourceType
    namespace: str
    slug: str
    version: str | None = None

    def __post_init__(self) -> None:
        """Validate URI components."""
        if self.resource_type not in ("lens", "binding", "session"):
            raise URIParseError(f"Invalid resource type: {self.resource_type}")

        if not self.slug:
            raise URIParseError("Slug cannot be empty")

        # Only lenses support versioning
        if self.version is not None and self.resource_type != "lens":
            raise URIParseError(f"Version not supported for {self.resource_type}")

    @classmethod
    def parse(cls, uri: str) -> SunwellURI:
        """Parse 'sunwell:type/namespace/slug[@version]'.

        Args:
            uri: Full URI string

        Returns:
            Parsed SunwellURI

        Raises:
            URIParseError: If URI format is invalid
        """
        if not uri.startswith("sunwell:"):
            raise URIParseError(f"Invalid URI scheme (expected 'sunwell:'): {uri}")

        rest = uri[8:]  # Remove "sunwell:"

        # Extract version if present
        if "@" in rest:
            path, version = rest.rsplit("@", 1)
            if not version:
                raise URIParseError(f"Empty version in URI: {uri}")
        else:
            path, version = rest, None

        parts = path.split("/")
        if len(parts) < 3:
            raise URIParseError(
                f"Invalid URI format (expected type/namespace/slug): {uri}"
            )

        resource_type = parts[0]
        namespace = parts[1]
        slug = "/".join(parts[2:])  # Allow nested slugs

        return cls(
            resource_type=resource_type,  # type: ignore[arg-type]
            namespace=namespace,
            slug=slug,
            version=version,
        )

    @classmethod
    def for_lens(
        cls,
        namespace: str,
        slug: str,
        version: str | None = None,
    ) -> SunwellURI:
        """Create a lens URI.

        Args:
            namespace: Lens namespace (builtin, user, or project slug)
            slug: Lens slug
            version: Optional version

        Returns:
            New SunwellURI for a lens
        """
        return cls(
            resource_type="lens",
            namespace=namespace,
            slug=slug,
            version=version,
        )

    @classmethod
    def for_binding(cls, namespace: str, slug: str) -> SunwellURI:
        """Create a binding URI.

        Args:
            namespace: Binding namespace (global or project slug)
            slug: Binding slug

        Returns:
            New SunwellURI for a binding
        """
        return cls(
            resource_type="binding",
            namespace=namespace,
            slug=slug,
        )

    @classmethod
    def for_session(cls, namespace: str, slug: str) -> SunwellURI:
        """Create a session URI.

        Args:
            namespace: Session namespace (project slug)
            slug: Session slug

        Returns:
            New SunwellURI for a session
        """
        return cls(
            resource_type="session",
            namespace=namespace,
            slug=slug,
        )

    def __str__(self) -> str:
        """Convert to URI string."""
        base = f"sunwell:{self.resource_type}/{self.namespace}/{self.slug}"
        return f"{base}@{self.version}" if self.version else base

    @property
    def is_builtin(self) -> bool:
        """Check if this is a built-in resource."""
        return self.namespace == "builtin"

    @property
    def is_user(self) -> bool:
        """Check if this is a user resource."""
        return self.namespace == "user"

    @property
    def is_project(self) -> bool:
        """Check if this is a project-scoped resource."""
        return self.namespace not in ("builtin", "user", "global")

    @property
    def is_versioned(self) -> bool:
        """Check if this URI specifies a concrete version."""
        return self.version is not None and self.version != "latest"

    @property
    def is_content_addressed(self) -> bool:
        """Check if this URI uses content-addressable versioning."""
        return self.version is not None and self.version.startswith("sha:")

    def with_version(self, version: str) -> SunwellURI:
        """Return new URI with specified version.

        Args:
            version: Version string (semver, "latest", or "sha:" prefix)

        Returns:
            New SunwellURI with the version set
        """
        return SunwellURI(
            self.resource_type,
            self.namespace,
            self.slug,
            version,
        )

    def without_version(self) -> SunwellURI:
        """Return new URI without version.

        Returns:
            New SunwellURI with version set to None
        """
        return SunwellURI(
            self.resource_type,
            self.namespace,
            self.slug,
            None,
        )


@dataclass(frozen=True, slots=True)
class ResourceIdentity:
    """Immutable resource identity with UUID.

    Provides stable identification that survives renames and moves.
    The UUID is the true identity; the URI is for human readability.

    Attributes:
        id: Universally unique identifier
        uri: Current canonical URI
        created_at: ISO format timestamp of creation
    """

    id: UUID
    uri: SunwellURI
    created_at: str

    @classmethod
    def create(cls, uri: SunwellURI) -> ResourceIdentity:
        """Create a new identity with a fresh UUID.

        Args:
            uri: The canonical URI for this resource

        Returns:
            New ResourceIdentity with generated UUID and timestamp
        """
        return cls(
            id=uuid4(),
            uri=uri,
            created_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ResourceIdentity:
        """Create from dictionary representation.

        Args:
            data: Dictionary with 'id', 'uri', and 'created_at' keys

        Returns:
            ResourceIdentity instance
        """
        return cls(
            id=UUID(data["id"]),
            uri=SunwellURI.parse(data["uri"]),
            created_at=data["created_at"],
        )

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with 'id', 'uri', and 'created_at' keys
        """
        return {
            "id": str(self.id),
            "uri": str(self.uri),
            "created_at": self.created_at,
        }

    def with_uri(self, uri: SunwellURI) -> ResourceIdentity:
        """Return new identity with updated URI (preserves UUID).

        Used when renaming a resource - the UUID stays the same.

        Args:
            uri: New URI for this resource

        Returns:
            New ResourceIdentity with same UUID but new URI
        """
        return ResourceIdentity(
            id=self.id,
            uri=uri,
            created_at=self.created_at,
        )


def parse_legacy_name(
    name: str,
    resource_type: ResourceType,
    check_user_exists: bool | None = None,
) -> SunwellURI:
    """Convert bare slug to full URI with deprecation warning.

    Resolution order for lenses: user -> builtin
    Resolution order for bindings: project -> global

    Args:
        name: Bare slug (e.g., "tech-writer")
        resource_type: Type of resource
        check_user_exists: Optional callback to check if user version exists

    Returns:
        Fully-qualified SunwellURI
    """
    warnings.warn(
        f"Bare slug '{name}' is deprecated. Use full URI: sunwell:{resource_type}/...",
        DeprecationWarning,
        stacklevel=3,
    )

    if resource_type == "lens":
        # Legacy behavior: user shadows builtin
        # Without filesystem check, default to user namespace for backwards compat
        namespace = "user"
        return SunwellURI.for_lens(namespace, name)

    elif resource_type == "binding":
        # Bindings default to global if no project context
        return SunwellURI.for_binding("global", name)

    elif resource_type == "session":
        # Sessions default to a generic project namespace
        return SunwellURI.for_session("default", name)

    # Should not reach here due to type checking
    raise URIParseError(f"Unknown resource type: {resource_type}")


def slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe slug.

    Args:
        name: Human-readable name

    Returns:
        Lowercase slug with hyphens
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def validate_slug(slug: str) -> None:
    """Validate a slug for path traversal attacks and format.

    Args:
        slug: Slug to validate

    Raises:
        ValueError: If slug is invalid
    """
    if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
        raise ValueError(f"Invalid slug (path traversal): {slug}")

    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f"Invalid slug format (use lowercase alphanumeric with hyphens): {slug}")
