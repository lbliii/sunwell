"""Intelligence Extractor - RFC-045 Integration.

Extract project intelligence from conversation history when Simulacrum
demotes chunks to warm/cold tiers.
"""


import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.intelligence.context import ProjectContext
    from sunwell.simulacrum.hierarchical.chunks import Chunk


# Pre-compiled regex patterns for decision extraction
_DECISION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:we|let's|i|we'll)\s+(?:decided|chose|use|going with)\s+([^,\.]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:decision|choice|using|chose)\s*:?\s*([^,\.]+)", re.IGNORECASE),
)

_INSTEAD_PATTERN: re.Pattern[str] = re.compile(
    r"([^,\.]+)\s+instead\s+of\s+([^,\.]+)\s+because\s+([^,\.]+)", re.IGNORECASE
)

# Pre-compiled regex patterns for failure extraction
_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"error\s*:?\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"exception\s*:?\s*([^\n]+)", re.IGNORECASE),
    re.compile(r"failed\s+because\s+([^\n]+)", re.IGNORECASE),
)

_FAILURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:that|this|it)\s+(?:didn't|doesn't)\s+work\s+because\s+([^\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:approach|method|solution)\s+failed\s+because\s+([^\n]+)", re.IGNORECASE
    ),
)

# Category keywords for decision classification
_CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "database": frozenset(["sql", "db", "database", "postgres", "sqlite", "mysql"]),
    "auth": frozenset(["auth", "authentication", "jwt", "oauth", "login"]),
    "framework": frozenset(["framework", "django", "flask", "fastapi"]),
    "caching": frozenset(["cache", "redis", "memcached"]),
    "testing": frozenset(["test", "pytest", "unittest"]),
}


class IntelligenceExtractor:
    """Extract project intelligence from conversation history."""

    def __init__(self, context: ProjectContext):
        """Initialize intelligence extractor.

        Args:
            context: Project context for storing extracted intelligence
        """
        self.context = context

    async def on_chunk_demotion(
        self,
        chunk: Chunk,
    ) -> None:
        """Called when Simulacrum demotes a chunk to warm/cold tier.

        Args:
            chunk: The chunk being demoted
        """
        # Extract content from chunk
        content = self._get_chunk_content(chunk)

        # Get session ID from chunk or context
        session_id = getattr(chunk, "session_id", "") or getattr(
            self.context.simulacrum, "_session_id", ""
        )

        # 1. Extract architectural decisions from conversation
        decisions = await self._extract_decisions(content, session_id)
        for decision in decisions:
            await self.context.decisions.record_decision(
                category=decision["category"],
                question=decision["question"],
                choice=decision["choice"],
                rejected=decision["rejected"],
                rationale=decision["rationale"],
                context=decision.get("context", ""),
                session_id=session_id,
            )

        # 2. Extract failure patterns from error discussions
        failures = await self._extract_failures(content, session_id)
        for failure in failures:
            await self.context.failures.record_failure(
                description=failure["description"],
                error_type=failure["error_type"],
                error_message=failure["error_message"],
                context=failure.get("context", ""),
                code=failure.get("code_snapshot"),
                session_id=session_id,
            )

        # Pattern learning happens in real-time during edits (not from demoted chunks)
        # Edits are tracked at the turn level, not chunk level

    def _get_chunk_content(self, chunk: Chunk) -> str:
        """Extract text content from chunk.

        Chunks can have content in different forms depending on tier:
        - HOT: Full turns with content
        - WARM: CTF-encoded content (would need decoding)
        - COLD: Summary only

        For intelligence extraction, we prioritize:
        1. Summary (most concise, always available)
        2. Full turns (if available)
        """
        # Prefer summary (always available, concise)
        if chunk.summary:
            return chunk.summary

        # Fall back to turns if available (HOT tier)
        if chunk.turns:
            return "\n".join(
                f"{turn.turn_type.value}: {turn.content}"
                for turn in chunk.turns
            )

        # WARM tier has CTF-encoded content, but decoding is expensive
        # For intelligence extraction, summary is sufficient
        return ""

    async def _extract_decisions(
        self,
        content: str,
        session_id: str,
    ) -> list[dict]:
        """Extract decisions from conversation turns.

        Looks for patterns like:
        - "Let's use X instead of Y because..."
        - "We decided on X"
        - "I chose X over Y since..."

        Args:
            content: Conversation content
            session_id: Session identifier

        Returns:
            List of extracted decisions
        """
        decisions = []

        # Pattern 1: "We decided on X" or "Let's use X"
        for pattern in _DECISION_PATTERNS:
            for match in pattern.finditer(content):
                choice = match.group(1).strip()
                if len(choice) > 3:  # Filter out very short matches
                    decisions.append({
                        "category": self._infer_category(choice),
                        "question": f"What to use for {choice}?",
                        "choice": choice,
                        "rejected": [],
                        "rationale": "Extracted from conversation",
                        "context": content[:200],  # First 200 chars for context
                    })

        # Pattern 2: "X instead of Y because..."
        for match in _INSTEAD_PATTERN.finditer(content):
            choice = match.group(1).strip()
            rejected_option = match.group(2).strip()
            rationale = match.group(3).strip()

            decisions.append({
                "category": self._infer_category(choice),
                "question": "Which option to use?",
                "choice": choice,
                "rejected": [(rejected_option, rationale)],
                "rationale": rationale,
                "context": content[:200],
            })

        return decisions

    async def _extract_failures(
        self,
        content: str,
        session_id: str,
    ) -> list[dict]:
        """Extract failures from conversation turns.

        Looks for patterns like:
        - "That didn't work because..."
        - "Error: ..."
        - "Let's try a different approach"

        Args:
            content: Conversation content
            session_id: Session identifier

        Returns:
            List of extracted failures
        """
        failures = []

        # Pattern 1: "Error:" or "Exception:"
        for pattern in _ERROR_PATTERNS:
            for match in pattern.finditer(content):
                error_msg = match.group(1).strip()
                failures.append({
                    "description": "Extracted from conversation",
                    "error_type": "runtime_error",
                    "error_message": error_msg,
                    "context": content[:200],
                })

        # Pattern 2: "That didn't work" or "This approach failed"
        for pattern in _FAILURE_PATTERNS:
            for match in pattern.finditer(content):
                reason = match.group(1).strip()
                failures.append({
                    "description": "Extracted from conversation",
                    "error_type": "user_rejection",
                    "error_message": reason,
                    "context": content[:200],
                })

        return failures

    def _infer_category(self, text: str) -> str:
        """Infer decision category from text."""
        text_lower = text.lower()

        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return "general"
