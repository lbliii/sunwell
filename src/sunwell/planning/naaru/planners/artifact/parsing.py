"""JSON and response parsing utilities for artifact planner.

Provides:
- extract_json: Extract JSON arrays from LLM responses
- parse_artifacts: Parse JSON into ArtifactSpec objects with validation
- validate_artifact: Validate artifacts against schema and boundaries (RFC-135)
"""

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.planning.naaru.artifacts import ArtifactSpec

if TYPE_CHECKING:
    from sunwell.knowledge.project.schema import ProjectSchema

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for LLM response parsing (avoid recompiling per call)
_RE_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_RE_JSON_CODE_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


def extract_json(response: str) -> list[dict] | None:
    """Extract JSON array from LLM response with diagnostic logging.

    Tries three strategies in order:
    1. Regex match for JSON array
    2. Code block extraction
    3. Full response parsing

    Args:
        response: LLM response text

    Returns:
        Parsed JSON array or None if all strategies fail
    """
    # Strategy 1: Find JSON array with regex
    json_match = _RE_JSON_ARRAY.search(response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.debug(
                f"JSON extraction strategy 1 (regex array) failed: {e}",
                extra={
                    "strategy": "regex_array",
                    "error": str(e),
                    "attempted_content": json_match.group()[:200],
                }
            )

    # Strategy 2: Look for code block with JSON
    code_match = _RE_JSON_CODE_BLOCK.search(response)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError as e:
            logger.debug(
                f"JSON extraction strategy 2 (code block) failed: {e}",
                extra={
                    "strategy": "code_block",
                    "error": str(e),
                    "attempted_content": code_match.group(1)[:200],
                }
            )

    # Strategy 3: Try parsing entire response
    try:
        data = json.loads(response)
        if isinstance(data, list):
            return data
        else:
            logger.debug(
                f"JSON extraction strategy 3 succeeded but result is not a list: {type(data)}",
                extra={"strategy": "full_response", "result_type": type(data).__name__}
            )
    except json.JSONDecodeError as e:
        logger.debug(
            f"JSON extraction strategy 3 (full response) failed: {e}",
            extra={
                "strategy": "full_response",
                "error": str(e),
                "response_preview": response[:200],
            }
        )

    # All strategies exhausted
    logger.warning(
        f"Failed to extract JSON array from LLM response (all 3 strategies failed). "
        f"Response length: {len(response)} chars. Preview: {response[:300]!r}",
        extra={
            "response_length": len(response),
            "response_preview": response[:500],
            "strategies_tried": ["regex_array", "code_block", "full_response"],
        }
    )
    return None


def _is_meta_artifact(artifact_id: str, produces_file: str | None) -> bool:
    """Check if artifact is a meta-artifact that shouldn't be created as a project file.
    
    Meta-artifacts are internal state files that the LLM sometimes hallucinates,
    like "key_learnings.md", "personal_reflection.md", "generated_code.py", etc.
    These should either not be created or go to .sunwell/ instead.
    """
    id_lower = artifact_id.lower()
    file_lower = (produces_file or "").lower()

    # Reject generic/meta artifact IDs
    meta_patterns = (
        "learning", "reflection", "summary", "notes", "thoughts",
        "generated_code", "output", "result", "response", "answer",
        "analysis", "findings", "observations", "insights", "takeaways",
    )

    for pattern in meta_patterns:
        if pattern in id_lower:
            return True
        if pattern in file_lower:
            return True

    # Reject files that look like internal state
    meta_files = (
        "key_learnings", "personal_reflection", "generated_code.py",
        "learnings.md", "notes.md", "summary.md", "thoughts.md",
    )

    return any(mf in file_lower for mf in meta_files)


# Forbidden path prefixes - these are internal/system directories
_FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = (
    ".sunwell/",
    ".git/",
    "__pycache__/",
    "node_modules/",
    ".venv/",
    "venv/",
    ".env/",
)


def validate_artifact(
    artifact: ArtifactSpec,
    schema: ProjectSchema | None = None,
    workspace: Path | None = None,
) -> tuple[bool, str | None]:
    """Validate artifact against schema and boundaries (RFC-135).

    Performs three levels of validation:
    1. Path boundary check - artifacts cannot write to internal directories
    2. Schema validation - if schema exists, domain_type must be valid
    3. Meta-artifact filter - rejects hallucinated internal state files

    Args:
        artifact: The artifact to validate
        schema: Optional project schema for type validation
        workspace: Optional workspace path (currently unused, for future)

    Returns:
        Tuple of (is_valid, rejection_reason)
        If is_valid is True, rejection_reason is None.

    Example:
        >>> is_valid, reason = validate_artifact(my_artifact, schema)
        >>> if not is_valid:
        ...     logger.warning(f"Rejected: {reason}")
    """
    produces_file = artifact.produces_file

    # Check 1: Path boundary - must not write to internal directories
    if produces_file:
        for prefix in _FORBIDDEN_PATH_PREFIXES:
            if produces_file.startswith(prefix):
                return False, f"Path writes to forbidden directory: {prefix}"

    # Check 2: Schema validation - domain_type must be valid if schema provided
    if schema and artifact.domain_type:
        if artifact.domain_type not in schema.artifact_types:
            valid_types = list(schema.artifact_types.keys())
            return False, f"Unknown artifact type '{artifact.domain_type}'. Valid: {valid_types}"

    # Check 3: Meta-artifact filter - reject hallucinated internal state
    if _is_meta_artifact(artifact.id, produces_file):
        return False, "Meta-artifacts (learnings, reflections, summaries) are not deliverables"

    return True, None


def validate_artifact_path(path: str) -> tuple[bool, str | None]:
    """Validate that an artifact path doesn't write to forbidden directories.

    Convenience function for validating paths outside of ArtifactSpec context.

    Args:
        path: The path to validate

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    for prefix in _FORBIDDEN_PATH_PREFIXES:
        if path.startswith(prefix):
            return False, f"Path writes to forbidden directory: {prefix}"
    return True, None


def parse_artifacts(
    response: str,
    schema: ProjectSchema | None = None,
    workspace: Path | None = None,
) -> list[ArtifactSpec]:
    """Parse LLM response into ArtifactSpec objects with validation.

    Args:
        response: LLM response text
        schema: Optional project schema for type validation (RFC-035)
        workspace: Optional workspace path for boundary checks

    Returns:
        List of parsed and validated ArtifactSpec objects
        Invalid artifacts are logged and filtered out.
    """
    artifacts_data = extract_json(response)

    if not artifacts_data:
        return []

    artifacts = []
    for item in artifacts_data:
        try:
            artifact_id = item["id"]
            produces_file = item.get("produces_file")

            artifact = ArtifactSpec(
                id=artifact_id,
                description=item.get("description", f"Artifact {artifact_id}"),
                contract=item.get("contract", ""),
                produces_file=produces_file,
                requires=frozenset(item.get("requires", [])),
                domain_type=item.get("domain_type"),
                metadata=item.get("metadata", {}),
            )

            # Validate artifact against schema and boundaries
            is_valid, reason = validate_artifact(artifact, schema, workspace)
            if not is_valid:
                logger.info(f"Filtered artifact '{artifact_id}': {reason}")
                continue

            artifacts.append(artifact)
        except (KeyError, TypeError) as e:
            # Skip malformed artifacts but log what was wrong
            logger.warning(
                f"Skipping malformed artifact in response: {e}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "artifact_data": str(item)[:300],
                }
            )
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
