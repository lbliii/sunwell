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

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.simulacrum.turn import Turn, Learning
    from sunwell.models.protocol import ModelProtocol


# Patterns that indicate a learning (from final responses)
LEARNING_PATTERNS = {
    # Facts
    "fact": [
        r"(?:the |it )(?:is|has|takes|uses|requires) (\d+[^\.,]*)",  # "it takes 5 seconds"
        r"(?:must|should|need to) (?:be |use |have )([^\.]+)",  # "must be authenticated"
        r"(?:always|never) ([^\.]+)",  # "always returns JSON"
        r"(?:default|defaults to) ([^\.]+)",  # "defaults to 1000"
        r"timeout (?:is|of) (\d+[^\.,]*)",  # "timeout is 5s"
        r"limit (?:is|of) (\d+[^\.,]*)",  # "limit is 100"
    ],
}

# Patterns for user-stated facts (personal info, preferences, context)
USER_FACT_PATTERNS = {
    "fact": [
        r"(?:my name is|i'm called|call me) ([a-zA-Z][a-zA-Z0-9_\- ]{1,30})",  # "my name is lb"
        r"(?:i am|i'm) (?:a |an )?([a-zA-Z][a-zA-Z0-9_\- ]{2,40})",  # "i am a developer"
        r"(?:i work (?:at|for|on)) ([^\.]{3,50})",  # "i work at google"
        r"(?:i(?:'m| am) (?:using|working with|building)) ([^\.]{3,50})",  # "i'm using python"
        r"(?:my (?:project|app|team|company) is) ([^\.]{3,50})",  # "my project is sunwell"
        r"(?:i prefer|i like|i use) ([^\.]{3,50})",  # "i prefer typescript"
    ],
    
    # Constraints
    "constraint": [
        r"(?:cannot|can't|won't|doesn't) ([^\.]+)",  # "can't exceed 1000"
        r"(?:blocked by|prevented by|limited by) ([^\.]+)",  # "blocked by firewall"
        r"(?:requires?|needs?) ([^\.]+?) (?:to|before|first)",  # "requires auth to access"
        r"(?:only works|only valid) (?:with|when|if) ([^\.]+)",  # "only works with v2"
    ],
    
    # Dead ends
    "dead_end": [
        r"(?:tried|attempted) ([^\.]+?) (?:but|however|didn't|failed)",  # "tried X but failed"
        r"(?:doesn't|won't|can't) work (?:because|due to|since) ([^\.]+)",  # "doesn't work because Y"
        r"(?:this approach|that method|this solution) (?:won't|doesn't|failed)",
        r"dead.?end|doesn't help|no luck|didn't work",
    ],
    
    # Patterns
    "pattern": [
        r"(?:whenever|every time|each time) ([^\.]+)",  # "whenever X happens"
        r"(?:pattern|trend|consistently) ([^\.]+)",  # "pattern of failures"
        r"(?:seems to|appears to|tends to) ([^\.]+)",  # "seems to timeout"
    ],
}

# THINKING TOKEN patterns - more informal, reasoning-style language
THINKING_PATTERNS = {
    # Facts discovered during reasoning
    "fact": [
        r"(?:I notice|I see|looking at|checking) .{0,20}(\d+[^\.,\n]*)",  # "I see it's 5 seconds"
        r"(?:it looks like|apparently|it seems) ([^,\n]+)",  # "it looks like the limit is 100"
        r"(?:the .{0,30}) (?:is|are|has|have) (\d+[^\n,]*)",  # "the timeout is 5s"
        r"(?:found|discovered|noticed) (?:that )?([^,\n]+)",  # "found that auth is required"
    ],
    
    # Rejected alternatives (GOLD for dead ends!)
    "dead_end": [
        r"(?:but |however |although )(?:that |this )(?:won't|wouldn't|can't|couldn't) ([^\n,]+)",
        r"(?:I considered|I thought about|maybe) .{0,30}(?:but|however) ([^\n]+)",  # "I thought about X but..."
        r"(?:this won't work|that's not going to work|can't do that) (?:because|since|as) ([^\n]+)",
        r"(?:ruled out|rejected|dismissed|discarded) ([^\n,]+)",  # "ruled out caching"
        r"(?:too |overly )(?:slow|expensive|complex|risky)([^\n,]*)",  # "too slow for production"
        r"(?:not viable|not feasible|not practical|won't scale)([^\n,]*)",
    ],
    
    # Constraints/assumptions
    "constraint": [
        r"(?:assuming|given that|since|because) ([^\n,]+?) (?:we|I|this)",  # "assuming auth is required..."
        r"(?:we need to|I need to|must) (?:ensure|make sure|guarantee) ([^\n,]+)",
        r"(?:the constraint|limitation|restriction) (?:is|here is) ([^\n,]+)",
        r"(?:can only|must only|should only) ([^\n,]+)",
    ],
    
    # Uncertainty signals (lower confidence)
    "uncertainty": [
        r"(?:I'm not sure|not certain|unclear|might be wrong) ([^\n,]+)",
        r"(?:probably|likely|possibly|maybe) ([^\n,]+?) (?:but|though|however)",
        r"(?:need to verify|should check|worth confirming) ([^\n,]+)",
    ],
}


