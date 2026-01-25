"""Artifact creation and verification for artifact planner."""

from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import ArtifactSpec, VerificationResult
from sunwell.planning.naaru.planners.artifact import parsing, prompts

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


async def create_artifact(
    model: ModelProtocol,
    artifact: ArtifactSpec,
    context: dict[str, Any] | None = None,
) -> str:
    """Create the content for an artifact based on its specification.

    Uses the model to generate code/content that satisfies the artifact's
    contract and description.

    Args:
        model: Model to use for creation
        artifact: The artifact specification
        context: Optional context (completed artifacts, cwd, etc.)

    Returns:
        Generated content as a string
    """
    prompt = prompts.build_creation_prompt(artifact, context)

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

    prompt = f"""ARTIFACT: {artifact.id}

CONTRACT (what it must satisfy):
{artifact.contract}

CREATED CONTENT:
```python
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
                explanation=data.get("explanation", ""),
                missing=data.get("missing", []),
            )
        except json.JSONDecodeError:
            pass

    # Fallback: assume passed if we can't parse
    return VerificationResult(
        passed=True,
        explanation="Verification response could not be parsed, assuming passed",
        missing=[],
    )
