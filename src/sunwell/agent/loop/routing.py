"""Confidence-based routing for the agentic tool loop.

Provides generation strategies:
- Single-shot: Standard generation for high confidence tasks
- Interference: 3 perspectives for medium confidence tasks
- Vortex: Multiple temperatures for low confidence tasks

This is a KEY DIFFERENTIATOR - competitors always use single-shot.
"""

import logging
from typing import TYPE_CHECKING, Literal

from sunwell.models import GenerateOptions, GenerateResult, Message

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol, Tool

logger = logging.getLogger(__name__)


async def single_shot_generate(
    model: ModelProtocol,
    messages: list[Message],
    tools: tuple[Tool, ...],
    tool_choice: Literal["auto", "none", "required"] | str,
    options: GenerateOptions,
) -> GenerateResult:
    """Standard single-shot generation."""
    return await model.generate(
        tuple(messages),
        tools=tools,
        tool_choice=tool_choice,
        options=options,
    )


async def interference_generate(
    model: ModelProtocol,
    messages: list[Message],
    tools: tuple[Tool, ...],
    tool_choice: Literal["auto", "none", "required"] | str,
    options: GenerateOptions,
) -> GenerateResult:
    """Generate with 3 perspectives and pick best (interference pattern).

    Like constructive/destructive interference in physics:
    - High agreement = constructive (amplified confidence in result)
    - Low agreement = destructive (signals uncertainty)
    """
    perspectives = ["analyst", "pragmatist", "expert"]
    candidates: list[GenerateResult] = []

    for perspective in perspectives:
        # Add perspective hint to system
        perspective_messages = list(messages)
        if perspective_messages and perspective_messages[0].role == "system":
            # Prepend to existing system prompt
            old_content = perspective_messages[0].content or ""
            perspective_messages[0] = Message(
                role="system",
                content=f"[Perspective: {perspective}] {old_content}",
            )
        else:
            # Insert new system message
            perspective_messages.insert(0, Message(
                role="system",
                content=f"Think from the perspective of a {perspective}.",
            ))

        try:
            result = await model.generate(
                tuple(perspective_messages),
                tools=tools,
                tool_choice=tool_choice,
                options=options,
            )
            candidates.append(result)
        except Exception:
            continue

    if not candidates:
        # All failed, fall back to single-shot
        return await single_shot_generate(model, messages, tools, tool_choice, options)

    # Select best candidate via voting/agreement
    return select_best_candidate(candidates)


async def vortex_generate(
    model: ModelProtocol,
    messages: list[Message],
    tools: tuple[Tool, ...],
    tool_choice: Literal["auto", "none", "required"] | str,
    options: GenerateOptions,
) -> GenerateResult:
    """Generate multiple candidates with different temperatures (Vortex).

    For low-confidence tasks, explore the solution space more thoroughly.
    """
    temperatures = [0.2, 0.5, 0.8]
    candidates: list[GenerateResult] = []

    for temp in temperatures:
        varied_options = GenerateOptions(
            temperature=temp,
            max_tokens=options.max_tokens,
            stop_sequences=options.stop_sequences,
        )

        try:
            result = await model.generate(
                tuple(messages),
                tools=tools,
                tool_choice=tool_choice,
                options=varied_options,
            )
            candidates.append(result)
        except Exception:
            continue

    if not candidates:
        return await single_shot_generate(model, messages, tools, tool_choice, options)

    return select_best_candidate(candidates)


def select_best_candidate(candidates: list[GenerateResult]) -> GenerateResult:
    """Select the best candidate from multiple generations.

    Preferences:
    1. Candidates with tool calls (actionable)
    2. Candidates with more tool calls (more complete)
    3. First candidate if tied
    """
    if not candidates:
        raise ValueError("No candidates to select from")

    # Prefer candidates with tool calls
    with_tools = [c for c in candidates if c.has_tool_calls]
    if with_tools:
        # Pick the one with most tool calls
        return max(with_tools, key=lambda c: len(c.tool_calls))

    # No tool calls - return first (most deterministic temperature)
    return candidates[0]


async def get_task_confidence(
    model: ModelProtocol,
    task_description: str | None,
    messages: list[Message],
) -> float:
    """Extract confidence for routing decisions.

    Uses signals extraction if available, otherwise defaults to high confidence.
    """
    if not task_description:
        # Extract from last user message
        for msg in reversed(messages):
            if msg.role == "user" and msg.content:
                task_description = msg.content
                break

    if not task_description:
        return 0.9  # Default to high confidence if no task

    try:
        from sunwell.agent.signals import extract_signals

        signals = await extract_signals(task_description, model)
        return signals.effective_confidence
    except Exception:
        # If signal extraction fails, default to high confidence
        return 0.9


def estimate_output_tokens(task_description: str) -> int:
    """Estimate expected output tokens based on task description.

    Uses simple heuristics to estimate output size. More sophisticated
    estimation could use a classifier or historical data.

    Args:
        task_description: The task to estimate

    Returns:
        Estimated token count for the task output
    """
    # Base estimate: longer descriptions usually mean more complex tasks
    word_count = len(task_description.split())
    base_tokens = word_count * 10  # Rough multiplier

    # Indicators of larger output
    large_indicators = (
        "multiple files",
        "all endpoints",
        "full implementation",
        "complete",
        "crud",
        "scaffold",
        "generate",
    )
    for indicator in large_indicators:
        if indicator in task_description.lower():
            base_tokens *= 2
            break

    # Cap at reasonable range
    return max(500, min(base_tokens, 20_000))
