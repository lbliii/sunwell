"""JSON parsing utilities for harmonic planning."""

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.naaru.artifacts import ArtifactSpec

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_RE_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_RE_JSON_CODE_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


def parse_artifacts(response: str) -> list[ArtifactSpec]:
    """Parse LLM response into ArtifactSpec objects."""
    from sunwell.naaru.artifacts import ArtifactSpec

    # Strategy 1: Find JSON array with regex
    json_match = _RE_JSON_ARRAY.search(response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return specs_from_data(data)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Look for code block with JSON
    code_match = _RE_JSON_CODE_BLOCK.search(response)
    if code_match:
        try:
            data = json.loads(code_match.group(1))
            return specs_from_data(data)
        except json.JSONDecodeError:
            pass

    return []


def specs_from_data(data: list[dict]) -> list[ArtifactSpec]:
    """Convert parsed JSON to ArtifactSpec list."""
    from sunwell.naaru.artifacts import ArtifactSpec

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