@dataclass
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


@dataclass
class LearningExtractor:
    """Extracts learnings from conversation automatically.
    
    Uses regex patterns to identify likely learnings.
    Optionally can use an LLM for higher-quality extraction.
    """
    
    min_confidence: float = 0.5
    """Minimum confidence to report a learning."""
    
    use_llm: bool = False
    """Whether to use LLM for extraction (slower but better)."""
    
    llm: "ModelProtocol | None" = None
    """LLM to use for extraction if use_llm=True."""
    
    def extract_from_text(self, text: str) -> list[ExtractedLearning]:
        """Extract learnings from text using pattern matching.
        
        Returns list of extracted learnings, sorted by confidence.
        """
        learnings = []
        text_lower = text.lower()
        
        for category, patterns in LEARNING_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                
                for match in matches:
                    # Get the captured group or full match
                    learning_text = match.group(1) if match.groups() else match.group(0)
                    learning_text = learning_text.strip()
                    
                    # Skip very short or very long extractions
                    if len(learning_text) < 5 or len(learning_text) > 200:
                        continue
                    
                    # Calculate confidence based on pattern specificity
                    confidence = self._calculate_confidence(
                        learning_text, pattern, category, text
                    )
                    
                    if confidence >= self.min_confidence:
                        learnings.append(ExtractedLearning(
                            text=learning_text,
                            category=category,
                            confidence=confidence,
                            source_text=text[:500],
                            pattern_matched=pattern,
                        ))
        
        # Deduplicate similar learnings
        learnings = self._deduplicate(learnings)
        
        # Sort by confidence
        return sorted(learnings, key=lambda l: l.confidence, reverse=True)
    
    def extract_from_turn(self, turn: "Turn") -> list[ExtractedLearning]:
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
                try:
                    current["confidence"] = float(line[11:].strip())
                except ValueError:
                    pass
        
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
    """Extract facts stated by user using regex patterns (fallback).
    
    Returns list of (fact_text, category, confidence) tuples.
    
    Note: Prefer extract_user_facts_with_llm() for better accuracy.
    """
    learnings = []
    text_lower = user_message.lower()
    
    for category, patterns in USER_FACT_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            
            for match in matches:
                fact_text = match.group(1).strip() if match.groups() else match.group(0).strip()
                
                # Skip very short extractions
                if len(fact_text) < 2 or len(fact_text) > 100:
                    continue
                
                # High confidence for explicit statements
                confidence = 0.9
                
                # Format nicely based on pattern
                if "name" in pattern:
                    fact_text = f"User's name is {fact_text}"
                elif "work" in pattern:
                    fact_text = f"User works at/on {fact_text}"
                elif "using" in pattern or "building" in pattern:
                    fact_text = f"User is working with {fact_text}"
                elif "prefer" in pattern or "like" in pattern:
                    fact_text = f"User prefers {fact_text}"
                
                learnings.append((fact_text, category, confidence))
    
    return learnings


# Prompt for tiny LLM fact extraction
_FACT_EXTRACTION_PROMPT = """Extract personal facts from this user message. Return ONLY facts worth remembering.

User message: "{message}"

For each fact, output one line in format:
FACT: [the fact to remember]

Examples of facts worth extracting:
- Names (user's name, pet names, family names)
- Preferences (likes, dislikes, favorites)
- Context (job, location, projects, pets, hobbies)
- Relationships (has a cat, works with someone)

If no personal facts are present, output: NONE

Facts:"""


async def extract_user_facts_with_llm(
    user_message: str,
    model: "ModelProtocol",
) -> list[tuple[str, str, float]]:
    """Extract facts from user message using a tiny LLM.
    
    Much more flexible than regex - catches natural variations like:
    - "i have a cat named milo"
    - "milo is my russian blue"
    - "her nickname is kiki"
    
    Args:
        user_message: The user's input message
        model: A tiny LLM (gemma3:1b, gpt-4o-mini, etc.)
    
    Returns:
        List of (fact_text, category, confidence) tuples.
    """
    from sunwell.models.protocol import Message
    
    prompt = _FACT_EXTRACTION_PROMPT.format(message=user_message)
    
    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()
        
        # Parse response
        facts = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line[5:].strip()
                if fact_text and len(fact_text) > 3 and fact_text.upper() != "NONE":
                    facts.append((fact_text, "fact", 0.85))
            elif line.upper() == "NONE":
                break
        
        return facts
    except Exception:
        # Fall back to regex on error
        return extract_user_facts(user_message)
