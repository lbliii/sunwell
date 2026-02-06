"""Research domain for knowledge work (RFC-DOMAINS).

The research domain handles:
- Web search and information gathering
- Content summarization
- Fact extraction and verification
- Source citation

This domain provides research-specific tools and validators
for knowledge-intensive tasks.
"""

from sunwell.domains.protocol import BaseDomain, DomainType
from sunwell.domains.research.validators import (
    CoherenceValidator,
    SourceValidator,
)

# Keywords for research domain detection
_RESEARCH_KEYWORDS: frozenset[str] = frozenset({
    # Actions
    "research",
    "find",
    "learn",
    "understand",
    "summarize",
    "explain",
    "investigate",
    "explore",
    "discover",
    "analyze",
    # Objects
    "information",
    "sources",
    "facts",
    "evidence",
    "data",
    "study",
    "report",
    "article",
    "paper",
    "topic",
    # Questions
    "what",
    "why",
    "how",
    "history",
    "overview",
    "comparison",
})


class ResearchDomain(BaseDomain):
    """Research and knowledge work domain.

    Provides:
    - Tools: Web search, summarize, extract_claims
    - Validators: Source verification, coherence checking
    - Patterns: Research insights, citations
    """

    def __init__(self) -> None:
        super().__init__()
        self._domain_type = DomainType.RESEARCH
        self._tools_package = "sunwell.domains.research.tools"
        self._validators = [
            SourceValidator(),
            CoherenceValidator(),
        ]
        self._default_validator_names = frozenset({"sources"})
        self._keywords = _RESEARCH_KEYWORDS
        self._high_conf_keywords = frozenset({
            "research", "investigate", "summarize", "sources", "evidence",
        })
        self._medium_conf_keywords = frozenset({
            "find", "learn", "understand", "explain", "analyze",
        })

    def detect_confidence(self, goal: str) -> float:
        """Detect if goal is research-related.

        Extends base tiered keyword matching with question pattern detection.
        """
        score = super().detect_confidence(goal)

        # Question words at start suggest research (+0.3)
        goal_lower = goal.lower()
        question_starts = ("what ", "why ", "how ", "who ", "when ", "where ")
        if any(goal_lower.startswith(start) for start in question_starts):
            score += 0.3

        return min(score, 1.0)

    def extract_learnings(self, artifact: str, file_path: str | None = None) -> list:
        """Extract research patterns from artifact.

        For research domain, learnings are:
        - Key facts discovered
        - Source citations
        - Topic connections
        """
        from sunwell.agent.learning.learning import Learning

        learnings: list[Learning] = []

        # Extract citations (URLs)
        import re

        url_pattern = re.compile(r"https?://[^\s]+")
        urls = url_pattern.findall(artifact)
        if urls:
            learnings.append(
                Learning(
                    fact=f"Sources used: {', '.join(urls[:5])}",
                    category="source",
                    confidence=0.9,
                )
            )

        # Extract key claims (sentences with strong assertions)
        claim_patterns = [
            re.compile(r"([A-Z][^.!?]*\b(?:is|are|was|were|has|have)\b[^.!?]+[.!?])"),
        ]
        for pattern in claim_patterns:
            matches = pattern.findall(artifact)
            for match in matches[:3]:  # Limit to 3 claims
                if len(match) > 20 and len(match) < 200:
                    learnings.append(
                        Learning(
                            fact=match.strip(),
                            category="claim",
                            confidence=0.7,
                        )
                    )

        return learnings


__all__ = [
    "CoherenceValidator",
    "ResearchDomain",
    "SourceValidator",
]
