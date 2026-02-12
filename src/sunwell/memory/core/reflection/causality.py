"""Causality analysis for reflection system.

Determines WHY patterns and constraints exist by analyzing
their common themes and underlying principles.

Part of Phase 3: Reflection System.
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.turn import Learning

logger = logging.getLogger(__name__)


class CausalityAnalyzer:
    """Analyzes causality: WHY do these patterns exist?

    Uses LLM (if available) or heuristic analysis to determine
    the underlying reasons for patterns and constraints.
    """

    def __init__(self, embedder: EmbeddingProtocol | None = None):
        """Initialize causality analyzer.

        Args:
            embedder: Optional embedder (if it supports text generation)
        """
        self._embedder = embedder

    async def analyze_causality(
        self,
        learnings: list[Learning],
        theme: str,
    ) -> tuple[str, str]:
        """Analyze causality for a set of learnings.

        Args:
            learnings: List of learnings to analyze
            theme: Common theme of these learnings

        Returns:
            Tuple of (causality, summary)
            - causality: Why these patterns exist
            - summary: Concise 2-3 sentence summary
        """
        # Try LLM-based analysis if available
        if self._embedder and hasattr(self._embedder, "generate"):
            try:
                return await self._llm_causality(learnings, theme)
            except Exception as e:
                logger.debug(f"LLM causality failed: {e}, falling back to heuristic")

        # Fall back to heuristic analysis
        return self._heuristic_causality(learnings, theme)

    async def _llm_causality(
        self,
        learnings: list[Learning],
        theme: str,
    ) -> tuple[str, str]:
        """LLM-based causality analysis.

        Uses a small model (3B-12B) to analyze causality.

        Args:
            learnings: List of learnings
            theme: Common theme

        Returns:
            Tuple of (causality, summary)
        """
        # Build prompt
        learning_facts = "\n".join(f"- {l.fact}" for l in learnings[:10])  # Limit to 10

        prompt = f"""You are analyzing patterns. Given these constraints about {theme}:

{learning_facts}

1. What principle connects them?
2. Why do they exist? (causality)
3. Summarize in 2-3 sentences.

Output JSON: {{"theme": "...", "causality": "...", "summary": "..."}}"""

        # Generate using embedder (if it supports generation)
        try:
            response = await self._embedder.generate([prompt])
            if response:
                result = json.loads(response[0])
                return result.get("causality", ""), result.get("summary", "")
        except Exception as e:
            logger.debug(f"LLM generation failed: {e}")
            raise

    def _heuristic_causality(
        self,
        learnings: list[Learning],
        theme: str,
    ) -> tuple[str, str]:
        """Heuristic causality analysis.

        Analyzes patterns without LLM by looking at:
        - Category distribution (constraints vs patterns vs preferences)
        - Common keywords and their relationships
        - Confidence levels

        Args:
            learnings: List of learnings
            theme: Common theme

        Returns:
            Tuple of (causality, summary)
        """
        # Analyze categories
        categories = [l.category for l in learnings]
        category_counts = {}
        for cat in categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1

        dominant_category = max(category_counts, key=category_counts.get)

        # Build causality based on category
        if dominant_category == "constraint":
            causality = f"These constraints ensure {theme} follows best practices and avoids common pitfalls"
        elif dominant_category == "pattern":
            causality = f"These patterns provide proven solutions for {theme} based on experience"
        elif dominant_category == "dead_end":
            causality = f"These represent failed approaches in {theme} that should be avoided"
        elif dominant_category == "preference":
            causality = f"These preferences optimize the development experience for {theme}"
        else:
            causality = f"These guidelines help maintain consistency and quality in {theme}"

        # Build summary
        count = len(learnings)
        high_confidence = sum(1 for l in learnings if l.confidence >= 0.8)
        confidence_ratio = high_confidence / count if count > 0 else 0

        if confidence_ratio >= 0.7:
            confidence_desc = "well-established"
        elif confidence_ratio >= 0.4:
            confidence_desc = "moderately confident"
        else:
            confidence_desc = "exploratory"

        summary = (
            f"Based on {count} {confidence_desc} learnings, "
            f"{theme} requires attention to {dominant_category} guidelines. "
            f"{causality}."
        )

        return causality, summary

    def extract_principles(self, learnings: list[Learning]) -> list[str]:
        """Extract core principles from learnings.

        Args:
            learnings: List of learnings

        Returns:
            List of principle strings
        """
        # Look for learnings that state principles
        # Heuristic: statements with "should", "must", "always", "never"
        principle_keywords = ["should", "must", "always", "never", "requires", "needs"]

        principles = []
        for learning in learnings:
            fact_lower = learning.fact.lower()
            if any(keyword in fact_lower for keyword in principle_keywords):
                # This looks like a principle
                principles.append(learning.fact)

        return principles[:5]  # Top 5 principles

    def extract_patterns(self, learnings: list[Learning]) -> list[str]:
        """Extract key patterns from learnings.

        Args:
            learnings: List of learnings

        Returns:
            List of pattern strings
        """
        # Look for learnings categorized as patterns
        patterns = [l.fact for l in learnings if l.category == "pattern"]

        # Also look for template-like statements
        if not patterns:
            patterns = [l.fact for l in learnings if l.category == "template"]

        return patterns[:5]  # Top 5 patterns

    def extract_anti_patterns(self, learnings: list[Learning]) -> list[str]:
        """Extract anti-patterns from learnings.

        Args:
            learnings: List of learnings

        Returns:
            List of anti-pattern strings
        """
        # Look for dead_ends or constraints that say "don't"
        anti_patterns = []

        for learning in learnings:
            if learning.category == "dead_end":
                anti_patterns.append(learning.fact)
            elif "don't" in learning.fact.lower() or "avoid" in learning.fact.lower():
                anti_patterns.append(learning.fact)

        return anti_patterns[:5]  # Top 5 anti-patterns
