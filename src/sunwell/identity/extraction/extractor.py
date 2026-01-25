"""Two-tier extraction: facts and behaviors from user messages.

RFC-023: Extends the existing fact extraction to also capture behavioral signals:
- FACTS: Durable information worth remembering across sessions
- BEHAVIORS: Interaction patterns that shape communication style

Uses a tiny LLM (gemma3:1b) for flexible extraction, falls back to regex.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.identity.extraction.patterns import (
    BEHAVIOR_EXTRACTION_PROMPT,
    BEHAVIOR_PATTERNS,
    TWO_TIER_EXTRACTION_PROMPT,
)


def _is_low_quality(text: str) -> bool:
    """Quick sanity check for obviously bad extractions.

    Not heavy regex - just basic quality gates. Trust the LLM prompt.
    """
    text_clean = text.strip().lower()

    # Too short to be useful
    if len(text_clean) < 8:
        return True

    # Looks like a category label, not a fact (starts with generic category word)
    category_starters = ("names", "preferences", "context", "relationships",
                         "communication", "emotional", "behaviors", "facts")
    if text_clean.split()[0].rstrip("s:,") in category_starters and "(" in text_clean:
        return True

    # Just says "none" or similar
    return text_clean in ("none", "nothing", "n/a", "no facts", "no behaviors")


def extract_behaviors_regex(message: str) -> list[tuple[str, float]]:
    """Extract behaviors using regex patterns (fallback).

    Returns:
        List of (behavior_text, confidence) tuples.
    """
    behaviors = []
    message_lower = message.lower()

    for behavior_type, patterns in BEHAVIOR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                # Map pattern type to readable behavior
                behavior_map = {
                    "casual_language": "Uses casual language",
                    "formal_language": "Uses formal language",
                    "appreciation": "Expresses appreciation",
                    "testing_memory": "Tests memory recall",
                    "frustration": "Shows frustration",
                    "prefers_brevity": "Prefers brief responses",
                    "detailed_communicator": "Communicates with detail",
                }
                behavior_text = behavior_map.get(behavior_type, behavior_type)

                # Avoid duplicates
                if not any(b[0] == behavior_text for b in behaviors):
                    behaviors.append((behavior_text, 0.7))
                break

    return behaviors


async def extract_behaviors(
    message: str,
    model: ModelProtocol,
) -> list[tuple[str, float]]:
    """Extract behavioral patterns from user message using a tiny LLM.

    Args:
        message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)

    Returns:
        List of (behavior_text, confidence) tuples.
    """
    from sunwell.models.protocol import Message

    prompt = BEHAVIOR_EXTRACTION_PROMPT.format(message=message)

    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()

        behaviors = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("BEHAVIOR:"):
                behavior_text = line[9:].strip()
                if behavior_text and len(behavior_text) > 3 and behavior_text.upper() != "NONE":
                    behaviors.append((behavior_text, 0.8))
            elif line.upper() == "NONE":
                break

        return behaviors
    except Exception:
        # Fall back to regex on error
        return extract_behaviors_regex(message)


def _categorize_fact(fact_text: str) -> str:
    """Infer category from fact content."""
    text_lower = fact_text.lower()

    # Name patterns
    if any(kw in text_lower for kw in ["named", "name is", "called", "nickname"]):
        return "names"
    if any(kw in text_lower for kw in ["pet", "cat", "dog", "family", "wife", "husband", "child"]):
        return "relationships"

    # Work/context patterns
    if any(kw in text_lower for kw in ["works at", "job", "project", "building", "working on"]):
        return "context"

    # Preference patterns
    if any(kw in text_lower for kw in ["prefer", "like", "favorite", "use "]):
        return "preferences"

    return "fact"  # Generic fallback


async def extract_with_categories(
    message: str,
    model: ModelProtocol,
) -> tuple[list[tuple[str, str, float]], list[tuple[str, float]]]:
    """Extract facts, interests, and behaviors from user message.

    Uses three-tier extraction:
    - FACT: Explicit statements about the user
    - INTEREST: Inferred interests from questions/topics
    - BEHAVIOR: Communication patterns

    Args:
        message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)

    Returns:
        (facts, behaviors) where:
        - facts: list of (fact_text, category, confidence) - includes interests
        - behaviors: list of (behavior_text, confidence)
    """
    from sunwell.models.protocol import Message

    prompt = TWO_TIER_EXTRACTION_PROMPT.format(message=message)

    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()

        facts, behaviors = [], []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line[5:].strip()
                # Filter out echoes and invalid responses
                if (fact_text
                    and fact_text.upper() != "NONE"
                    and not _is_low_quality(fact_text)):
                    # Infer actual category from content
                    category = _categorize_fact(fact_text)
                    facts.append((fact_text, category, 0.85))
            elif line.startswith("INTEREST:"):
                # Interests stored as facts with category="interest"
                interest_text = line[9:].strip()
                if (interest_text
                    and interest_text.upper() != "NONE"
                    and not _is_low_quality(interest_text)):
                    # Lower confidence for inferred interests
                    facts.append((interest_text, "interest", 0.7))
            elif line.startswith("BEHAVIOR:"):
                behavior_text = line[9:].strip()
                # Filter out echoes and invalid responses
                if (behavior_text
                    and behavior_text.upper() != "NONE"
                    and not _is_low_quality(behavior_text)):
                    behaviors.append((behavior_text, 0.8))
            elif line.upper() == "NONE":
                break

        return facts, behaviors
    except Exception:
        # Fall back to regex for both
        from sunwell.memory.simulacrum.extractors.extractor import extract_user_facts
        facts = extract_user_facts(message)
        behaviors = extract_behaviors_regex(message)
        return facts, behaviors
