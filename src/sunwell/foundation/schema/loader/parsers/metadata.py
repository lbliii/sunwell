"""Metadata and reference parsing."""

from typing import Any

from sunwell.core.types.types import LensReference, SemanticVersion
from sunwell.foundation.core.lens import LensMetadata


def parse_metadata(data: dict[str, Any]) -> LensMetadata:
    """Parse lens metadata.

    RFC-035: Also parses compatible_schemas for domain-specific lenses.
    RFC-070: Also parses library metadata (use_cases, tags, icon).
    """
    name = data.get("name", "Unnamed Lens")

    version = SemanticVersion(0, 1, 0)
    if "version" in data:
        version = SemanticVersion.parse(data["version"])

    # RFC-035: Parse compatible_schemas
    compatible_schemas = tuple(data.get("compatible_schemas", []))

    # RFC-070: Parse library metadata
    use_cases = tuple(data.get("use_cases", []))
    tags = tuple(data.get("tags", []))
    icon = data.get("icon")

    return LensMetadata(
        name=name,
        domain=data.get("domain"),
        version=version,
        description=data.get("description"),
        author=data.get("author"),
        license=data.get("license"),
        compatible_schemas=compatible_schemas,
        use_cases=use_cases,
        tags=tags,
        icon=icon,
    )


def parse_lens_reference(data: str | dict) -> LensReference:
    """Parse a lens reference."""
    if isinstance(data, str):
        # Simple string reference "sunwell/tech-writer@1.0"
        if "@" in data:
            source, version = data.rsplit("@", 1)
            return LensReference(source=source, version=version)
        return LensReference(source=data)

    return LensReference(
        source=data["lens"],
        version=data.get("version"),
        priority=data.get("priority", 1),
    )
