# src/sunwell/simulacrum/facets.py
"""Multi-faceted memory - cross-dimensional tagging for retrieval.

Enables queries across multiple axes simultaneously:
- "Tutorial content for novices" (diataxis + persona)
- "Unverified reference content" (verification + diataxis)
- "High-confidence CLI documentation" (confidence + domain)

Part of RFC-014: Multi-Topology Memory.
"""


from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiataxisType(Enum):
    """Diataxis documentation types."""
    TUTORIAL = "tutorial"
    HOWTO = "howto"
    REFERENCE = "reference"
    EXPLANATION = "explanation"


class PersonaType(Enum):
    """Target audience personas."""
    NOVICE = "novice"           # New to the tool
    PRAGMATIST = "pragmatist"   # Just wants code
    SKEPTIC = "skeptic"         # Needs convincing
    EXPERT = "expert"           # Advanced user


class VerificationState(Enum):
    """Verification status of content."""
    UNVERIFIED = "unverified"   # Not yet checked
    VERIFIED = "verified"       # Confirmed accurate
    DISPUTED = "disputed"       # Known issues
    OUTDATED = "outdated"       # Needs update


class ConfidenceLevel(Enum):
    """Confidence in the content."""
    HIGH = "high"         # 90-100%
    MODERATE = "moderate" # 70-89%
    LOW = "low"           # 50-69%
    UNCERTAIN = "uncertain"  # <50%


@dataclass(frozen=True, slots=True)
class ContentFacets:
    """Multi-dimensional tags for cross-axis retrieval.

    Enables queries like:
    - "Tutorial content for novices" (diataxis + persona)
    - "Unverified reference content" (verification + diataxis)
    - "High-confidence CLI documentation" (confidence + domain)
    """

    # Diataxis
    diataxis_type: DiataxisType | None = None
    """Content type per Diataxis framework."""

    # Audience
    primary_persona: PersonaType | None = None
    """Primary target audience."""

    secondary_personas: tuple[PersonaType, ...] = ()
    """Additional relevant audiences."""

    # Trust
    verification_state: VerificationState = VerificationState.UNVERIFIED
    """Verification status."""

    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    """Confidence in accuracy."""

    # Domain
    domain_tags: tuple[str, ...] = ()
    """Domain/topic tags: ("cli", "api", "config", "security")."""

    # Temporal
    is_time_sensitive: bool = False
    """Content may become outdated."""

    last_verified: str | None = None
    """ISO timestamp of last verification."""

    # Source
    source_type: str | None = None
    """Where this came from: "code", "docs", "conversation", "external"."""

    source_authority: float = 1.0
    """Authority of source (0.0-1.0). Code = 1.0, docs = 0.9, user = 0.7."""

    def matches(self, query: FacetQuery) -> float:
        """Score how well facets match a query.

        Returns 0.0 (no match) to 1.0 (perfect match).
        """
        if not query.has_constraints():
            return 1.0

        score = 0.0
        checks = 0

        # Diataxis match
        if query.diataxis_type is not None:
            checks += 1
            if self.diataxis_type == query.diataxis_type:
                score += 1.0

        # Persona match
        if query.persona is not None:
            checks += 1
            if self.primary_persona == query.persona:
                score += 1.0
            elif query.persona in self.secondary_personas:
                score += 0.7

        # Verification match
        if query.verification_states:
            checks += 1
            if self.verification_state in query.verification_states:
                score += 1.0

        # Confidence match
        if query.min_confidence is not None:
            checks += 1
            confidence_order = [
                ConfidenceLevel.UNCERTAIN,
                ConfidenceLevel.LOW,
                ConfidenceLevel.MODERATE,
                ConfidenceLevel.HIGH,
            ]
            if confidence_order.index(self.confidence) >= confidence_order.index(query.min_confidence):
                score += 1.0

        # Domain match
        if query.domain_tags:
            checks += 1
            overlap = len(set(self.domain_tags) & set(query.domain_tags))
            if overlap > 0:
                score += overlap / len(query.domain_tags)

        return score / checks if checks > 0 else 1.0


@dataclass
class FacetQuery:
    """Query for multi-faceted retrieval."""

    # Diataxis filter
    diataxis_type: DiataxisType | None = None

    # Persona filter
    persona: PersonaType | None = None

    # Verification filter
    verification_states: tuple[VerificationState, ...] = ()

    # Confidence filter
    min_confidence: ConfidenceLevel | None = None

    # Domain filter
    domain_tags: tuple[str, ...] = ()
    """All tags must match (AND logic)."""

    # Source filter
    source_types: tuple[str, ...] = ()

    def has_constraints(self) -> bool:
        """Check if query has any constraints."""
        return any([
            self.diataxis_type,
            self.persona,
            self.verification_states,
            self.min_confidence,
            self.domain_tags,
            self.source_types,
        ])


