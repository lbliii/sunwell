"""Intent classification for chat-agent routing (RFC-135).

Classifies user input as conversation vs task to route appropriately:
- CONVERSATION: Questions, discussions → respond directly
- TASK: Action requests → trigger agent planning + execution
- COMMAND: /slash commands or :: shortcuts → handle specially
- INTERRUPT: Input during execution → pause and handle
- UNKNOWN: Unclear input that couldn't be classified confidently

Uses heuristics first for speed, falls back to LLM for ambiguous cases.

This module provides:
- IntentRouter: Core classification engine
- classify_input(): Convenience function for shared use across CLI entry points
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)


class Intent(Enum):
    """User input intent categories."""

    CONVERSATION = "conversation"
    """Question, discussion, or clarification request."""

    TASK = "task"
    """Action request requiring agent execution."""

    INTERRUPT = "interrupt"
    """Input during active execution."""

    COMMAND = "command"
    """Explicit /slash command or :: shortcuts."""

    UNKNOWN = "unknown"
    """Unclear input that couldn't be classified confidently."""


@dataclass(frozen=True, slots=True)
class IntentClassification:
    """Result of intent classification.

    Contains the classified intent, confidence score, and optional
    extracted information for routing decisions.
    """

    intent: Intent
    """The classified intent."""

    confidence: float
    """Confidence in classification (0.0-1.0)."""

    task_description: str | None = None
    """Extracted goal if TASK intent."""

    reasoning: str | None = None
    """Why this classification was made."""


# High-signal task indicators (imperative verbs)
_TASK_VERBS: frozenset[str] = frozenset({
    "add", "create", "build", "implement", "make", "write",
    "fix", "refactor", "update", "modify", "change", "delete",
    "remove", "migrate", "convert", "generate", "setup", "configure",
    "install", "deploy", "test", "debug", "optimize", "improve",
})

# High-signal conversation indicators
_QUESTION_STARTERS: frozenset[str] = frozenset({
    "what", "why", "how", "when", "where", "who", "which",
    "can you explain", "tell me about", "describe", "explain",
    "is there", "are there", "do you", "does this", "could you",
})


