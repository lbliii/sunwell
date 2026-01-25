"""Tool expertise enhancement for the agentic tool loop."""

import logging
from typing import TYPE_CHECKING

from sunwell.models import Tool

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens

logger = logging.getLogger(__name__)


def enhance_tools_with_expertise(
    tools: tuple[Tool, ...],
    lens: Lens | None,
    enable_expertise_injection: bool = True,
) -> tuple[Tool, ...]:
    """Enhance tool descriptions with lens-specific heuristics (Sunwell differentiator).

    Dynamically injects domain expertise into tool descriptions so the model
    knows HOW to use tools correctly for this domain. Competitors use static
    tool descriptions - Sunwell's tools are context-aware.

    Example:
        write_file for Python lens gets:
        "When writing Python files: always include type hints, use snake_case,
         add docstrings to public functions. AVOID: global state, print debugging."

    Args:
        tools: Original tool definitions
        lens: Lens to extract heuristics from
        enable_expertise_injection: Whether to enable enhancement

    Returns:
        Enhanced tool definitions with lens-specific guidance
    """
    if not lens or not enable_expertise_injection:
        return tools

    try:
        # Extract heuristics from lens
        heuristics: list[str] = []
        anti_heuristics: list[str] = []

        # Get heuristics (do's)
        if hasattr(lens, "heuristics"):
            for h in lens.heuristics[:5]:  # Limit to top 5
                if hasattr(h, "name") and hasattr(h, "description"):
                    heuristics.append(f"{h.name}: {h.description}")
                elif hasattr(h, "content"):
                    heuristics.append(str(h.content)[:100])
                else:
                    heuristics.append(str(h)[:100])

        # Get anti-heuristics (don'ts)
        if hasattr(lens, "anti_heuristics"):
            for ah in lens.anti_heuristics[:3]:  # Limit to top 3
                if hasattr(ah, "pattern"):
                    anti_heuristics.append(f"AVOID: {ah.pattern}")
                else:
                    anti_heuristics.append(f"AVOID: {str(ah)[:80]}")

        if not heuristics and not anti_heuristics:
            return tools

        # Build expertise suffix for file-writing tools
        expertise_suffix = ""
        if heuristics:
            expertise_suffix += " BEST PRACTICES: " + "; ".join(heuristics[:3])
        if anti_heuristics:
            expertise_suffix += " " + "; ".join(anti_heuristics[:2])

        # Enhance write_file and edit_file descriptions
        enhanced: list[Tool] = []
        for tool in tools:
            if tool.name in ("write_file", "edit_file"):
                # Create enhanced copy
                enhanced.append(Tool(
                    name=tool.name,
                    description=tool.description + expertise_suffix,
                    parameters=tool.parameters,
                ))
            else:
                enhanced.append(tool)

        lens_name = "unknown"
        if hasattr(lens, "metadata") and hasattr(lens.metadata, "name"):
            lens_name = lens.metadata.name
        logger.info(
            "⚙ EXPERTISE INJECTION → Enhanced tools with %d heuristics [%s]",
            len(heuristics),
            lens_name,
            extra={
                "lens": lens_name,
                "heuristics_count": len(heuristics),
                "anti_heuristics_count": len(anti_heuristics),
            },
        )

        return tuple(enhanced)

    except Exception as e:
        logger.warning("Failed to enhance tools with expertise: %s", e)
        return tools