@dataclass
class FacetedIndex:
    """Index for efficient multi-faceted retrieval.

    Maintains inverted indexes for each facet dimension.
    """

    # Inverted indexes: facet_value -> set of node IDs
    _by_diataxis: dict[DiataxisType, set[str]] = field(default_factory=dict)
    _by_persona: dict[PersonaType, set[str]] = field(default_factory=dict)
    _by_verification: dict[VerificationState, set[str]] = field(default_factory=dict)
    _by_confidence: dict[ConfidenceLevel, set[str]] = field(default_factory=dict)
    _by_domain: dict[str, set[str]] = field(default_factory=dict)

    # Forward index: node ID -> facets
    _facets: dict[str, ContentFacets] = field(default_factory=dict)

    def add(self, node_id: str, facets: ContentFacets) -> None:
        """Add node to index."""
        self._facets[node_id] = facets

        # Update inverted indexes
        if facets.diataxis_type:
            if facets.diataxis_type not in self._by_diataxis:
                self._by_diataxis[facets.diataxis_type] = set()
            self._by_diataxis[facets.diataxis_type].add(node_id)

        if facets.primary_persona:
            if facets.primary_persona not in self._by_persona:
                self._by_persona[facets.primary_persona] = set()
            self._by_persona[facets.primary_persona].add(node_id)

        for persona in facets.secondary_personas:
            if persona not in self._by_persona:
                self._by_persona[persona] = set()
            self._by_persona[persona].add(node_id)

        if facets.verification_state not in self._by_verification:
            self._by_verification[facets.verification_state] = set()
        self._by_verification[facets.verification_state].add(node_id)

        if facets.confidence not in self._by_confidence:
            self._by_confidence[facets.confidence] = set()
        self._by_confidence[facets.confidence].add(node_id)

        for tag in facets.domain_tags:
            if tag not in self._by_domain:
                self._by_domain[tag] = set()
            self._by_domain[tag].add(node_id)

    def remove(self, node_id: str) -> None:
        """Remove node from index."""
        facets = self._facets.pop(node_id, None)
        if not facets:
            return

        # Remove from inverted indexes
        if facets.diataxis_type and facets.diataxis_type in self._by_diataxis:
            self._by_diataxis[facets.diataxis_type].discard(node_id)

        if facets.primary_persona and facets.primary_persona in self._by_persona:
            self._by_persona[facets.primary_persona].discard(node_id)

        for persona in facets.secondary_personas:
            if persona in self._by_persona:
                self._by_persona[persona].discard(node_id)

        if facets.verification_state in self._by_verification:
            self._by_verification[facets.verification_state].discard(node_id)

        if facets.confidence in self._by_confidence:
            self._by_confidence[facets.confidence].discard(node_id)

        for tag in facets.domain_tags:
            if tag in self._by_domain:
                self._by_domain[tag].discard(node_id)

    def query(self, query: FacetQuery) -> list[tuple[str, float]]:
        """Query index, returning (node_id, score) pairs.

        Uses inverted indexes for efficient filtering,
        then scores remaining candidates.
        """
        # Start with all nodes
        candidates: set[str] | None = None

        # Filter by diataxis
        if query.diataxis_type:
            matching = self._by_diataxis.get(query.diataxis_type, set())
            candidates = matching if candidates is None else candidates & matching

        # Filter by persona
        if query.persona:
            matching = self._by_persona.get(query.persona, set())
            candidates = matching if candidates is None else candidates & matching

        # Filter by verification
        if query.verification_states:
            matching = set()
            for state in query.verification_states:
                matching |= self._by_verification.get(state, set())
            candidates = matching if candidates is None else candidates & matching

        # Filter by confidence
        if query.min_confidence:
            confidence_order = [
                ConfidenceLevel.UNCERTAIN,
                ConfidenceLevel.LOW,
                ConfidenceLevel.MODERATE,
                ConfidenceLevel.HIGH,
            ]
            min_idx = confidence_order.index(query.min_confidence)
            matching = set()
            for level in confidence_order[min_idx:]:
                matching |= self._by_confidence.get(level, set())
            candidates = matching if candidates is None else candidates & matching

        # Filter by domain (AND logic)
        if query.domain_tags:
            matching = None
            for tag in query.domain_tags:
                tag_nodes = self._by_domain.get(tag, set())
                matching = tag_nodes if matching is None else matching & tag_nodes
            if matching:
                candidates = matching if candidates is None else candidates & matching
            else:
                candidates = set()

        # If no filters, return all
        if candidates is None:
            candidates = set(self._facets.keys())

        # Score candidates
        results = []
        for node_id in candidates:
            facets = self._facets.get(node_id)
            if facets:
                score = facets.matches(query)
                if score > 0:
                    results.append((node_id, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def get_facets(self, node_id: str) -> ContentFacets | None:
        """Get facets for a node."""
        return self._facets.get(node_id)

    def stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_nodes": len(self._facets),
            "by_diataxis": {k.value: len(v) for k, v in self._by_diataxis.items()},
            "by_persona": {k.value: len(v) for k, v in self._by_persona.items()},
            "by_verification": {k.value: len(v) for k, v in self._by_verification.items()},
            "by_confidence": {k.value: len(v) for k, v in self._by_confidence.items()},
            "domain_tags": {k: len(v) for k, v in self._by_domain.items()},
        }
