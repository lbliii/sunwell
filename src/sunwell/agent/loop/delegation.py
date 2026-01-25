"""Model delegation for the agentic tool loop (RFC-137)."""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import (
    AgentEvent,
    delegation_started_event,
    ephemeral_lens_created_event,
)

if TYPE_CHECKING:
    from sunwell.agent.loop_config import LoopConfig
    from sunwell.foundation.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol, Tool
    from sunwell.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


async def run_with_delegation(
    loop_instance: Any,  # AgentLoop instance
    task_description: str,
    tools: tuple[Tool, ...],
    system_prompt: str | None,
    context: str | None,
) -> AsyncIterator[AgentEvent]:
    """Execute task with smart-to-dumb delegation (RFC-137).

    Uses a smart model to create an EphemeralLens, then executes
    with a cheaper model using that lens for guidance.

    Args:
        loop_instance: AgentLoop instance (needed to modify model/lens)
        task_description: What to accomplish
        tools: Available tools
        system_prompt: Optional system prompt
        context: Additional context

    Yields:
        AgentEvent for progress tracking
    """
    from sunwell.agent.ephemeral_lens import create_ephemeral_lens
    from sunwell.agent.loop_routing import estimate_output_tokens

    # Must have both smart and delegation models
    smart_model = loop_instance.smart_model
    if smart_model is None:
        smart_model = loop_instance.model  # Use primary as smart model
    delegation_model = loop_instance.delegation_model
    if delegation_model is None:
        logger.warning("Delegation requested but no delegation_model set")
        # Fall through to normal execution
        async for event in loop_instance.run(
            task_description, tools, system_prompt, context
        ):
            yield event
        return

    smart_model_id = getattr(smart_model, "model_id", "unknown")
    delegation_model_id = getattr(delegation_model, "model_id", "unknown")

    # Emit delegation started event
    estimated_tokens = estimate_output_tokens(task_description)
    yield delegation_started_event(
        task_description=task_description,
        smart_model=smart_model_id,
        delegation_model=delegation_model_id,
        reason="Task exceeds delegation threshold",
        estimated_tokens=estimated_tokens,
    )

    logger.info(
        "◈ DELEGATION → Creating lens with %s for execution by %s",
        smart_model_id,
        delegation_model_id,
    )

    # Create ephemeral lens using smart model
    context_summary = context[:2000] if context else ""
    ephemeral_lens = await create_ephemeral_lens(
        model=smart_model,
        task=task_description,
        context=context_summary,
    )

    # Emit lens created event
    yield ephemeral_lens_created_event(
        task_scope=ephemeral_lens.task_scope,
        heuristics_count=len(ephemeral_lens.heuristics),
        patterns_count=len(ephemeral_lens.patterns),
        anti_patterns_count=len(ephemeral_lens.anti_patterns),
        constraints_count=len(ephemeral_lens.constraints),
        generated_by=ephemeral_lens.generated_by,
    )

    logger.info(
        "◐ LENS CREATED → %s: %d heuristics, %d patterns",
        ephemeral_lens.task_scope[:50],
        len(ephemeral_lens.heuristics),
        len(ephemeral_lens.patterns),
    )

    # Inject lens context into system prompt
    lens_context = ephemeral_lens.to_context()
    enhanced_system = system_prompt or ""
    if lens_context:
        if enhanced_system:
            enhanced_system = f"{lens_context}\n\n{enhanced_system}"
        else:
            enhanced_system = lens_context

    try:
        # Set flag to prevent recursion
        loop_instance._in_delegation = True

        # Run the loop with delegation model
        async for event in loop_instance.run(
            task_description=task_description,
            tools=tools,
            system_prompt=enhanced_system,
            context=context,
        ):
            yield event

    finally:
        # Restore original model and lens
        loop_instance.model = original_model
        loop_instance.lens = original_lens
        loop_instance._in_delegation = False
