"""Retry and escalation strategies for the agentic tool loop (RFC-134).

Provides:
- Interference fix: 3 perspectives to fix a failed tool call
- Vortex fix: Multiple candidates to fix a failed tool call
- Dead-end recording: Track approaches that consistently fail
"""

import json
import logging
import re
from typing import TYPE_CHECKING

from sunwell.agent.loop_routing import interference_generate, vortex_generate
from sunwell.models.protocol import GenerateOptions, Message, ToolCall

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore
    from sunwell.models.protocol import ModelProtocol

logger = logging.getLogger(__name__)


async def interference_fix(
    model: ModelProtocol,
    tc: ToolCall,
    error: str,
    tool_choice: str = "auto",
) -> ToolCall | None:
    """Use interference (3 perspectives) to fix a failed tool call.

    Returns a repaired ToolCall or None if fix failed.
    """
    fix_prompt = f"""A tool call failed. Analyze from 3 perspectives and fix it.

Tool: {tc.name}
Arguments: {tc.arguments}
Error: {error}

Provide the corrected arguments as a JSON object."""

    # Use interference generate to get multiple perspectives
    messages = [Message(role="user", content=fix_prompt)]
    options = GenerateOptions(temperature=0.5, max_tokens=500)

    try:
        result = await interference_generate(
            model=model,
            messages=messages,
            tools=(),  # No tools, just get JSON response
            tool_choice=tool_choice,
            options=options,
        )

        if result.text:
            # Try to parse JSON from response
            fixed_args = _extract_json_args(result.text)
            if fixed_args is not None:
                return ToolCall(id=tc.id, name=tc.name, arguments=fixed_args)
    except Exception as e:
        logger.warning("Interference fix failed: %s", e)

    return None


async def vortex_fix(
    model: ModelProtocol,
    tc: ToolCall,
    error: str,
    tool_choice: str = "auto",
) -> ToolCall | None:
    """Use vortex (multiple candidates) to fix a failed tool call.

    Returns a repaired ToolCall or None if fix failed.
    """
    fix_prompt = f"""A tool call failed. Generate the best fix.

Tool: {tc.name}
Arguments: {tc.arguments}
Error: {error}

Provide the corrected arguments as a JSON object."""

    messages = [Message(role="user", content=fix_prompt)]
    options = GenerateOptions(temperature=0.3, max_tokens=500)

    try:
        result = await vortex_generate(
            model=model,
            messages=messages,
            tools=(),
            tool_choice=tool_choice,
            options=options,
        )

        if result.text:
            fixed_args = _extract_json_args(result.text)
            if fixed_args is not None:
                return ToolCall(id=tc.id, name=tc.name, arguments=fixed_args)
    except Exception as e:
        logger.warning("Vortex fix failed: %s", e)

    return None


def _extract_json_args(text: str) -> dict | None:
    """Extract JSON arguments from text response.

    Handles text wrapped in markdown code blocks.
    """
    text = text.strip()
    if "```" in text:
        # Extract from code block
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse fix response as JSON")
        return None


async def record_tool_dead_end(
    learning_store: LearningStore | None,
    tc: ToolCall,
    error: str,
    max_retries: int,
) -> None:
    """Record a tool call failure as a dead-end for future avoidance.

    RFC-134: Dead-ends are stored in LearningStore and can be used
    to avoid similar failures in future sessions.
    """
    if not learning_store:
        return

    from sunwell.agent.learning import DeadEnd

    dead_end = DeadEnd(
        approach=f"Tool {tc.name} with args: {tc.arguments}",
        reason=error,
        context=f"Failed after {max_retries} retries",
    )
    learning_store.add_dead_end(dead_end)
    logger.info("Recorded dead-end: %s", dead_end.approach[:100])
