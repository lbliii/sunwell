"""Context injection for prompts."""

from __future__ import annotations

from dataclasses import dataclass

from sunwell.core.lens import Lens


@dataclass
class ContextInjector:
    """Builds context from lens components for injection into prompts."""

    def build_context(
        self,
        lens: Lens,
        retrieved_components: tuple[str, ...] | None = None,
    ) -> str:
        """Build context injection from lens and retrieved components.

        Args:
            lens: The lens to build context from
            retrieved_components: Names of retrieved heuristics to include.
                                  If None, includes all heuristics.

        Returns:
            Formatted context string for prompt injection.
        """
        sections = []

        # Header
        sections.append(f"# Expertise: {lens.metadata.name}")
        if lens.metadata.description:
            sections.append(lens.metadata.description)

        # Filter heuristics based on retrieval
        heuristics = lens.heuristics
        if retrieved_components:
            heuristics = tuple(
                h for h in heuristics if h.name in retrieved_components
            )

        # Add heuristics
        if heuristics:
            sections.append("\n## Professional Heuristics\n")
            sections.append(
                "Apply these thinking patterns when completing the task:\n"
            )
            for h in heuristics:
                sections.append(h.to_prompt_fragment())
                sections.append("")

        # Add anti-heuristics (always include - they're warnings)
        if lens.anti_heuristics:
            sections.append("\n## Anti-Patterns to Avoid\n")
            for ah in lens.anti_heuristics:
                sections.append(ah.to_prompt_fragment())
                sections.append("")

        # Add communication style
        if lens.communication:
            sections.append("\n## Communication Style\n")
            sections.append(lens.communication.to_prompt_fragment())

        # Add framework
        if lens.framework:
            sections.append("\n" + lens.framework.to_prompt_fragment())

        return "\n".join(sections)

    def build_validation_context(
        self,
        lens: Lens,
        content: str,
    ) -> str:
        """Build context for validation prompts."""
        sections = [
            "# Validation Task",
            "",
            "Validate the following content against the lens criteria.",
            "",
            "## Lens Criteria",
            "",
        ]

        # Add heuristics as validation criteria
        for h in lens.heuristics:
            sections.append(f"- **{h.name}**: {h.rule}")

        sections.append("")
        sections.append("## Content to Validate")
        sections.append("")
        sections.append("```")
        sections.append(content)
        sections.append("```")

        return "\n".join(sections)

    def build_persona_context(
        self,
        lens: Lens,
        content: str,
        persona_name: str,
    ) -> str:
        """Build context for persona evaluation."""
        persona = lens.get_persona(persona_name)
        if not persona:
            raise ValueError(f"Unknown persona: {persona_name}")

        return persona.to_evaluation_prompt(content)
