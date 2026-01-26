"""Automatic learning extraction from conversations AND thinking tokens.

Watches conversation for extractable insights:
- Facts discovered ("The API timeout is 5 seconds")
- Constraints identified ("Must use Redis for caching")
- Patterns recognized ("This always happens when X")
- Dead ends hit ("Tried X, didn't work because Y")

THINKING TOKENS are especially valuable because they contain:
- Raw reasoning (unfiltered thought process)
- Rejected alternatives (potential dead ends)
- Assumptions made (implicit constraints)
- Uncertainties (confidence signals)

Supports:
- Claude extended thinking (thinking blocks)
- OpenAI reasoning tokens
- Any chain-of-thought output
"""


import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.turn import Turn
    from sunwell.models import ModelProtocol


# =============================================================================
# Pre-compiled patterns for learning extraction
# Compiled once at module load, avoiding per-call regex compilation overhead.
# =============================================================================

from re import Pattern

# Patterns that indicate a learning (from final responses)
_LEARNING_PATTERNS: dict[str, tuple[Pattern[str], ...]] = {
    "fact": (
        re.compile(r"(?:the |it )(?:is|has|takes|uses|requires) (\d+[^\.,]*)", re.IGNORECASE),
        re.compile(r"(?:must|should|need to) (?:be |use |have )([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:always|never) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:default|defaults to) ([^\.]+)", re.IGNORECASE),
        re.compile(r"timeout (?:is|of) (\d+[^\.,]*)", re.IGNORECASE),
        re.compile(r"limit (?:is|of) (\d+[^\.,]*)", re.IGNORECASE),
    ),
}


# Patterns for user-stated facts (personal info, preferences, context)
_USER_FACT_PATTERNS: dict[str, tuple[Pattern[str], ...]] = {
    "fact": (
        re.compile(r"(?:my name is|i'm called|call me) ([a-zA-Z][a-zA-Z0-9_\- ]{1,30})", re.IGNORECASE),
        re.compile(r"(?:i am|i'm) (?:a |an )?([a-zA-Z][a-zA-Z0-9_\- ]{2,40})", re.IGNORECASE),
        re.compile(r"(?:i work (?:at|for|on)) ([^\.]{3,50})", re.IGNORECASE),
        re.compile(r"(?:i(?:'m| am) (?:using|working with|building)) ([^\.]{3,50})", re.IGNORECASE),
        re.compile(r"(?:my (?:project|app|team|company) is) ([^\.]{3,50})", re.IGNORECASE),
        re.compile(r"(?:i prefer|i like|i use) ([^\.]{3,50})", re.IGNORECASE),
    ),
    "constraint": (
        re.compile(r"(?:cannot|can't|won't|doesn't) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:blocked by|prevented by|limited by) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:requires?|needs?) ([^\.]+?) (?:to|before|first)", re.IGNORECASE),
        re.compile(r"(?:only works|only valid) (?:with|when|if) ([^\.]+)", re.IGNORECASE),
    ),
    "dead_end": (
        re.compile(r"(?:tried|attempted) ([^\.]+?) (?:but|however|didn't|failed)", re.IGNORECASE),
        re.compile(r"(?:doesn't|won't|can't) work (?:because|due to|since) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:this approach|that method|this solution) (?:won't|doesn't|failed)", re.IGNORECASE),
        re.compile(r"dead.?end|doesn't help|no luck|didn't work", re.IGNORECASE),
    ),
    "pattern": (
        re.compile(r"(?:whenever|every time|each time) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:pattern|trend|consistently) ([^\.]+)", re.IGNORECASE),
        re.compile(r"(?:seems to|appears to|tends to) ([^\.]+)", re.IGNORECASE),
    ),
}


