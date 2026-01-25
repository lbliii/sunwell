"""Expertise Context for Planning (RFC-039).

Data structures for holding extracted expertise that gets injected
into artifact planning prompts.

Example:
    >>> context = ExpertiseContext(
    ...     heuristics=[
    ...         HeuristicSummary(name="Progressive Disclosure", ...),
    ...         HeuristicSummary(name="Signal-to-Noise", ...),
    ...     ],
    ...     domain="documentation",
    ...     source_lenses=["tech-writer.lens"],
    ... )
    >>>
    >>> # Inject into planning prompt
    >>> prompt = f"{base_prompt}\\n\\n{context.to_prompt_section()}"
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.models.heuristic import Heuristic
    from sunwell.core.models.validator import Validator


@dataclass(frozen=True, slots=True)
class HeuristicSummary:
    """Summarized heuristic for prompt injection.

    A lightweight representation of a heuristic that's optimized
    for including in prompts without the full heuristic object.
    """

    name: str
    rule: str  # The core rule/principle
    always: tuple[str, ...]  # Key "always" patterns (top 3)
    never: tuple[str, ...]  # Key "never" patterns (top 3)
    relevance: float = 1.0  # How relevant to the current goal (0-1)

    @classmethod
    def from_heuristic(
        cls,
        heuristic: Heuristic,
        relevance: float = 1.0,
        max_patterns: int = 3,
    ) -> HeuristicSummary:
        """Create summary from full Heuristic object.

        Args:
            heuristic: Full heuristic object
            relevance: Relevance score (0-1)
            max_patterns: Max always/never patterns to include
        """
        return cls(
            name=heuristic.name,
            rule=heuristic.rule,
            always=tuple(heuristic.always[:max_patterns]) if heuristic.always else (),
            never=tuple(heuristic.never[:max_patterns]) if heuristic.never else (),
            relevance=relevance,
        )

    def to_markdown(self) -> str:
        """Format as markdown for prompt injection."""
        parts = [f"### {self.name}\n"]

        if self.rule:
            parts.append(f"**Rule**: {self.rule}\n")

        if self.always:
            parts.append("**Always**:")
            for pattern in self.always:
                parts.append(f"- ✅ {pattern}")
            parts.append("")

        if self.never:
            parts.append("**Never**:")
            for pattern in self.never:
                parts.append(f"- ❌ {pattern}")
            parts.append("")

        return "\n".join(parts)


@dataclass(slots=True)
class ExpertiseContext:
    """Container for extracted expertise to inject into planning.

    Holds heuristics, validators, and domain context that should
    inform artifact planning and generation.

    Attributes:
        heuristics: Relevant heuristic summaries
        validators: Applicable validators for output checking
        domain: Detected domain name
        domain_context: Markdown summary of domain expertise
        source_lenses: Names of lenses that contributed expertise
    """

    heuristics: tuple[HeuristicSummary, ...] = ()
    validators: tuple[Validator, ...] = ()
    domain: str = "general"
    domain_context: str = ""
    source_lenses: tuple[str, ...] = ()

    @property
    def has_expertise(self) -> bool:
        """Whether any expertise was extracted."""
        return bool(self.heuristics) or bool(self.validators)

    @property
    def heuristic_count(self) -> int:
        """Number of heuristics available."""
        return len(self.heuristics)

    def to_prompt_section(self, max_heuristics: int = 5) -> str:
        """Format expertise as prompt section for injection.

        Args:
            max_heuristics: Maximum heuristics to include

        Returns:
            Markdown-formatted expertise section
        """
        if not self.has_expertise:
            return ""

        parts = ["## Domain Expertise\n"]

        # Domain context (if provided)
        if self.domain_context:
            parts.append(self.domain_context)
            parts.append("")

        # Heuristics
        if self.heuristics:
            parts.append("### Key Principles\n")

            # Sort by relevance, take top N
            sorted_heuristics = sorted(
                self.heuristics,
                key=lambda h: h.relevance,
                reverse=True,
            )[:max_heuristics]

            for h in sorted_heuristics:
                parts.append(h.to_markdown())

        # Source attribution
        if self.source_lenses:
            parts.append("---")
            parts.append(f"*Expertise from: {', '.join(self.source_lenses)}*")

        return "\n".join(parts)

    def to_compact_prompt(self) -> str:
        """Format as compact prompt for token-constrained contexts.

        Returns a more condensed version suitable for smaller context windows.
        """
        if not self.has_expertise:
            return ""

        parts = [f"## {self.domain.title()} Best Practices\n"]

        for h in self.heuristics[:3]:  # Top 3 only
            parts.append(f"**{h.name}**: {h.rule}")

            # Combine always/never into single line
            patterns = []
            if h.always:
                patterns.append("DO: " + "; ".join(h.always[:2]))
            if h.never:
                patterns.append("DON'T: " + "; ".join(h.never[:2]))

            if patterns:
                parts.append("  " + " | ".join(patterns))
            parts.append("")

        return "\n".join(parts)

    def merge(self, other: ExpertiseContext) -> ExpertiseContext:
        """Merge with another expertise context.

        Useful for multi-domain goals that need expertise from
        multiple sources.

        Args:
            other: Another ExpertiseContext to merge

        Returns:
            New ExpertiseContext with combined expertise
        """
        # Deduplicate heuristics by name
        seen_names = {h.name for h in self.heuristics}
        merged_heuristics = list(self.heuristics)

        for h in other.heuristics:
            if h.name not in seen_names:
                merged_heuristics.append(h)
                seen_names.add(h.name)

        # Combine validators (dedupe by name if available)
        merged_validators = list(self.validators)
        validator_names = {getattr(v, 'name', str(i)) for i, v in enumerate(self.validators)}

        for v in other.validators:
            v_name = getattr(v, 'name', None)
            if v_name and v_name not in validator_names:
                merged_validators.append(v)
                validator_names.add(v_name)
            elif not v_name:
                merged_validators.append(v)

        # Combine source lenses
        merged_sources = list(dict.fromkeys(list(self.source_lenses) + list(other.source_lenses)))

        # Domain: prefer more specific (non-general)
        domain = self.domain if self.domain != "general" else other.domain

        # Combine domain context
        domain_context = "\n\n".join(filter(None, [self.domain_context, other.domain_context]))

        return ExpertiseContext(
            heuristics=tuple(merged_heuristics),
            validators=tuple(merged_validators),
            domain=domain,
            domain_context=domain_context,
            source_lenses=tuple(merged_sources),
        )


# Convenience factory for empty context
def empty_context() -> ExpertiseContext:
    """Create an empty expertise context (no expertise loaded)."""
    return ExpertiseContext()
