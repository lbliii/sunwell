"""Expertise Extraction for Planning (RFC-039).

Extracts relevant heuristics from lenses based on the goal.
Supports both keyword-based filtering and semantic ranking.

Example:
    >>> from sunwell.naaru.expertise import ExpertiseExtractor
    >>>
    >>> extractor = ExpertiseExtractor(lenses=[tech_writer_lens])
    >>> context = await extractor.extract("Write API documentation")
    >>>
    >>> for h in context.heuristics:
    ...     print(f"{h.name}: {h.rule}")
    Progressive Disclosure: Layer information by expertise level
    Signal-to-Noise: Every sentence must earn its place
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.heuristic import Heuristic
    from sunwell.core.lens import Lens
    from sunwell.embedding.protocol import Embedder

from sunwell.naaru.expertise.context import (
    ExpertiseContext,
    HeuristicSummary,
)


@dataclass
class ExpertiseExtractor:
    """Extract relevant expertise from lenses for a goal.

    Collects heuristics from loaded lenses and filters them based
    on relevance to the goal. Supports keyword-based filtering
    and optional semantic ranking.

    Example:
        >>> extractor = ExpertiseExtractor(lenses=[my_lens])
        >>> context = await extractor.extract("Build REST API")
    """

    lenses: list[Lens]
    embedder: Embedder | None = None

    # Extraction settings
    max_heuristics: int = 5
    min_relevance: float = 0.1

    # Cache
    _all_heuristics: list[tuple[Heuristic, str]] | None = field(
        default=None, init=False
    )

    def _collect_heuristics(self) -> list[tuple[Heuristic, str]]:
        """Collect all heuristics from lenses with source info.

        Returns list of (heuristic, source_lens_name) tuples.
        """
        if self._all_heuristics is not None:
            return self._all_heuristics

        result: list[tuple[Heuristic, str]] = []

        for lens in self.lenses:
            lens_name = getattr(lens.metadata, 'name', 'Unknown') if hasattr(lens, 'metadata') else 'Unknown'

            for h in lens.heuristics:
                result.append((h, lens_name))

        self._all_heuristics = result
        return result

    async def extract(
        self,
        goal: str,
        artifact_type: str | None = None,
    ) -> ExpertiseContext:
        """Extract relevant expertise for a goal.

        Args:
            goal: The user's goal
            artifact_type: Optional artifact type hint (e.g., "api_reference")

        Returns:
            ExpertiseContext with relevant heuristics and validators
        """
        if not self.lenses:
            return ExpertiseContext(domain="general")

        # Collect all heuristics
        all_heuristics = self._collect_heuristics()

        if not all_heuristics:
            return ExpertiseContext(
                domain="general",
                source_lenses=[self._get_lens_name(l) for l in self.lenses],
            )

        # Score heuristics by relevance
        scored = self._keyword_score(goal, artifact_type, all_heuristics)

        # Optionally re-rank with embeddings
        if self.embedder and len(scored) > self.max_heuristics:
            scored = await self._semantic_rank(goal, scored)

        # Filter by minimum relevance
        scored = [(h, s, rel) for h, s, rel in scored if rel >= self.min_relevance]

        # Take top heuristics
        top_heuristics = scored[:self.max_heuristics]

        # Build summaries
        heuristic_summaries = [
            HeuristicSummary.from_heuristic(h, relevance=rel)
            for h, _source, rel in top_heuristics
        ]

        # Collect validators from lenses
        validators = []
        for lens in self.lenses:
            # Lens uses all_validators property (deterministic + heuristic)
            if hasattr(lens, 'all_validators'):
                validators.extend(lens.all_validators)
            elif hasattr(lens, 'deterministic_validators'):
                validators.extend(lens.deterministic_validators)
                if hasattr(lens, 'heuristic_validators'):
                    validators.extend(lens.heuristic_validators)

        # Get source lens names
        source_lenses = list(dict.fromkeys([
            s for _h, s, _r in top_heuristics
        ]))

        # Detect domain from lenses
        domain = self._detect_domain_from_lenses()

        return ExpertiseContext(
            heuristics=heuristic_summaries,
            validators=validators,
            domain=domain,
            source_lenses=source_lenses,
        )

    def _keyword_score(
        self,
        goal: str,
        artifact_type: str | None,
        heuristics: list[tuple[Heuristic, str]],
    ) -> list[tuple[Heuristic, str, float]]:
        """Score heuristics by keyword matching.

        Returns list of (heuristic, source, relevance_score).
        """
        goal_lower = goal.lower()
        goal_words = set(goal_lower.split())

        # Stop words to ignore in matching
        stop_words = {
            "the", "a", "an", "is", "are", "be", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "and", "or", "but",
            "if", "then", "else", "when", "where", "how", "what", "which",
        }
        goal_words = goal_words - stop_words

        scored: list[tuple[Heuristic, str, float]] = []

        for h, source in heuristics:
            # Build heuristic text for matching
            h_text = f"{h.name} {h.rule}".lower()
            h_words = set(h_text.split()) - stop_words

            # Calculate overlap
            overlap = len(goal_words & h_words)

            # Normalize by smaller set size
            if goal_words and h_words:
                relevance = overlap / min(len(goal_words), len(h_words))
            else:
                relevance = 0.0

            # Boost for artifact type match
            if artifact_type and artifact_type.lower() in h.name.lower():
                relevance += 0.3

            # Boost for exact phrase matches
            if h.name.lower() in goal_lower:
                relevance += 0.5

            # Cap at 1.0
            relevance = min(relevance, 1.0)

            # Always include heuristics with some patterns (they're useful)
            if h.always or h.never:
                relevance = max(relevance, 0.1)

            scored.append((h, source, relevance))

        # Sort by relevance
        scored.sort(key=lambda x: x[2], reverse=True)

        return scored

    async def _semantic_rank(
        self,
        goal: str,
        scored: list[tuple[Heuristic, str, float]],
    ) -> list[tuple[Heuristic, str, float]]:
        """Re-rank heuristics using semantic similarity.

        Only called if embedder is available and we have more
        candidates than max_heuristics.
        """
        if not self.embedder:
            return scored

        try:
            # Get goal embedding
            goal_embedding = await self.embedder.embed(goal)

            # Get heuristic embeddings
            h_texts = [f"{h.name}: {h.rule}" for h, _s, _r in scored]
            h_embeddings = await self.embedder.embed_batch(h_texts)

            # Calculate similarities
            reranked = []
            for i, (h, source, keyword_score) in enumerate(scored):
                similarity = self._cosine_similarity(goal_embedding, h_embeddings[i])

                # Combine keyword score and semantic similarity
                combined = 0.5 * keyword_score + 0.5 * similarity
                reranked.append((h, source, combined))

            # Sort by combined score
            reranked.sort(key=lambda x: x[2], reverse=True)

            return reranked

        except Exception:
            # Fall back to keyword scoring on any error
            return scored

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b, strict=False))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    def _detect_domain_from_lenses(self) -> str:
        """Detect domain based on lens metadata."""
        for lens in self.lenses:
            if hasattr(lens, 'metadata') and hasattr(lens.metadata, 'domain'):
                return lens.metadata.domain

        # Infer from lens names
        for lens in self.lenses:
            name = self._get_lens_name(lens).lower()
            if "writer" in name or "doc" in name:
                return "documentation"
            if "coder" in name or "dev" in name:
                return "code"
            if "review" in name or "qa" in name:
                return "review"

        return "general"

    def _get_lens_name(self, lens: Lens) -> str:
        """Get lens name safely."""
        if hasattr(lens, 'metadata') and hasattr(lens.metadata, 'name'):
            return lens.metadata.name
        return "Unknown"


async def extract_expertise(
    goal: str,
    lenses: list[Lens],
    max_heuristics: int = 5,
) -> ExpertiseContext:
    """Extract expertise for a goal from lenses.

    Convenience function for quick extraction.

    Args:
        goal: The user's goal
        lenses: Lenses to extract from
        max_heuristics: Maximum heuristics to include

    Returns:
        ExpertiseContext with relevant expertise
    """
    extractor = ExpertiseExtractor(
        lenses=lenses,
        max_heuristics=max_heuristics,
    )
    return await extractor.extract(goal)


def load_dori_rules_as_heuristics(rule_paths: list[Path]) -> list[Heuristic]:
    """Load DORI rules and convert to heuristics.

    Parses DORI rule files (.mdc) and extracts heuristic-like
    patterns (always/never lists, principles).

    Args:
        rule_paths: Paths to DORI rule files

    Returns:
        List of Heuristic-like objects
    """

    heuristics: list[Heuristic] = []

    for path in rule_paths:
        if not path.exists():
            continue

        try:
            content = path.read_text()
            parsed = _parse_dori_rule(content, path.stem)
            heuristics.extend(parsed)
        except Exception:
            continue

    return heuristics


def _parse_dori_rule(content: str, rule_name: str) -> list[Heuristic]:
    """Parse DORI rule content into heuristics.

    Simple parser that extracts:
    - ## headers as heuristic names
    - Lists starting with ✅ or "Do" as always patterns
    - Lists starting with ❌ or "Don't" as never patterns
    """
    from sunwell.core.heuristic import Heuristic

    heuristics: list[Heuristic] = []

    lines = content.split('\n')
    current_name = rule_name
    current_rule = ""
    current_always: list[str] = []
    current_never: list[str] = []

    for line in lines:
        line = line.strip()

        # New section
        if line.startswith('## '):
            # Save previous
            if current_rule or current_always or current_never:
                heuristics.append(Heuristic(
                    name=current_name,
                    rule=current_rule,
                    always=current_always,
                    never=current_never,
                ))

            current_name = line[3:].strip()
            current_rule = ""
            current_always = []
            current_never = []

        # Rule text (first paragraph after header)
        elif line and not current_rule and not line.startswith('-') and not line.startswith('*'):
            current_rule = line

        # Always patterns
        elif line.startswith('- ✅') or line.lower().startswith('- do:'):
            pattern = line.split(':', 1)[-1].strip() if ':' in line else line[4:].strip()
            if pattern:
                current_always.append(pattern)

        # Never patterns
        elif line.startswith('- ❌') or line.lower().startswith("- don't:"):
            pattern = line.split(':', 1)[-1].strip() if ':' in line else line[4:].strip()
            if pattern:
                current_never.append(pattern)

    # Save last
    if current_rule or current_always or current_never:
        heuristics.append(Heuristic(
            name=current_name,
            rule=current_rule,
            always=current_always,
            never=current_never,
        ))

    return heuristics
