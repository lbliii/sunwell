"""JSON parsing utilities for harmonic planning.

RFC-135: This module now delegates to the validated artifact parsing
to ensure consistent validation across all planning paths.
"""

from typing import TYPE_CHECKING

# Re-export from artifact parsing for backwards compatibility
from sunwell.planning.naaru.planners.artifact.parsing import (
    extract_json,
    parse_artifacts,
    validate_artifact,
)

if TYPE_CHECKING:
    from sunwell.planning.naaru.artifacts import ArtifactSpec


def specs_from_data(data: list[dict]) -> list[ArtifactSpec]:
    """Convert parsed JSON to ArtifactSpec list.

    DEPRECATED: Use parse_artifacts() from artifact.parsing instead.
    This function is kept for backwards compatibility but doesn't
    apply validation.
    """
    from sunwell.planning.naaru.artifacts import ArtifactSpec

    artifacts = []
    for item in data:
        try:
            artifact = ArtifactSpec(
                id=item["id"],
                description=item.get("description", f"Artifact {item['id']}"),
                contract=item.get("contract", ""),
                produces_file=item.get("produces_file"),
                requires=frozenset(item.get("requires", [])),
                domain_type=item.get("domain_type"),
                metadata=item.get("metadata", {}),
            )
            artifacts.append(artifact)
        except (KeyError, TypeError):
            continue
    return artifacts


__all__ = ["extract_json", "parse_artifacts", "validate_artifact", "specs_from_data"]
