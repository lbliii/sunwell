"""Regex patterns and prompts for behavior/fact extraction."""

# Three-tier extraction prompt (RFC-023 + interests)
# Extracts: FACTS (stated), INTERESTS (inferred), BEHAVIORS (observed)
TWO_TIER_EXTRACTION_PROMPT = """Extract information about the user from their message.

User message: "{message}"

Extract THREE types of signals:

1. FACT - Something they explicitly state about themselves:
   - Names (pets, family, colleagues)
   - Job, role, expertise, location
   - Tools, languages, preferences
   Example: "I have a cat named Milo" → FACT: User has a cat named Milo

2. INTEREST - Inferred from what they ask about or discuss:
   - Topics they keep asking about
   - Domains they're curious about
   - Goals or aspirations
   Example: "why do stars twinkle" → INTEREST: Curious about astronomy/space
   Example: "I want to space travel" → INTEREST: Interested in space exploration

3. BEHAVIOR - How they communicate:
   - Tone (casual, formal)
   - Style (brief, detailed)
   - Patterns (asks follow-ups, tests memory)
   Example: "lol that's cool" → BEHAVIOR: Uses casual language

Output format (one per line):
FACT: [explicit personal fact]
INTEREST: [inferred interest/curiosity area]
BEHAVIOR: [communication pattern]

If NONE of these apply, output: NONE

Important:
- FACT requires explicit statement ("I am", "I have", "I work")
- INTEREST can be inferred from questions/topics
- Don't output category names, output specific observations"""

# Behavior-only extraction prompt (lighter weight)
BEHAVIOR_EXTRACTION_PROMPT = """Identify behavioral patterns in this user message.

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
