"""Recovery state management for the agentic tool loop."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.loop_config import LoopState
    from sunwell.models.protocol import ToolCall
    from sunwell.recovery.manager import RecoveryManager

logger = logging.getLogger(__name__)


async def save_recovery_state(
    failed_tool: ToolCall,
    error: str,
    state: LoopState,
    recovery_manager: RecoveryManager | None,
) -> None:
    """Save recovery state for later resume (Sunwell differentiator).

    When tool execution fails, we save the current state so the user can:
    - Review what happened with `sunwell review`
    - Resume from where they left off
    - Manually fix and continue

    Competitors lose all progress on failure - Sunwell preserves it.

    Args:
        failed_tool: The tool call that failed
        error: Error message
        state: Current loop state
        recovery_manager: Recovery manager to save state
    """
    if not recovery_manager:
        logger.debug("Recovery skipped - no recovery manager configured")
        return

    try:
        from sunwell.recovery.types import RecoveryState

        # Build context from messages
        conversation_context = []
        for msg in state.messages[-10:]:  # Last 10 messages
            role = msg.role
            content = msg.content[:500] if msg.content else ""
            conversation_context.append(f"[{role}] {content}")

        # Extract goal from first user message
        goal = ""
        for msg in state.messages:
            if msg.role == "user" and msg.content:
                goal = msg.content[:200]
                break

        # Create recovery state
        recovery_state = RecoveryState(
            goal=goal,
            artifacts=state.file_writes,
            failed_gate="tool_execution",
            error_details=[
                f"Tool: {failed_tool.name}",
                f"Arguments: {failed_tool.arguments}",
                f"Error: {error}",
            ],
            context={
                "turn": state.turn,
                "tool_calls_total": state.tool_calls_total,
                "conversation": conversation_context,
            },
        )

        # Save via recovery manager
        await recovery_manager.save(recovery_state)

        logger.info(
            "◇ RECOVERY → State saved [sunwell review to resume]",
            extra={
                "tool": failed_tool.name,
                "turn": state.turn,
                "files_written": len(state.file_writes),
            },
        )

    except Exception as e:
        logger.warning("Failed to save recovery state: %s", e)
        # Don't fail the operation if recovery save fails