# THINKING TOKEN patterns - more informal, reasoning-style language
_THINKING_PATTERNS: dict[str, tuple[Pattern[str], ...]] = {
    "fact": (
        re.compile(r"(?:I notice|I see|looking at|checking) .{0,20}(\d+[^\.,\n]*)", re.IGNORECASE),
        re.compile(r"(?:it looks like|apparently|it seems) ([^,\n]+)", re.IGNORECASE),
        re.compile(r"(?:the .{0,30}) (?:is|are|has|have) (\d+[^\n,]*)", re.IGNORECASE),
        re.compile(r"(?:found|discovered|noticed) (?:that )?([^,\n]+)", re.IGNORECASE),
    ),
    "dead_end": (
        re.compile(r"(?:but |however |although )(?:that |this )(?:won't|wouldn't|can't|couldn't) ([^\n,]+)", re.IGNORECASE),
        re.compile(r"(?:I considered|I thought about|maybe) .{0,30}(?:but|however) ([^\n]+)", re.IGNORECASE),
        re.compile(r"(?:this won't work|that's not going to work|can't do that) (?:because|since|as) ([^\n]+)", re.IGNORECASE),
        re.compile(r"(?:ruled out|rejected|dismissed|discarded) ([^\n,]+)", re.IGNORECASE),
        re.compile(r"(?:too |overly )(?:slow|expensive|complex|risky)([^\n,]*)", re.IGNORECASE),
        re.compile(r"(?:not viable|not feasible|not practical|won't scale)([^\n,]*)", re.IGNORECASE),
    ),
    "constraint": (
        re.compile(r"(?:assuming|given that|since|because) ([^\n,]+?) (?:we|I|this)", re.IGNORECASE),
        re.compile(r"(?:we need to|I need to|must) (?:ensure|make sure|guarantee) ([^\n,]+)", re.IGNORECASE),
        re.compile(r"(?:the constraint|limitation|restriction) (?:is|here is) ([^\n,]+)", re.IGNORECASE),
        re.compile(r"(?:can only|must only|should only) ([^\n,]+)", re.IGNORECASE),
    ),
    "uncertainty": (
        re.compile(r"(?:I'm not sure|not certain|unclear|might be wrong) ([^\n,]+)", re.IGNORECASE),
        re.compile(r"(?:probably|likely|possibly|maybe) ([^\n,]+?) (?:but|though|however)", re.IGNORECASE),
        re.compile(r"(?:need to verify|should check|worth confirming) ([^\n,]+)", re.IGNORECASE),
    ),
}



@dataclass(frozen=True, slots=True)
class ExtractedLearning:
    """A learning extracted from conversation."""

    text: str
    """The extracted learning text."""

    category: Literal["fact", "constraint", "dead_end", "pattern"]
    """Type of learning."""

    confidence: float
    """Confidence in extraction (0-1)."""

    source_text: str
    """Original text this was extracted from."""

    pattern_matched: str
    """Which pattern triggered this extraction."""


