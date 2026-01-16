"""Two-tier extraction: facts and behaviors from user messages.

RFC-023: Extends the existing fact extraction to also capture behavioral signals:
- FACTS: Durable information worth remembering across sessions
- BEHAVIORS: Interaction patterns that shape communication style

Uses a tiny LLM (gemma3:1b) for flexible extraction, falls back to regex.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# Two-tier extraction prompt (canonical from RFC-023)
_TWO_TIER_EXTRACTION_PROMPT = """Extract from this user message into two categories:

FACTS - Durable information worth remembering across sessions:
- Names (user, pets, family, colleagues)
- Preferences (tools, languages, styles)
- Context (job, projects, location)
- Relationships (has a cat, works with X)

BEHAVIORS - Interaction patterns that shape communication style:
- Communication style (formal, casual, terse, verbose)
- Emotional signals (appreciative, frustrated, testing)
- Conversation patterns (asks follow-ups, changes topics)
- Response preferences (likes detail, prefers brevity)

User message: "{message}"

Output format (one per line):
FACT: [fact to remember]
BEHAVIOR: [behavioral observation]

If nothing notable, output: NONE

Important: Only extract clear signals. Skip ambiguous or uncertain observations.
"""

# Behavior-only extraction prompt (lighter weight)
_BEHAVIOR_EXTRACTION_PROMPT = """Identify behavioral patterns in this user message.

Look for:
- Communication style (formal, casual, terse, verbose, uses slang)
- Emotional signals (appreciative, frustrated, curious, testing)
- Conversation patterns (asks follow-ups, provides detail, changes topics)
- Response preferences (likes examples, prefers brevity, values precision)

User message: "{message}"

Output format (one per line):
BEHAVIOR: [behavioral observation]

If no clear behavioral signals, output: NONE
"""

# Regex patterns for behavior detection (fallback)
BEHAVIOR_PATTERNS = {
    "casual_language": [
        r"\blol\b",
        r"\bhaha\b",
        r"\bomg\b",
        r"\bbtw\b",
        r"\bidk\b",
        r"\bimo\b",
        r":\)|:\(|:D|:P|<3",
        r"\bnice\b",
        r"\bcool\b",
        r"\bawesome\b",
        r"\bsweet\b",
    ],
    "formal_language": [
        r"\bplease\b.*\bwould you\b",
        r"\bI would appreciate\b",
        r"\bkindly\b",
        r"\bregards\b",
        r"\bthank you for\b",
    ],
    "appreciation": [
        r"\bthanks?\b",
        r"\bthank you\b",
        r"\bappreciate\b",
        r"\bhelpful\b",
        r"\bgreat\b.*\bhelp\b",
        r"\bperfect\b",
    ],
    "testing_memory": [
        r"\bremember\b.*\?",
        r"\bdo you recall\b",
        r"\bearlier\b.*\bsaid\b",
        r"\blast time\b",
        r"\bwhat did I\b",
        r"\bwhat was\b.*\bname\b",
    ],
    "frustration": [
        r"\bugh\b",
        r"\bfrustra",
        r"\bnot working\b",
        r"\bstill\b.*\bnot\b",
        r"\bdoesn't work\b",
        r"\bwhy\b.*\bnot\b",
    ],
    "prefers_brevity": [
        r"^.{1,20}$",  # Very short messages
        r"^(?:ok|yes|no|sure|k|yep|nope|got it)\b",
    ],
    "detailed_communicator": [
        r".{200,}",  # Long messages
        r"(?:first|second|third|then|finally)",
        r"(?:for example|specifically|in particular)",
    ],
}


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
    model: "ModelProtocol",
) -> list[tuple[str, float]]:
    """Extract behavioral patterns from user message using a tiny LLM.
    
    Args:
        message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)
    
    Returns:
        List of (behavior_text, confidence) tuples.
    """
    from sunwell.models.protocol import Message
    
    prompt = _BEHAVIOR_EXTRACTION_PROMPT.format(message=message)
    
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


async def extract_with_categories(
    message: str,
    model: "ModelProtocol",
) -> tuple[list[tuple[str, str, float]], list[tuple[str, float]]]:
    """Extract facts and behaviors from user message.
    
    Uses the two-tier extraction prompt to categorize extractions.
    
    Args:
        message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)
    
    Returns:
        (facts, behaviors) where:
        - facts: list of (fact_text, category, confidence)
        - behaviors: list of (behavior_text, confidence)
    """
    from sunwell.models.protocol import Message
    
    prompt = _TWO_TIER_EXTRACTION_PROMPT.format(message=message)
    
    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()
        
        facts, behaviors = [], []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line[5:].strip()
                if fact_text and fact_text.upper() != "NONE" and len(fact_text) > 3:
                    facts.append((fact_text, "fact", 0.85))
            elif line.startswith("BEHAVIOR:"):
                behavior_text = line[9:].strip()
                if behavior_text and behavior_text.upper() != "NONE" and len(behavior_text) > 3:
                    behaviors.append((behavior_text, 0.8))
            elif line.upper() == "NONE":
                break
        
        return facts, behaviors
    except Exception:
        # Fall back to regex for both
        from sunwell.simulacrum.extractor import extract_user_facts
        facts = extract_user_facts(message)
        behaviors = extract_behaviors_regex(message)
        return facts, behaviors
