"""Identity digest: synthesize behavioral observations into identity prompt.

RFC-023: Converts raw behavioral observations into a coherent identity prompt
that guides how the assistant interacts with the user.

Key features:
- Confidence scoring based on observation consistency
- Length-limited output (max 500 chars)
- Minimum confidence threshold for injection
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.identity.core.models import Identity
    from sunwell.models.protocol import ModelProtocol

from sunwell.identity.core.constants import (
    MAX_IDENTITY_PROMPT_LENGTH,
    MIN_IDENTITY_CONFIDENCE,
)

_DIGEST_PROMPT = """Based on these behavioral observations about a user, synthesize
an identity profile that describes how to interact with them.

Previous identity (if any):
{previous_identity}

Recent observations:
{observations}

Output a brief (3-5 sentence, MAX 500 characters) interaction guide that captures:
1. Preferred tone and style
2. What they value in conversation
3. Any patterns to be aware of

Write in second person ("This user prefers...").
End with CONFIDENCE: [0.0-1.0] based on observation consistency.

If observations are contradictory or too sparse, use lower confidence.
"""


def _extract_confidence(content: str) -> float:
    """Extract confidence score from digest output."""
    match = re.search(r'CONFIDENCE:\s*([\d.]+)', content, re.IGNORECASE)
    if match:
        try:
            return min(1.0, max(0.0, float(match.group(1))))
        except ValueError:
            pass
    return 0.7  # Default moderate confidence


def _extract_prompt(content: str) -> str:
    """Extract prompt text, removing confidence line."""
    # Remove confidence line
    cleaned = re.sub(r'\n?CONFIDENCE:.*$', '', content, flags=re.IGNORECASE | re.MULTILINE)
    return cleaned.strip()


def _extract_tone(content: str) -> str | None:
    """Try to extract tone from digest content."""
    tone_patterns = [
        r"(?:prefer|uses?|likes?)\s+(\w+(?:\s+and\s+\w+)?)\s+(?:tone|style|language)",
        r"(\w+(?:\s+and\s+\w+)?)\s+(?:tone|style|conversation)",
    ]
    for pattern in tone_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


def _extract_values(content: str) -> list[str]:
    """Try to extract values from digest content."""
    values = []
    value_patterns = [
        r"(?:values?|appreciates?)\s+(.+?)(?:\.|,|$)",
        r"(?:when|if)\s+you\s+(.+?)(?:\.|,|$)",
    ]
    for pattern in value_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches[:3]:  # Limit to 3 values
            value = match.strip()
            if 5 < len(value) < 50:  # Reasonable length
                values.append(value)
    return values


async def digest_identity(
    observations: list[str],
    current_identity: Identity | None,
    tiny_model: ModelProtocol,
) -> Identity:
    """Synthesize behavioral observations into validated identity prompt.

    Args:
        observations: List of behavioral observation strings
        current_identity: Current identity (for evolution, not replacement)
        tiny_model: Tiny LLM for synthesis

    Returns:
        Updated Identity with synthesized prompt and confidence
    """
    from sunwell.identity.core.models import Identity
    from sunwell.models.protocol import Message

    if not observations:
        return current_identity or Identity()

    # Build prompt
    previous = current_identity.prompt if current_identity and current_identity.prompt else "None - first synthesis"
    obs_text = "\n".join(f"- {obs}" for obs in observations[-20:])  # Last 20

    prompt = _DIGEST_PROMPT.format(
        previous_identity=previous,
        observations=obs_text,
    )

    try:
        result = await tiny_model.generate((Message(role="user", content=prompt),))
        content = result.content.strip()

        # Parse response
        confidence = _extract_confidence(content)
        prompt_text = _extract_prompt(content)

        # Enforce length limit
        if len(prompt_text) > MAX_IDENTITY_PROMPT_LENGTH:
            # Truncate at word boundary
            prompt_text = prompt_text[:MAX_IDENTITY_PROMPT_LENGTH].rsplit(' ', 1)[0] + "..."

        # Only return if confident enough
        if confidence < MIN_IDENTITY_CONFIDENCE:
            return current_identity or Identity()

        # Extract additional metadata
        tone = _extract_tone(content)
        values = _extract_values(content)

        # Preserve observations from current identity
        current_obs = current_identity.observations if current_identity else []

        return Identity(
            observations=current_obs,
            prompt=prompt_text,
            confidence=confidence,
            tone=tone,
            values=values,
        )

    except Exception:
        # On error, return current identity unchanged
        return current_identity or Identity()


async def quick_digest(
    observations: list[str],
    current_prompt: str | None = None,
) -> tuple[str | None, float]:
    """Quick heuristic digest without LLM.

    Used when tiny model is unavailable or for very quick updates.

    Returns:
        (prompt, confidence) tuple
    """
    if len(observations) < 3:
        return current_prompt, 0.5  # Not enough data

    # Simple heuristic: look for dominant patterns
    casual_count = sum(1 for o in observations if "casual" in o.lower() or "informal" in o.lower())
    formal_count = sum(1 for o in observations if "formal" in o.lower())
    appreciative_count = sum(1 for o in observations if "appreciat" in o.lower() or "thank" in o.lower())
    testing_count = sum(1 for o in observations if "test" in o.lower() or "memory" in o.lower() or "recall" in o.lower())

    parts = []

    # Determine tone
    if casual_count > formal_count and casual_count >= 2:
        parts.append("This user prefers casual, conversational interaction.")
    elif formal_count > casual_count and formal_count >= 2:
        parts.append("This user prefers formal, professional communication.")

    # Add values
    if appreciative_count >= 2:
        parts.append("They appreciate acknowledgment and express gratitude.")
    if testing_count >= 2:
        parts.append("They may test memory recall, so reference past context when relevant.")

    if not parts:
        return current_prompt, 0.5

    # Calculate confidence based on observation count and consistency
    confidence = min(0.85, 0.5 + (len(observations) / 20) * 0.35)

    return " ".join(parts), confidence
