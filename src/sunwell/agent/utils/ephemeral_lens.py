"""Ephemeral Lens Generation - Smart-to-Dumb Model Delegation.

A smart model analyzes the task and codebase, then generates an EphemeralLens
that encodes its understanding. A cheaper model then executes using this lens.

This is a key cost optimization: think once, generate many.
"""

import json
import logging
from typing import TYPE_CHECKING

from sunwell.foundation.core.lens import EphemeralLens

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)

# Prompt for generating ephemeral lenses
_GENERATION_PROMPT = """You are creating an expertise lens for a code generation task.

Analyze the task and context, then output a structured lens that will guide a simpler model
to generate high-quality code. The simpler model will follow your guidance exactly.

TASK: {task}

CONTEXT:
{context}

Output a JSON object with these fields:
{{
  "heuristics": ["guideline 1", "guideline 2", ...],  // 3-7 domain-specific guidelines
  "patterns": ["pattern 1", "pattern 2", ...],        // 3-5 code patterns to follow
  "anti_patterns": ["avoid 1", "avoid 2", ...],       // 2-4 things to avoid
  "constraints": ["constraint 1", ...],               // 1-3 hard requirements
  "examples": ["code snippet 1", ...],                // 1-2 style examples (optional)
  "task_scope": "brief description of what this lens covers"
}}

Guidelines should be specific and actionable, not generic advice.
Focus on what makes THIS task's code good, not general best practices.

Output ONLY the JSON object, no explanation."""


async def create_ephemeral_lens(
    model: "ModelProtocol",
    task: str,
    context: str = "",
    target_files: tuple[str, ...] = (),
) -> EphemeralLens:
    """Generate an ephemeral lens using a smart model.

    The smart model analyzes the task and context, then outputs a structured
    lens that encodes its understanding. This lens can then be used with a
    cheaper model for actual generation.

    Args:
        model: Smart model (e.g., Opus, o1) for analysis
        task: Task description
        context: Additional context (codebase summary, existing code, etc.)
        target_files: Files that will be generated/modified

    Returns:
        EphemeralLens ready to use with AgentLoop

    Example:
        >>> lens = await create_ephemeral_lens(
        ...     model=opus,
        ...     task="Build user authentication API",
        ...     context=existing_models,
        ... )
        >>> # Now use lens with cheaper model
        >>> loop = AgentLoop(model=haiku, ...)
    """
    from sunwell.models import GenerateOptions

    prompt = _GENERATION_PROMPT.format(
        task=task,
        context=context or "No additional context provided.",
    )

    model_id = getattr(model, "model_id", "unknown")

    try:
        result = await model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.3,  # Low temperature for structured output
                max_tokens=2000,
            ),
        )

        content = result.content or result.text or ""

        # Parse JSON from response
        lens_data = _parse_lens_json(content)

        return EphemeralLens(
            heuristics=tuple(lens_data.get("heuristics", [])),
            patterns=tuple(lens_data.get("patterns", [])),
            anti_patterns=tuple(lens_data.get("anti_patterns", [])),
            constraints=tuple(lens_data.get("constraints", [])),
            examples=tuple(lens_data.get("examples", [])),
            task_scope=lens_data.get("task_scope", task[:100]),
            target_files=target_files,
            generated_by=model_id,
            generation_prompt=prompt,
        )

    except Exception as e:
        logger.warning("Failed to generate ephemeral lens: %s", e)
        # Return minimal lens on failure
        return EphemeralLens(
            heuristics=("Follow best practices for the language/framework",),
            task_scope=task[:100],
            generated_by=model_id,
        )


def _parse_lens_json(content: str) -> dict:
    """Parse JSON from model response, handling common issues."""
    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed content
        import re

        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse lens JSON from response")
        return {}


async def should_use_delegation(
    task: str,
    estimated_tokens: int,
    budget_remaining: int,
) -> bool:
    """Decide whether to use smart→dumb delegation for a task.

    Delegation is beneficial when:
    - Task requires significant generation (many tokens)
    - Budget is limited
    - Task is "routine" (doesn't need smart model throughout)

    Args:
        task: Task description
        estimated_tokens: Estimated output tokens
        budget_remaining: Remaining token budget

    Returns:
        True if delegation would be cost-effective
    """
    # Simple heuristics for now
    # In future, could use a classifier

    # Large generation tasks benefit from delegation
    if estimated_tokens > 2000:
        return True

    # Low budget situations benefit from delegation
    if budget_remaining < estimated_tokens * 3:
        return True

    # Multiple file generation benefits from delegation
    file_indicators = ("files", "endpoints", "components", "modules")
    if any(ind in task.lower() for ind in file_indicators):
        return True

    return False
