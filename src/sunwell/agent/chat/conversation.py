"""Conversation generation for the unified chat loop.

Handles response generation and message building for conversational mode.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)


def build_system_prompt(workspace: Path) -> str:
    """Build system prompt for conversation mode.

    Args:
        workspace: Current workspace path

    Returns:
        System prompt string
    """
    now = datetime.now(timezone.utc).astimezone()
    current_time = now.strftime("%A, %B %d, %Y at %H:%M %Z")

    return f"""You are Sunwell, an AI assistant for software development.

You can both:
1. Answer questions and have conversations
2. Execute coding tasks (create files, modify code, etc.)

When the user asks you to DO something (create, add, fix, refactor),
you'll transition to execution mode with a plan.

When the user asks questions, explain or discuss freely.

Current date/time: {current_time}
Current workspace: {workspace}

Note: Your training data has a knowledge cutoff. For questions about current
events, recent releases, or time-sensitive information, acknowledge you may
not have the latest data and suggest the user verify from authoritative sources."""


def build_messages(
    user_input: str,
    conversation_history: list[dict[str, str]],
    system_prompt: str,
) -> list[dict[str, str]]:
    """Build message list with conversation history.

    Args:
        user_input: Current user message
        conversation_history: Previous conversation messages
        system_prompt: System prompt to use

    Returns:
        List of messages for the model
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    # Add recent conversation history (last 20 messages = 10 turns)
    messages.extend(conversation_history[-20:])

    # Add current input if not already there
    if not messages or messages[-1].get("content") != user_input:
        messages.append({"role": "user", "content": user_input})

    return messages


def get_conversation_context(conversation_history: list[dict[str, str]]) -> str:
    """Get recent conversation as context string for intent classification.

    Args:
        conversation_history: Conversation message history

    Returns:
        Formatted context string
    """
    recent = conversation_history[-6:]
    return "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)


async def generate_response(
    model: ModelProtocol,
    user_input: str,
    conversation_history: list[dict[str, str]],
    workspace: Path,
    execution_context: dict[str, Any] | None = None,
) -> str:
    """Generate conversational response.

    Args:
        model: LLM model for generation
        user_input: User's message
        conversation_history: Conversation history
        workspace: Current workspace path
        execution_context: Optional context during execution

    Returns:
        Generated response string
    """
    from sunwell.models import Message

    system_prompt = build_system_prompt(workspace)
    messages = build_messages(user_input, conversation_history, system_prompt)

    if execution_context:
        # Add execution context for mid-execution questions
        messages.insert(-1, {
            "role": "system",
            "content": f"Current execution context: {execution_context}",
        })

    # Convert to message tuples for model
    structured = tuple(
        Message(role=m["role"], content=m["content"]) for m in messages
    )

    logger.debug(
        "Calling model.generate with %d messages (model=%s)",
        len(structured),
        type(model).__name__,
    )

    # Check if model supports streaming
    if hasattr(model, "generate_stream"):
        logger.debug("Using streaming generation")
        response_parts: list[str] = []
        async for chunk in model.generate_stream(structured):
            response_parts.append(chunk)
        response = "".join(response_parts)
        logger.debug("Streaming complete: %d chars", len(response))
        return response

    # Fallback to non-streaming
    logger.debug("Using non-streaming generation")
    result = await model.generate(structured)
    response = result.text or ""
    logger.debug("Generation complete: %d chars", len(response))
    return response
