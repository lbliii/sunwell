"""Artifact creation and verification for artifact planner."""

import logging
from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import ArtifactSpec, VerificationResult
from sunwell.planning.naaru.planners.artifact import parsing, prompts

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)


async def create_artifact(
    model: ModelProtocol,
    artifact: ArtifactSpec,
    context: dict[str, Any] | None = None,
    goal: str | None = None,
) -> str:
    """Create the content for an artifact based on its specification.

    Uses the model to generate code/content that satisfies the artifact's
    contract and description.

    Args:
        model: Model to use for creation
        artifact: The artifact specification
        context: Optional context (completed artifacts, cwd, etc.)
        goal: Optional goal for language detection fallback

    Returns:
        Generated content as a string
    """
    # Extract goal from context if not provided
    if goal is None and context:
        goal = context.get("goal")

    prompt = prompts.build_creation_prompt(artifact, context, goal=goal)

    from sunwell.models import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.2, max_tokens=4000),
    )

    # Extract code from response (may be wrapped in markdown code blocks)
    content = result.content or ""
    return parsing.extract_code(content, artifact.produces_file)


async def verify_artifact(
    model: ModelProtocol,
    artifact: ArtifactSpec,
    created_content: str,
) -> VerificationResult:
    """Verify that created content satisfies the artifact's contract.

    Uses LLM-based verification to check if the implementation
    matches the specification.

    Args:
        model: Model to use for verification
        artifact: The artifact specification
        created_content: The actual content that was created

    Returns:
        VerificationResult with pass/fail and explanation
    """
    # Truncate very long content
    content_preview = created_content[:3000]
    if len(created_content) > 3000:
        content_preview += "\n... [truncated]"

    # Determine file extension for code block
    file_ext = ""
    if artifact.produces_file and "." in artifact.produces_file:
        file_ext = artifact.produces_file.split(".")[-1]

    prompt = f"""ARTIFACT: {artifact.id}

CONTRACT (what it must satisfy):
{artifact.contract}

CREATED CONTENT:
```{file_ext}
{content_preview}
```

=== VERIFICATION ===

Does the created content satisfy the contract?

Check:
1. Does it implement all requirements from the contract?
2. Is it complete (no placeholders, TODOs, or stubs)?
3. Does it match the description: "{artifact.description}"?

Respond with JSON:
{{
  "passed": true/false,
  "explanation": "Brief explanation of why it passed or failed",
  "missing": ["list", "of", "missing", "requirements"]  // if failed
}}"""

    from sunwell.models import GenerateOptions

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=500),
    )

    # Parse verification result
    import json
    import re

    content = result.content or ""
    json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return VerificationResult(
                passed=data.get("passed", False),
                reason=data.get("explanation", ""),
                gaps=tuple(data.get("missing", [])),
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse verification JSON for artifact '{artifact.id}': {e}",
                extra={
                    "artifact_id": artifact.id,
                    "error": str(e),
                    "attempted_json": json_match.group()[:300],
                }
            )

    # CRITICAL FIX: Fail-safe behavior - reject unparseable verifications
    # Previously this was 'passed=True' which allowed bad artifacts through
    logger.error(
        f"Verification response for artifact '{artifact.id}' could not be parsed. "
        f"FAILING verification for safety (requires manual review). "
        f"Response preview: {content[:500]}",
        extra={
            "artifact_id": artifact.id,
            "response_length": len(content),
            "response_preview": content[:500],
        }
    )
    return VerificationResult(
        passed=False,
        reason="Verification response malformed - requires manual review",
        gaps=("unparseable_verification_response",),
    )
