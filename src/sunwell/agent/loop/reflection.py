"""Self-reflection for the agentic tool loop."""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sunwell.agent.events import AgentEvent, signal_event
from sunwell.models.protocol import Message

if TYPE_CHECKING:
    from sunwell.agent.loop_config import LoopState
    from sunwell.features.mirror.handler import MirrorHandler

logger = logging.getLogger(__name__)


async def run_self_reflection(
    state: LoopState,
    task_description: str,
    mirror_handler: MirrorHandler | None,
    reflection_interval: int = 5,
) -> AsyncIterator[AgentEvent]:
    """Self-reflect on tool usage patterns and adjust strategy (Sunwell differentiator).

    Every N turns, analyze recent tool calls to detect:
    - Repeated failures → suggest different approach
    - Inefficient patterns → suggest better tool sequence
    - Stuck loops → recommend breaking out

    Competitors blindly continue. Sunwell adapts mid-execution.

    Args:
        state: Current loop state
        task_description: Task being executed
        mirror_handler: Mirror handler for pattern analysis
        reflection_interval: How often to reflect (every N turns)

    Yields:
        AgentEvent for reflection results
    """
    if not mirror_handler:
        logger.debug("Self-reflection skipped - no mirror handler configured")
        return

    try:
        # Analyze recent tool calls
        analysis = await mirror_handler.handle(
            "analyze_patterns",
            {
                "context": "tool_calls",
                "scope": "session",
                "include_sequences": True,
            },
        )

        if not analysis or not analysis.get("patterns"):
            return

        patterns = analysis.get("patterns", [])
        suggestions: list[str] = []

        # Check for repeated failures
        failure_count = sum(1 for p in patterns if p.get("type") == "failure")
        if failure_count >= 2:
            suggestions.append("Multiple failures detected. Consider different approach.")

        # Check for repetitive sequences (stuck in loop)
        sequences = analysis.get("sequences", [])
        for seq in sequences:
            if seq.get("count", 0) >= 3:
                tool_pair = seq.get("sequence", [])
                suggestions.append(
                    f"Repetitive pattern detected: {' → '.join(tool_pair)}. "
                    "Breaking may be needed."
                )

        # Emit reflection event if we have suggestions
        if suggestions:
            yield signal_event(
                "self_reflection",
                {
                    "turn": state.turn,
                    "suggestions": suggestions,
                    "patterns_analyzed": len(patterns),
                },
            )

            # Inject reflection into conversation for model awareness
            reflection_msg = (
                f"[Self-Reflection at turn {state.turn}] "
                f"Observed: {'; '.join(suggestions)} "
                "Consider adjusting approach."
            )
            state.messages.append(Message(role="system", content=reflection_msg))

            logger.info(
                "◜ SELF-REFLECTION → Detected patterns, suggesting adjustments",
                extra={
                    "turn": state.turn,
                    "suggestions_count": len(suggestions),
                    "suggestions": suggestions,
                },
            )

    except Exception as e:
        logger.debug("Self-reflection failed (non-fatal): %s", e)
        # Self-reflection is enhancement, not critical path