class IntentRouter:
    """Classify user input intent for chat-agent routing.

    Uses fast heuristics for clear cases, optional LLM for ambiguous ones.
    Designed to minimize latency while maintaining accuracy.

    Example:
        >>> router = IntentRouter(threshold=0.7)
        >>> result = await router.classify("Add user authentication")
        >>> assert result.intent == Intent.TASK
        >>> assert result.confidence >= 0.7
    """

    def __init__(
        self,
        model: ModelProtocol | None = None,
        threshold: float = 0.7,
    ) -> None:
        """Initialize the intent router.

        Args:
            model: Optional LLM for ambiguous cases (falls back to heuristics if None)
            threshold: Confidence threshold for classification (default 0.7)
        """
        self.model = model
        self.threshold = threshold

    async def classify(
        self,
        user_input: str,
        context: str | None = None,
        is_executing: bool = False,
    ) -> IntentClassification:
        """Classify user input intent.

        Uses heuristics first for speed, falls back to LLM only when:
        - Score difference between TASK and CONVERSATION is < 0.3
        - Model is available

        Args:
            user_input: Raw user input text
            context: Optional conversation context for disambiguation
            is_executing: Whether agent is currently executing (enables INTERRUPT)

        Returns:
            IntentClassification with intent, confidence, and reasoning
        """
        logger.debug("classify() called: input=%r, is_executing=%s", user_input[:50], is_executing)

        # Check for explicit commands first
        stripped = user_input.strip()
        if stripped.startswith("/") or stripped.startswith("::"):
            logger.debug("Detected command prefix")
            return IntentClassification(
                intent=Intent.COMMAND,
                confidence=1.0,
                reasoning="Explicit command prefix",
            )

        # Check for interrupt during execution
        if is_executing:
            logger.debug("Input during execution -> INTERRUPT")
            return IntentClassification(
                intent=Intent.INTERRUPT,
                confidence=1.0,
                reasoning="Input during active execution",
            )

        # Heuristic classification
        try:
            result = await self._classify_heuristic(user_input, context)
            logger.debug(
                "Classification complete: %s (confidence=%.2f, reason=%s)",
                result.intent.value,
                result.confidence,
                result.reasoning,
            )
            return result
        except Exception as e:
            logger.exception("Classification failed with exception")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                reasoning=f"Classification error: {e}",
            )

    async def _classify_heuristic(
        self,
        user_input: str,
        context: str | None = None,
    ) -> IntentClassification:
        """Classify using heuristics, with LLM escalation for unclear cases."""
        lower = user_input.lower().strip()
        words = lower.split()

        if not words:
            logger.debug("Empty input after stripping")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                reasoning="Empty input",
            )

        # Gibberish detection: if no recognizable words, escalate to LLM
        has_recognizable = any(
            len(w) <= 2 or  # Short words like "a", "is", "to"
            w in _TASK_VERBS or
            w in _QUESTION_STARTERS or
            w in {"the", "this", "that", "it", "i", "you", "we", "they", "my", "your",
                  "a", "an", "is", "are", "was", "were", "be", "have", "has", "do", "does",
                  "hello", "hi", "hey", "thanks", "thank", "please", "yes", "no", "ok", "okay"}
            for w in words
        )

        if not has_recognizable and len(words) == 1 and len(words[0]) > 10:
            logger.debug("Detected possible gibberish, escalating to LLM: %r", user_input[:30])
            if self.model:
                return await self._classify_with_llm(user_input, context)
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.1,
                reasoning="Unrecognizable input (no LLM available)",
            )

        # Score task indicators
        first_word = words[0]
        task_score = 0.0

        # Strong signal: starts with task verb
        if first_word in _TASK_VERBS:
            task_score += 0.5
        # Medium signal: task verb in words 2-3 (not first word to avoid double-counting)
        elif any(w in _TASK_VERBS for w in words[1:3]):
            task_score += 0.3

        # Weak signal: not a question
        is_question = lower.endswith("?")
        if not is_question:
            task_score += 0.1

        # Boost if has reasonable length after task verb
        if len(words) > 3 and first_word in _TASK_VERBS:
            task_score += 0.2

        # Score conversation indicators
        conv_score = 0.0

        # Strong signal: ends with question mark
        if is_question:
            conv_score += 0.4

        # Strong signal: starts with question word/phrase
        if any(lower.startswith(q) for q in _QUESTION_STARTERS):
            conv_score += 0.4

        # Medium signal: conversational patterns
        if any(phrase in lower for phrase in ("i think", "i'm wondering", "curious about")):
            conv_score += 0.2

        # Weak signal: greeting patterns
        if first_word in {"hello", "hi", "hey", "greetings"}:
            conv_score += 0.3

        logger.debug("Heuristic scores: task=%.2f, conv=%.2f, threshold=%.2f", task_score, conv_score, self.threshold)

        # Determine intent from scores
        if task_score >= self.threshold:
            return IntentClassification(
                intent=Intent.TASK,
                confidence=min(task_score, 1.0),
                task_description=user_input,
                reasoning="Imperative verb detected",
            )

        if conv_score >= self.threshold:
            return IntentClassification(
                intent=Intent.CONVERSATION,
                confidence=min(conv_score, 1.0),
                reasoning="Question pattern detected",
            )

        # Neither score above threshold - escalate to LLM
        max_score = max(task_score, conv_score)
        if self.model:
            logger.debug("Scores below threshold (max=%.2f), escalating to LLM", max_score)
            return await self._classify_with_llm(user_input, context)

        # No LLM available - return UNKNOWN if very low, otherwise best guess
        if max_score < 0.3:
            logger.debug("No LLM, scores very low, marking as UNKNOWN")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=max_score,
                reasoning=f"Low confidence, no LLM (task={task_score:.2f}, conv={conv_score:.2f})",
            )

        # Default to higher score with caveat
        logger.debug("No LLM, using best guess from heuristics")
        if task_score > conv_score:
            return IntentClassification(
                intent=Intent.TASK,
                confidence=task_score,
                task_description=user_input,
                reasoning="Heuristic best guess: task score higher",
            )

        return IntentClassification(
            intent=Intent.CONVERSATION,
            confidence=max(conv_score, 0.5),
            reasoning="Heuristic best guess: conversation score higher",
        )

    async def _classify_with_llm(
        self,
        user_input: str,
        context: str | None,
    ) -> IntentClassification:
        """Use LLM for ambiguous classification."""
        from sunwell.models.core.protocol import Message

        if not self.model:
            logger.debug("No LLM available for ambiguous classification")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.3,
                reasoning="No LLM available for disambiguation",
            )

        prompt = f"""Classify this user input as either TASK or CONVERSATION.

TASK: User wants something done (create, modify, fix, implement code/files)
CONVERSATION: User wants information, explanation, or discussion

{f"Recent conversation context:{chr(10)}{context}{chr(10)}" if context else ""}
User input: "{user_input}"

Respond with only: TASK or CONVERSATION"""

        try:
            logger.debug("Calling LLM for intent classification")
            result = await self.model.generate(
                (Message(role="user", content=prompt),),
            )

            text = (result.text or "").strip().upper()
            logger.debug("LLM classification response: %r", text[:50])

            if "TASK" in text:
                return IntentClassification(
                    intent=Intent.TASK,
                    confidence=0.8,
                    task_description=user_input,
                    reasoning="LLM classification: TASK",
                )
            elif "CONVERSATION" in text:
                return IntentClassification(
                    intent=Intent.CONVERSATION,
                    confidence=0.8,
                    reasoning="LLM classification: CONVERSATION",
                )
            else:
                logger.warning("LLM returned unexpected classification: %r", text[:50])
                return IntentClassification(
                    intent=Intent.UNKNOWN,
                    confidence=0.4,
                    reasoning=f"LLM returned unclear response: {text[:30]}",
                )
        except Exception as e:
            logger.exception("LLM classification failed")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.2,
                reasoning=f"LLM classification error: {e}",
            )


# =============================================================================
# Convenience Functions for Shared Use
# =============================================================================


async def classify_input(
    user_input: str,
    model: ModelProtocol | None = None,
    context: str | None = None,
    threshold: float = 0.7,
) -> IntentClassification:
    """Classify user input for routing decisions.

    Shared convenience function used by both goal command and chat loop
    to ensure consistent intent classification across all entry points.

    Args:
        user_input: Raw user input text
        model: Optional LLM for ambiguous cases
        context: Optional conversation context for disambiguation
        threshold: Confidence threshold for classification

    Returns:
        IntentClassification with intent, confidence, and reasoning

    Example:
        >>> result = await classify_input("where is flask used?", model)
        >>> if result.intent == Intent.CONVERSATION:
        ...     print("This is a question")
    """
    router = IntentRouter(model=model, threshold=threshold)
    return await router.classify(user_input, context=context)
