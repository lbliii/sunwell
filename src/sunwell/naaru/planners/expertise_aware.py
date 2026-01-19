"""Expertise-Aware Artifact Planner (RFC-039).

Extends ArtifactPlanner with automatic domain detection and expertise injection.
The planner discovers relevant lenses based on the goal and injects heuristics
into artifact planning prompts.

Example:
    >>> planner = ExpertiseAwareArtifactPlanner(model=my_model)
    >>> graph = await planner.discover_graph("Write docs for the CLI module")
    >>> # Artifacts are informed by tech-writer heuristics (Diataxis, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactLimits, DEFAULT_LIMITS
from sunwell.naaru.planners.artifact import ArtifactPlanner

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.expertise.context import ExpertiseContext
    from sunwell.naaru.expertise.classifier import DomainClassifier
    from sunwell.naaru.expertise.discovery import LensDiscovery
    from sunwell.naaru.expertise.extractor import ExpertiseExtractor


@dataclass
class ExpertiseAwareArtifactPlanner(ArtifactPlanner):
    """Artifact planner with automatic expertise injection (RFC-039).
    
    Extends ArtifactPlanner to:
    1. Auto-detect the domain of the goal
    2. Discover and load relevant lenses
    3. Extract applicable heuristics
    4. Inject expertise into discovery prompts
    
    The result is higher-quality artifacts that follow domain best practices.
    
    Example:
        >>> planner = ExpertiseAwareArtifactPlanner(
        ...     model=my_model,
        ...     enable_expertise=True,  # Default
        ... )
        >>> 
        >>> # For documentation goals:
        >>> graph = await planner.discover_graph("Write docs for the CLI")
        >>> # → Artifacts follow Diataxis, progressive disclosure, etc.
        >>> 
        >>> # Explicit disable:
        >>> planner.enable_expertise = False
        >>> graph = await planner.discover_graph("Write docs")
        >>> # → Baseline behavior (no expertise injection)
    """
    
    # Expertise components (lazy-initialized)
    domain_classifier: "DomainClassifier | None" = None
    lens_discovery: "LensDiscovery | None" = None
    
    # Settings
    enable_expertise: bool = True
    min_confidence: float = 0.3  # Minimum domain confidence to load expertise
    max_heuristics: int = 5  # Max heuristics to inject
    
    # State (set during planning)
    _current_expertise: "ExpertiseContext | None" = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        """Initialize expertise components lazily."""
        pass  # Components are created on first use
    
    def _ensure_classifier(self) -> "DomainClassifier":
        """Ensure domain classifier is initialized."""
        if self.domain_classifier is None:
            from sunwell.naaru.expertise.classifier import DomainClassifier
            self.domain_classifier = DomainClassifier()
        return self.domain_classifier
    
    def _ensure_discovery(self) -> "LensDiscovery":
        """Ensure lens discovery is initialized."""
        if self.lens_discovery is None:
            from sunwell.naaru.expertise.discovery import LensDiscovery
            self.lens_discovery = LensDiscovery()
        return self.lens_discovery
    
    async def discover_graph(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ArtifactGraph:
        """Discover artifacts with expertise awareness.
        
        Extends parent to:
        1. Classify goal domain
        2. Load relevant lenses if confidence is high
        3. Extract expertise
        4. Pass to parent with expertise context
        
        Args:
            goal: The goal to achieve
            context: Optional context
            
        Returns:
            ArtifactGraph ready for execution
        """
        # Load expertise if enabled
        if self.enable_expertise:
            self._current_expertise = await self._load_expertise(goal)
        else:
            self._current_expertise = None
        
        # Call parent implementation (which will use our overridden prompt builder)
        return await super().discover_graph(goal, context)
    
    async def _load_expertise(self, goal: str) -> "ExpertiseContext | None":
        """Load expertise for a goal.
        
        1. Classify domain
        2. If confident, discover lenses
        3. Extract relevant heuristics
        
        Returns ExpertiseContext or None if no expertise loaded.
        """
        from sunwell.naaru.expertise.context import ExpertiseContext
        from sunwell.naaru.expertise.extractor import ExpertiseExtractor
        
        # Classify domain
        classifier = self._ensure_classifier()
        classification = classifier.classify(goal)
        
        # Skip if not confident
        if classification.confidence < self.min_confidence:
            return None
        
        # Discover lenses for domain
        discovery = self._ensure_discovery()
        lenses = await discovery.discover(classification.domain)
        
        if not lenses:
            return None
        
        # Extract expertise
        extractor = ExpertiseExtractor(
            lenses=lenses,
            max_heuristics=self.max_heuristics,
        )
        
        return await extractor.extract(goal)
    
    def _build_discovery_prompt(
        self,
        goal: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Build discovery prompt with expertise injection.
        
        Extends parent prompt with expertise section if available.
        """
        # Get base prompt from parent
        base_prompt = super()._build_discovery_prompt(goal, context)
        
        # Inject expertise if available
        if self._current_expertise and self._current_expertise.has_expertise:
            expertise_section = self._build_expertise_section()
            
            # Insert expertise before the discovery principles
            insert_marker = "=== DISCOVERY PRINCIPLES ==="
            if insert_marker in base_prompt:
                base_prompt = base_prompt.replace(
                    insert_marker,
                    f"{expertise_section}\n\n{insert_marker}",
                )
            else:
                # Fallback: append after context
                context_end = base_prompt.find("=== ARTIFACT DISCOVERY ===")
                if context_end > 0:
                    base_prompt = (
                        base_prompt[:context_end] +
                        f"{expertise_section}\n\n" +
                        base_prompt[context_end:]
                    )
        
        return base_prompt
    
    def _build_expertise_section(self) -> str:
        """Build expertise section for prompt injection."""
        if not self._current_expertise:
            return ""
        
        ctx = self._current_expertise
        
        lines = [
            f"=== DOMAIN EXPERTISE ({ctx.domain.upper()}) ===",
            "",
            "Apply these principles when discovering artifacts:",
            "",
        ]
        
        for h in ctx.heuristics:
            lines.append(f"**{h.name}**")
            if h.rule:
                lines.append(f"  {h.rule}")
            
            if h.always:
                lines.append("  DO:")
                for pattern in h.always[:2]:  # Top 2
                    lines.append(f"    - {pattern}")
            
            if h.never:
                lines.append("  DON'T:")
                for pattern in h.never[:2]:  # Top 2
                    lines.append(f"    - {pattern}")
            
            lines.append("")
        
        if ctx.source_lenses:
            lines.append(f"(Expertise from: {', '.join(ctx.source_lenses)})")
        
        return "\n".join(lines)
    
    def get_expertise_summary(self) -> dict[str, Any]:
        """Get summary of loaded expertise for debugging/logging.
        
        Returns dict with domain, confidence, heuristic count, etc.
        """
        if not self._current_expertise:
            return {
                "enabled": self.enable_expertise,
                "loaded": False,
            }
        
        ctx = self._current_expertise
        return {
            "enabled": self.enable_expertise,
            "loaded": True,
            "domain": ctx.domain,
            "heuristic_count": len(ctx.heuristics),
            "heuristics": [h.name for h in ctx.heuristics],
            "validator_count": len(ctx.validators),
            "source_lenses": ctx.source_lenses,
        }


# Convenience factory
def create_expertise_aware_planner(
    model: "ModelProtocol",
    enable_expertise: bool = True,
    limits: ArtifactLimits | None = None,
) -> ExpertiseAwareArtifactPlanner:
    """Create an expertise-aware artifact planner.
    
    Factory function for creating planners with default settings.
    
    Args:
        model: The LLM for planning
        enable_expertise: Whether to enable expertise injection
        limits: Optional artifact limits
        
    Returns:
        Configured ExpertiseAwareArtifactPlanner
    """
    return ExpertiseAwareArtifactPlanner(
        model=model,
        limits=limits or DEFAULT_LIMITS,
        enable_expertise=enable_expertise,
    )
