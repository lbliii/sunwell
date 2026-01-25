"""Diversity Layer - Generate multiple perspectives from the model (RFC-033).

This module implements the Diversity Layer of Naaru's unified architecture.
It provides four strategies for generating diverse candidates:
- none: Single generation (baseline)
- sampling: Temperature-based diversity (zero prompt overhead)
- rotation: Cognitive frame markers (integrated perspectives)
- harmonic: Multi-persona generation (maximum diversity)
"""


import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import GenerateOptions, ModelProtocol


@dataclass(frozen=True, slots=True)
class Candidate:
    """A candidate output from the diversity layer."""

    text: str
    """The generated text."""

    source: str
    """Source identifier (e.g., 'single', 'temp_0.7', 'rotation', 'adversary')."""

    temperature: float | None = None
    """Temperature used (if applicable)."""

    persona: str | None = None
    """Persona name (if applicable)."""

    frames: dict[str, str] | None = None
    """Parsed frames from rotation (if applicable)."""

    tokens: int = 0
    """Token count for this candidate."""


# Hardcoded personas for Harmonic Synthesis
HARMONIC_PERSONAS: dict[str, tuple[str, float]] = {
    "adversary": (
        "You MUST find ways to break this. Assume the worst case. "
        "Look for security holes, edge cases that crash, race conditions. "
        "Be paranoid and adversarial.",
        0.4,  # Low temp: methodical, focused attack
    ),
    "advocate": (
        "You MUST defend this solution. Find its strengths. "
        "Explain why this approach is good. Be optimistic and supportive. "
        "Show how it solves the problem elegantly.",
        0.7,  # Medium temp: balanced defense
    ),
    "naive": (
        "You know NOTHING about this domain. Ask obvious questions. "
        "What would a complete beginner wonder? What's confusing? "
        "Point out things that seem weird or unexplained.",
        1.0,  # High temp: wild, unexpected questions
    ),
}


async def diversity_none(
    model: ModelProtocol,
    prompt: str,
    options: GenerateOptions | None = None,
) -> list[Candidate]:
    """Diversity Strategy: None - Single generation, no diversity.

    Args:
        model: The model to use for generation
        prompt: The input prompt
        options: Optional generation options

    Returns:
        List with a single candidate

    Cost: 1x (baseline)
    Use when: Deterministic tasks, simple questions, cost-constrained
    """
    if options is None:
        from sunwell.models import GenerateOptions
        options = GenerateOptions()

    result = await model.generate(prompt, options=options)
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    return [
        Candidate(
            text=result.text,
            source="single",
            tokens=tokens,
        )
    ]


async def diversity_sampling(
    model: ModelProtocol,
    prompt: str,
    temps: Sequence[float] = (0.3, 0.7, 1.0),
    options: GenerateOptions | None = None,
) -> list[Candidate]:
    """Diversity Strategy: Sampling - Same prompt, different temperatures.

    Achieves diversity through sampling parameters with zero prompt overhead.

    Args:
        model: The model to use for generation
        prompt: The input prompt
        temps: Temperature values to use (default: 0.3, 0.7, 1.0)
        options: Base generation options (temperature will be overridden)

    Returns:
        List of candidates, one per temperature

    Cost: Nx completions, 0 extra prompt tokens
    Use when: Non-deterministic tasks, need diversity cheaply
    """
    if options is None:
        from sunwell.models import GenerateOptions
        options = GenerateOptions()

    async def generate_with_temp(temp: float) -> Candidate:
        temp_options = GenerateOptions(
            temperature=temp,
            max_tokens=options.max_tokens,
            system_prompt=options.system_prompt,
        )
        result = await model.generate(prompt, options=temp_options)
        tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        return Candidate(
            text=result.text,
            source=f"temp_{temp}",
            temperature=temp,
            tokens=tokens,
        )

    candidates = await asyncio.gather(*[generate_with_temp(t) for t in temps])
    return list(candidates)


async def diversity_rotation(
    model: ModelProtocol,
    prompt: str,
    options: GenerateOptions | None = None,
) -> list[Candidate]:
    """Diversity Strategy: Rotation - Single generation (rotation removed).

    Note: Cognitive frame rotation was removed after benchmarking showed
    no quality improvement for 20B+ models. This now behaves like diversity_none.

    Args:
        model: The model to use for generation
        prompt: The input prompt
        options: Optional generation options

    Returns:
        List with a single candidate
    """
    # Rotation removed - just do a single generation
    return await diversity_none(model, prompt, options)


async def diversity_harmonic(
    model: ModelProtocol,
    prompt: str,
    personas: dict[str, tuple[str, float]] | None = None,
    options: GenerateOptions | None = None,
) -> list[Candidate]:
    """Diversity Strategy: Harmonic - Multi-persona generation in parallel.

    Generates with multiple personas in parallel, each bringing different
    expertise. This is the most expensive but highest-quality diversity strategy.

    Args:
        model: The model to use for generation
        prompt: The input prompt
        personas: Dict mapping persona names to (prompt, temperature) tuples.
                  Defaults to HARMONIC_PERSONAS
        options: Base generation options

    Returns:
        List of candidates, one per persona

    Cost: 3.5x generation-only (3 parallel generations), ~6-8x with full Resonance
    Use when: High-stakes, maximum quality needed
    """
    if personas is None:
        personas = HARMONIC_PERSONAS

    if options is None:
        from sunwell.models import GenerateOptions
        options = GenerateOptions()

    async def generate_with_persona(
        name: str, persona_prompt: str, temp: float
    ) -> Candidate:
        persona_options = GenerateOptions(
            temperature=temp,
            max_tokens=options.max_tokens,
            system_prompt=persona_prompt,
        )
        result = await model.generate(prompt, options=persona_options)
        tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
        return Candidate(
            text=result.text,
            source=name,
            temperature=temp,
            persona=name,
            tokens=tokens,
        )

    candidates = await asyncio.gather(*[
        generate_with_persona(name, prompt_text, temp)
        for name, (prompt_text, temp) in personas.items()
    ])

    return list(candidates)