@dataclass(slots=True)
class LearningExtractor:
    """Extracts learnings from conversation automatically.

    Uses regex patterns to identify likely learnings.
    Optionally can use an LLM for higher-quality extraction.
    """

    min_confidence: float = 0.5
    """Minimum confidence to report a learning."""

    use_llm: bool = False
    """Whether to use LLM for extraction (slower but better)."""

    llm: ModelProtocol | None = None
    """LLM to use for extraction if use_llm=True."""

    def extract_from_text(self, text: str) -> list[ExtractedLearning]:
        """Extract learnings from text using pre-compiled pattern matching.

        Returns list of extracted learnings, sorted by confidence.
        """
        learnings = []
        text_lower = text.lower()

        for category, patterns in _LEARNING_PATTERNS.items():
            for pattern in patterns:
                # Use pre-compiled pattern's finditer method directly
                for match in pattern.finditer(text_lower):
                    # Get the captured group or full match
                    learning_text = match.group(1) if match.groups() else match.group(0)
                    learning_text = learning_text.strip()

                    # Skip very short or very long extractions
                    if len(learning_text) < 5 or len(learning_text) > 200:
                        continue

                    # Calculate confidence based on pattern specificity
                    confidence = self._calculate_confidence(
                        learning_text, pattern.pattern, category, text
                    )

                    if confidence >= self.min_confidence:
                        learnings.append(ExtractedLearning(
                            text=learning_text,
                            category=category,
                            confidence=confidence,
                            source_text=text[:500],
                            pattern_matched=pattern.pattern,
                        ))

        # Deduplicate similar learnings
        learnings = self._deduplicate(learnings)

        # Sort by confidence
        return sorted(learnings, key=lambda l: l.confidence, reverse=True)

    def extract_from_turn(self, turn: Turn) -> list[ExtractedLearning]:
        """Extract learnings from a conversation turn."""
        # Only extract from assistant responses (they contain findings)
        if turn.turn_type.value != "assistant":
            return []

        return self.extract_from_text(turn.content)

    async def extract_with_llm(self, text: str) -> list[ExtractedLearning]:
        """Use LLM to extract learnings (higher quality, slower)."""
        if not self.llm:
            return self.extract_from_text(text)

        prompt = f"""Extract key learnings from this text. For each learning, identify:
- The fact, constraint, pattern, or dead end
- Its category (fact, constraint, dead_end, pattern)
- Your confidence (0-1)

Text:
{text[:2000]}

Format each learning as:
LEARNING: [text]
CATEGORY: [fact|constraint|dead_end|pattern]
CONFIDENCE: [0.0-1.0]

Only extract clear, actionable learnings. Skip vague observations."""

        result = await self.llm.generate(prompt)

        # Parse LLM response
        learnings = []
        current = {}

        for line in result.content.split("\n"):
            line = line.strip()
            if line.startswith("LEARNING:"):
                if current.get("text"):
                    learnings.append(ExtractedLearning(
                        text=current["text"],
                        category=current.get("category", "fact"),
                        confidence=float(current.get("confidence", 0.7)),
                        source_text=text[:500],
                        pattern_matched="llm",
                    ))
                current = {"text": line[9:].strip()}
            elif line.startswith("CATEGORY:"):
                cat = line[9:].strip().lower()
                if cat in ("fact", "constraint", "dead_end", "pattern"):
                    current["category"] = cat
            elif line.startswith("CONFIDENCE:"):
                with contextlib.suppress(ValueError):
                    current["confidence"] = float(line[11:].strip())

        # Don't forget last one
        if current.get("text"):
            learnings.append(ExtractedLearning(
                text=current["text"],
                category=current.get("category", "fact"),
                confidence=float(current.get("confidence", 0.7)),
                source_text=text[:500],
                pattern_matched="llm",
            ))

        return learnings

    def _calculate_confidence(
        self,
        learning: str,
        pattern: str,
        category: str,
        context: str,
    ) -> float:
        """Calculate confidence score for an extraction."""
        confidence = 0.5  # Base

        # Boost for specific patterns
        if any(x in pattern for x in [r"\d+", "timeout", "limit", "requires"]):
            confidence += 0.2  # Specific patterns more reliable

        # Boost for category-specific keywords in context
        if category == "dead_end" and any(x in context.lower() for x in ["failed", "error", "didn't work"]):
            confidence += 0.15
        elif category == "fact" and any(x in context.lower() for x in ["is", "has", "takes"]):
            confidence += 0.1
        elif category == "constraint" and any(x in context.lower() for x in ["must", "cannot", "blocked"]):
            confidence += 0.15

        # Penalty for very generic extractions
        if len(learning) < 10:
            confidence -= 0.2

        # Boost for numbers (usually more reliable)
        if re.search(r'\d+', learning):
            confidence += 0.1

        return min(1.0, max(0.0, confidence))

    def _deduplicate(self, learnings: list[ExtractedLearning]) -> list[ExtractedLearning]:
        """Remove duplicate or very similar learnings."""
        seen = set()
        unique = []

        for l in learnings:
            # Normalize for comparison
            normalized = l.text.lower().strip()

            # Check for exact or near duplicates
            is_dup = False
            for s in seen:
                if normalized in s or s in normalized:
                    is_dup = True
                    break

            if not is_dup:
                seen.add(normalized)
                unique.append(l)

        return unique


def auto_extract_learnings(
    response_text: str,
    min_confidence: float = 0.6,
) -> list[tuple[str, str, float]]:
    """Convenience function: extract learnings from response.

    Returns list of (learning_text, category, confidence) tuples.
    """
    extractor = LearningExtractor(min_confidence=min_confidence)
    extracted = extractor.extract_from_text(response_text)

    return [(l.text, l.category, l.confidence) for l in extracted]


