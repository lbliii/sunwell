"""Surface Composer (RFC-072 prep for RFC-075).

The main entry point for surface composition. Takes a goal and produces
a WorkspaceSpec that can be rendered by the SurfaceRenderer.

RFC-075 (Generative Interface) will extend this with:
- LLM-based intent analysis
- Context-aware primitive selection
- User preference learning
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sunwell.core.lens import Affordances
from sunwell.surface.fallback import get_domain_for_project
from sunwell.surface.intent import IntentSignals, extract_intent
from sunwell.surface.registry import PrimitiveRegistry
from sunwell.surface.scoring import ScoringContext, score_primitives, select_primitives
from sunwell.surface.types import SurfaceArrangement, WorkspaceSpec

if TYPE_CHECKING:
    from sunwell.core.lens import Lens

# Module-level constants (avoid per-call dict/set rebuilds)
_DOMAIN_DEFAULT_PRIMARY: dict[str, str] = {
    "code": "CodeEditor",
    "planning": "Kanban",
    "writing": "ProseEditor",
    "data": "DataTable",
    "universal": "CodeEditor",
}

_VALID_ARRANGEMENTS: frozenset[SurfaceArrangement] = frozenset({
    "standard", "focused", "split", "dashboard"
})


@dataclass(frozen=True, slots=True)
class CompositionResult:
    """Result of surface composition."""

    spec: WorkspaceSpec
    """The composed workspace specification."""

    intent: IntentSignals
    """Extracted intent signals."""

    confidence: float
    """Confidence in composition (0.0-1.0)."""

    reasoning: MappingProxyType[str, Any]
    """Explanation of composition decisions (immutable mapping)."""


class SurfaceComposer:
    """Composes surface layouts from goals.

    The composer takes a user's goal and produces a WorkspaceSpec
    by analyzing intent, scoring primitives, and selecting the
    best combination for the task.

    This is the main integration point for RFC-075 (Generative Interface).
    """

    def __init__(
        self,
        registry: PrimitiveRegistry | None = None,
    ) -> None:
        """Initialize composer.

        Args:
            registry: Primitive registry (defaults to PrimitiveRegistry.default())
        """
        self.registry = registry or PrimitiveRegistry.default()

    def compose(
        self,
        goal: str,
        project_path: Path | None = None,
        lens: Lens | None = None,
        memory_patterns: dict[str, float] | None = None,
    ) -> CompositionResult:
        """Compose a surface layout for a goal.

        Args:
            goal: User's goal string
            project_path: Project path for domain inference
            lens: Active lens for affordances
            memory_patterns: Historical primitive success rates

        Returns:
            Composition result with spec and reasoning
        """
        # 1. Extract intent from goal
        intent = extract_intent(goal)

        # 2. Build scoring context
        affordances = lens.affordances if lens else None
        project_domain = (
            get_domain_for_project(project_path)
            if project_path
            else intent.primary_domain
        )

        context = ScoringContext(
            intent=intent,
            affordances=affordances,
            project_domain=project_domain,
            memory_patterns=memory_patterns or {},
        )

        # 3. Score all primitives
        scoring_result = score_primitives(goal, self.registry, context)

        # 4. Select primitives
        primary_scored, secondary_scored, contextual_scored = select_primitives(
            scoring_result,
            max_secondary=3,
            max_contextual=2,
            min_score=0.1,
        )

        # 5. Build WorkspaceSpec
        if primary_scored:
            primary = primary_scored.primitive_id
            primary_size = primary_scored.suggested_size
        else:
            # Fallback to domain default
            primary = self._get_domain_default_primary(intent.primary_domain)
            primary_size = "full"

        secondary = tuple(s.primitive_id for s in secondary_scored)
        contextual = tuple(s.primitive_id for s in contextual_scored)

        # Validate arrangement
        arrangement = self._validate_arrangement(intent.suggested_arrangement)

        spec = WorkspaceSpec(
            primary=primary,
            secondary=secondary,
            contextual=contextual,
            arrangement=arrangement,
            primary_props={"suggested_size": primary_size},
        )

        # 6. Calculate confidence
        confidence = self._calculate_confidence(
            intent=intent,
            primary_scored=primary_scored,
            secondary_scored=secondary_scored,
        )

        # 7. Build reasoning
        reasoning = self._build_reasoning(
            intent=intent,
            primary_scored=primary_scored,
            secondary_scored=secondary_scored,
            contextual_scored=contextual_scored,
            context=context,
        )

        return CompositionResult(
            spec=spec,
            intent=intent,
            confidence=confidence,
            reasoning=reasoning,
        )

    def compose_with_affordances(
        self,
        goal: str,
        affordances: Affordances,
        project_path: Path | None = None,
        memory_patterns: dict[str, float] | None = None,
    ) -> CompositionResult:
        """Compose using explicit affordances (without full lens).

        Useful when affordances are loaded separately from the lens.

        Args:
            goal: User's goal string
            affordances: Explicit affordances to use
            project_path: Project path for domain inference
            memory_patterns: Historical primitive success rates

        Returns:
            Composition result
        """
        # Build a minimal context with affordances
        intent = extract_intent(goal)

        project_domain = (
            get_domain_for_project(project_path)
            if project_path
            else intent.primary_domain
        )

        context = ScoringContext(
            intent=intent,
            affordances=affordances,
            project_domain=project_domain,
            memory_patterns=memory_patterns or {},
        )

        # Score and select
        scoring_result = score_primitives(goal, self.registry, context)
        primary_scored, secondary_scored, contextual_scored = select_primitives(
            scoring_result
        )

        # Build spec
        primary = (
            primary_scored.primitive_id
            if primary_scored
            else self._get_domain_default_primary(intent.primary_domain)
        )

        spec = WorkspaceSpec(
            primary=primary,
            secondary=tuple(s.primitive_id for s in secondary_scored),
            contextual=tuple(s.primitive_id for s in contextual_scored),
            arrangement=self._validate_arrangement(intent.suggested_arrangement),
        )

        confidence = self._calculate_confidence(intent, primary_scored, secondary_scored)

        return CompositionResult(
            spec=spec,
            intent=intent,
            confidence=confidence,
            reasoning=MappingProxyType({"source": "affordances"}),
        )

    def compose_minimal(self, goal: str) -> WorkspaceSpec:
        """Compose with minimal processing (no lens, no memory).

        Fast path for simple composition without full context.

        Args:
            goal: User's goal string

        Returns:
            Composed workspace spec
        """
        result = self.compose(goal)
        return result.spec

    def _get_domain_default_primary(self, domain: str) -> str:
        """Get default primary primitive for a domain."""
        return _DOMAIN_DEFAULT_PRIMARY.get(domain, "CodeEditor")

    def _validate_arrangement(self, arrangement: str) -> SurfaceArrangement:
        """Validate and return a valid arrangement."""
        if arrangement in _VALID_ARRANGEMENTS:
            return arrangement  # type: ignore[return-value]
        return "standard"

    def _calculate_confidence(
        self,
        intent: IntentSignals,
        primary_scored: Any,
        secondary_scored: tuple[Any, ...],
    ) -> float:
        """Calculate overall composition confidence."""
        # Start with intent confidence
        confidence = intent.confidence * 0.4

        # Add primary selection confidence
        if primary_scored and primary_scored.score > 0.3:
            confidence += 0.3
        elif primary_scored:
            confidence += primary_scored.score * 0.3

        # Add secondary selection confidence
        if secondary_scored:
            avg_secondary_score = sum(s.score for s in secondary_scored) / len(
                secondary_scored
            )
            confidence += avg_secondary_score * 0.2

        # Base confidence from having any result
        confidence += 0.1

        return min(0.95, confidence)  # Cap at 0.95 for heuristic-only

    def _build_reasoning(
        self,
        intent: IntentSignals,
        primary_scored: Any,
        secondary_scored: tuple[Any, ...],
        contextual_scored: tuple[Any, ...],
        context: ScoringContext,
    ) -> MappingProxyType[str, Any]:
        """Build explanation of composition decisions."""
        return MappingProxyType({
            "intent": {
                "primary_domain": intent.primary_domain,
                "domain_scores": intent.domain_scores,
                "triggered_primitives": intent.triggered_primitives,
                "confidence": intent.confidence,
            },
            "selection": {
                "primary": {
                    "id": primary_scored.primitive_id if primary_scored else None,
                    "score": primary_scored.score if primary_scored else 0,
                    "reasons": primary_scored.reasons if primary_scored else [],
                },
                "secondary": [
                    {"id": s.primitive_id, "score": s.score, "reasons": s.reasons}
                    for s in secondary_scored
                ],
                "contextual": [
                    {"id": s.primitive_id, "score": s.score, "reasons": s.reasons}
                    for s in contextual_scored
                ],
            },
            "context": {
                "has_affordances": context.affordances is not None,
                "project_domain": context.project_domain,
                "memory_patterns_count": len(context.memory_patterns),
            },
        })


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def compose_surface(
    goal: str,
    project_path: Path | None = None,
    lens: Lens | None = None,
) -> WorkspaceSpec:
    """Convenience function to compose a surface.

    Args:
        goal: User's goal string
        project_path: Project path for domain inference
        lens: Active lens for affordances

    Returns:
        Composed workspace spec
    """
    composer = SurfaceComposer()
    result = composer.compose(goal, project_path, lens)
    return result.spec


def compose_surface_with_reasoning(
    goal: str,
    project_path: Path | None = None,
    lens: Lens | None = None,
) -> CompositionResult:
    """Compose surface with full reasoning information.

    Args:
        goal: User's goal string
        project_path: Project path for domain inference
        lens: Active lens for affordances

    Returns:
        Full composition result with reasoning
    """
    composer = SurfaceComposer()
    return composer.compose(goal, project_path, lens)
