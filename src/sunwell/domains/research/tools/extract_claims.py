"""Claim extraction tool for research domain."""

import re

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="extract_claims",
    simple_description="Extract factual claims from text",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance=(
        "Use extract_claims to identify factual assertions that can be verified. "
        "This helps fact-check research and identify key claims."
    ),
)
class ExtractClaimsTool(BaseTool):
    """Extract factual claims from text.

    Identifies sentences that make verifiable factual assertions
    (statements that can be proven true or false).
    """

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Text content to extract claims from",
            },
            "max_claims": {
                "type": "integer",
                "description": "Maximum number of claims to extract (default: 10)",
                "default": 10,
            },
        },
        "required": ["content"],
    }

    async def execute(self, arguments: dict) -> str:
        """Extract factual claims from content.

        Args:
            arguments: Must contain 'content', optionally 'max_claims'

        Returns:
            List of extracted claims with confidence scores
        """
        content = arguments["content"]
        max_claims = arguments.get("max_claims", 10)

        # Check if content is a file path
        path = self.resolve_path(content)
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")

        if not content.strip():
            return "No content to analyze."

        claims = self._extract_claims(content, max_claims)

        if not claims:
            return "No factual claims found in content."

        output = ["**Factual Claims Found:**\n"]
        for i, (claim, confidence) in enumerate(claims, 1):
            confidence_label = "HIGH" if confidence > 0.7 else "MEDIUM" if confidence > 0.4 else "LOW"
            output.append(f"{i}. [{confidence_label}] {claim}")

        output.append(f"\nTotal: {len(claims)} claim(s) extracted")
        return "\n".join(output)

    def _extract_claims(
        self,
        content: str,
        max_claims: int,
    ) -> list[tuple[str, float]]:
        """Extract factual claims from content.

        Returns list of (claim, confidence) tuples.
        """
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        claims: list[tuple[str, float]] = []

        # Patterns that indicate factual claims
        claim_patterns = [
            # "X is/are Y" patterns
            (re.compile(r"^[A-Z][^.]*\b(?:is|are|was|were)\b[^.]*[a-z]", re.IGNORECASE), 0.8),
            # Contains numbers/statistics
            (re.compile(r"\b\d+(?:\.\d+)?%?\b"), 0.9),
            # Contains dates
            (re.compile(r"\b(?:19|20)\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b", re.IGNORECASE), 0.85),
            # "According to" patterns
            (re.compile(r"\baccording to\b", re.IGNORECASE), 0.9),
            # Comparative statements
            (re.compile(r"\b(?:more|less|greater|fewer|higher|lower)\s+than\b", re.IGNORECASE), 0.75),
            # Definitive statements
            (re.compile(r"\b(?:always|never|all|none|every)\b", re.IGNORECASE), 0.6),
        ]

        # Opinion indicators (lower confidence or skip)
        opinion_patterns = [
            re.compile(r"\b(?:I think|I believe|in my opinion|perhaps|maybe|might|could|should)\b", re.IGNORECASE),
            re.compile(r"^\s*(?:perhaps|maybe|probably)", re.IGNORECASE),
        ]

        for sentence in sentences:
            # Skip obvious opinions
            if any(p.search(sentence) for p in opinion_patterns):
                continue

            # Score sentence based on claim patterns
            score = 0.0
            matches = 0
            for pattern, weight in claim_patterns:
                if pattern.search(sentence):
                    score += weight
                    matches += 1

            if matches > 0:
                # Normalize score
                avg_score = score / matches
                claims.append((sentence, avg_score))

        # Sort by confidence and return top N
        claims.sort(reverse=True, key=lambda x: x[1])
        return claims[:max_claims]
