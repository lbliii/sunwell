"""JSON and response parsing utilities for artifact planner."""

import json
import re
from typing import TYPE_CHECKING

from sunwell.planning.naaru.artifacts import ArtifactSpec

if TYPE_CHECKING:
    pass

# Pre-compiled regex patterns for LLM response parsing (avoid recompiling per call)
_RE_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_RE_JSON_CODE_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


def extract_json(response: str) -> list[dict] | None:
    """Extract JSON array from LLM response.

    Args:
        response: LLM response text

    Returns:
        Parsed JSON array or None if parsing fails
    """
    # Strategy 1: Find JSON array with regex
    json_match = _RE_JSON_ARRAY.search(response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 2: Look for code block with JSON
    code_match = _RE_JSON_CODE_BLOCK.search(response)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Try parsing entire response
    try:
        data = json.loads(response)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    return None


def parse_artifacts(response: str) -> list[ArtifactSpec]:
    """Parse LLM response into ArtifactSpec objects.

    Args:
        response: LLM response text

    Returns:
        List of parsed ArtifactSpec objects
    """
    artifacts_data = extract_json(response)

    if not artifacts_data:
        return []

    artifacts = []
    for item in artifacts_data:
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
            # Skip malformed artifacts
            continue

    return artifacts


def extract_code(response: str, filename: str | None = None) -> str:
    """Extract code from LLM response.

    Args:
        response: LLM response text
        filename: Optional filename hint for extraction

    Returns:
        Extracted code content
    """
    import re

    # Pre-compiled regex for code blocks
    _RE_CODE_BLOCK = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)

    # Try to extract from code block
    code_match = _RE_CODE_BLOCK.search(response)
    if code_match:
        return code_match.group(1).strip()

    # Fallback: return response as-is (might be plain code)
    return response.strip()