def extract_user_facts(
    user_message: str,
    min_confidence: float = 0.7,
) -> list[tuple[str, str, float]]:
    """Extract facts stated by user using pre-compiled regex patterns (fallback).

    Returns list of (fact_text, category, confidence) tuples.

    Note: Prefer extract_user_facts_with_llm() for better accuracy.
    """
    learnings = []
    text_lower = user_message.lower()

    for category, patterns in _USER_FACT_PATTERNS.items():
        for pattern in patterns:
            # Use pre-compiled pattern's finditer method directly
            for match in pattern.finditer(text_lower):
                fact_text = match.group(1).strip() if match.groups() else match.group(0).strip()

                # Skip very short extractions
                if len(fact_text) < 2 or len(fact_text) > 100:
                    continue

                # High confidence for explicit statements
                confidence = 0.9

                # Format nicely based on pattern
                pattern_str = pattern.pattern
                if "name" in pattern_str:
                    fact_text = f"User's name is {fact_text}"
                elif "work" in pattern_str:
                    fact_text = f"User works at/on {fact_text}"
                elif "using" in pattern_str or "building" in pattern_str:
                    fact_text = f"User is working with {fact_text}"
                elif "prefer" in pattern_str or "like" in pattern_str:
                    fact_text = f"User prefers {fact_text}"

                learnings.append((fact_text, category, confidence))

    return learnings


def _is_low_quality_fact(text: str) -> bool:
    """Quick sanity check for obviously bad extractions.

    Not heavy regex - just basic quality gates. Trust the LLM prompt.
    """
    text_clean = text.strip().lower()

    # Too short to be useful
    if len(text_clean) < 8:
        return True

    # Looks like a category label (starts with generic word + parenthetical)
    first_word = text_clean.split()[0].rstrip("s:,")
    if first_word in ("names", "preferences", "context", "relationships", "facts") and "(" in text_clean:
        return True

    # Just says "none" or similar
    return text_clean in ("none", "nothing", "n/a", "no facts")


def _infer_fact_category(fact_text: str) -> str:
    """Infer semantic category from fact content."""
    text_lower = fact_text.lower()

    if any(kw in text_lower for kw in ["named", "name is", "called", "nickname"]):
        return "names"
    if any(kw in text_lower for kw in ["pet", "cat", "dog", "family", "wife", "husband"]):
        return "relationships"
    if any(kw in text_lower for kw in ["works at", "job", "project", "building"]):
        return "context"
    if any(kw in text_lower for kw in ["prefer", "like", "favorite"]):
        return "preferences"

    return "fact"


# Prompt for tiny LLM fact extraction
# IMPORTANT: Only extract DURABLE personal facts, not conversation topics
_FACT_EXTRACTION_PROMPT = """Extract ONLY durable personal facts about the user worth remembering.

User message: "{message}"

EXTRACT (worth remembering):
- Names of their pets, family, colleagues
- Their job, role, location, expertise
- Tools, languages, preferences they state

DO NOT EXTRACT:
- What they're asking about (just a topic, not a fact about them)
- Hypothetical questions or wishes
- Conversation fragments

Output one line per fact:
FACT: [specific personal fact]

If no personal facts about the user, output: NONE

Examples:
- "what do stars look like" → NONE (question, not personal fact)
- "I have a cat named Milo" → FACT: User has a cat named Milo
- "I work at NVIDIA on docs" → FACT: User works at NVIDIA on documentation"""


async def extract_user_facts_with_llm(
    user_message: str,
    model: ModelProtocol,
) -> list[tuple[str, str, float]]:
    """Extract facts from user message using a tiny LLM.

    Much more flexible than regex - catches natural variations like:
    - "i have a cat named milo"
    - "milo is my russian blue"
    - "her nickname is kiki"

    Includes echo filtering to prevent prompt example leakage.

    Args:
        user_message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)

    Returns:
        List of (fact_text, category, confidence) tuples.
    """
    from sunwell.models import Message

    prompt = _FACT_EXTRACTION_PROMPT.format(message=user_message)

    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()

        # Parse response with echo filtering
        facts = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line[5:].strip()
                # Filter out echoes and invalid responses
                if (fact_text
                    and fact_text.upper() != "NONE"
                    and not _is_low_quality_fact(fact_text)):
                    # Infer actual category from content
                    category = _infer_fact_category(fact_text)
                    facts.append((fact_text, category, 0.85))
            elif line.upper() == "NONE":
                break

        return facts
    except Exception:
        # Fall back to regex on error
        return extract_user_facts(user_message)
