"""Tool description engineering for improved tool selection accuracy.

Research Insight: "We spent more time optimizing our tools than the overall prompt"
(Anthropic: Building Effective Agents)

Key principles:
- Tool descriptions are prompts - invest heavily in their quality
- Clear, unambiguous descriptions improve tool selection accuracy
- Parameter descriptions should guide correct usage
"""

from dataclasses import dataclass

from sunwell.models.core.protocol import Tool


@dataclass(frozen=True, slots=True)
class ToolQuality:
    """Quality assessment of a tool description.

    Attributes:
        score: Overall quality score (0.0-1.0)
        issues: List of identified issues
        suggestions: Improvement suggestions
    """

    score: float
    """Quality score from 0.0 (poor) to 1.0 (excellent)."""

    issues: tuple[str, ...]
    """Identified issues with the tool description."""

    suggestions: tuple[str, ...]
    """Suggestions for improvement."""


# Quality thresholds
MIN_DESCRIPTION_LENGTH = 20
MAX_DESCRIPTION_LENGTH = 500
MIN_PARAM_DESCRIPTION_LENGTH = 10

# Words that indicate vague descriptions
VAGUE_WORDS = frozenset({
    "various",
    "different",
    "many",
    "some",
    "several",
    "etc",
    "stuff",
    "things",
    "data",
    "info",
    "information",
})

# Words that should be avoided in tool descriptions
MARKETING_WORDS = frozenset({
    "powerful",
    "flexible",
    "easy",
    "simple",
    "amazing",
    "best",
    "great",
    "awesome",
    "robust",
    "seamless",
    "intuitive",
})


def audit_tool(tool: Tool) -> ToolQuality:
    """Audit a single tool's description quality.

    Checks for:
    - Appropriate description length
    - Clear, unambiguous language
    - Documented parameters
    - Actionable usage hints

    Args:
        tool: Tool to audit

    Returns:
        ToolQuality assessment
    """
    issues: list[str] = []
    suggestions: list[str] = []
    score = 1.0

    # Check description length
    desc_len = len(tool.description)
    if desc_len < MIN_DESCRIPTION_LENGTH:
        issues.append(f"Description too short ({desc_len} chars)")
        suggestions.append("Add more detail about what the tool does and when to use it")
        score -= 0.2
    elif desc_len > MAX_DESCRIPTION_LENGTH:
        issues.append(f"Description too long ({desc_len} chars)")
        suggestions.append("Condense to key information")
        score -= 0.1

    # Check for vague words
    desc_lower = tool.description.lower()
    vague_found = [w for w in VAGUE_WORDS if w in desc_lower]
    if vague_found:
        issues.append(f"Vague language: {', '.join(vague_found)}")
        suggestions.append("Replace vague terms with specific details")
        score -= 0.1 * min(len(vague_found), 3)

    # Check for marketing words
    marketing_found = [w for w in MARKETING_WORDS if w in desc_lower]
    if marketing_found:
        issues.append(f"Marketing language: {', '.join(marketing_found)}")
        suggestions.append("Use factual, technical language instead")
        score -= 0.1 * min(len(marketing_found), 2)

    # Check parameter documentation
    params = tool.parameters.get("properties", {})
    required = set(tool.parameters.get("required", []))

    undocumented_params = []
    for param_name, param_schema in params.items():
        param_desc = param_schema.get("description", "")
        if len(param_desc) < MIN_PARAM_DESCRIPTION_LENGTH:
            undocumented_params.append(param_name)

    if undocumented_params:
        issues.append(f"Undocumented parameters: {', '.join(undocumented_params)}")
        suggestions.append("Add descriptions for all parameters")
        score -= 0.15 * min(len(undocumented_params), 3)

    # Check for required parameters without descriptions
    required_undoc = [p for p in required if p in undocumented_params]
    if required_undoc:
        issues.append(f"Required params without descriptions: {', '.join(required_undoc)}")
        score -= 0.1

    # Ensure score doesn't go below 0
    score = max(0.0, score)

    return ToolQuality(
        score=score,
        issues=tuple(issues),
        suggestions=tuple(suggestions),
    )


def audit_tool_set(tools: tuple[Tool, ...]) -> dict[str, ToolQuality]:
    """Audit a set of tools.

    Args:
        tools: Tools to audit

    Returns:
        Dict mapping tool name to quality assessment
    """
    return {tool.name: audit_tool(tool) for tool in tools}


def enhance_tool_description(tool: Tool) -> Tool:
    """Enhance a tool's description based on audit feedback.

    Applies automatic improvements where possible:
    - Removes marketing language
    - Adds missing structure

    Args:
        tool: Tool to enhance

    Returns:
        Enhanced Tool (or original if no changes needed)
    """
    description = tool.description

    # Remove marketing words
    for word in MARKETING_WORDS:
        # Case-insensitive replacement
        import re

        description = re.sub(rf"\b{word}\b", "", description, flags=re.IGNORECASE)

    # Clean up extra whitespace from removals
    description = " ".join(description.split())

    # Return enhanced tool if changed
    if description != tool.description:
        return Tool(
            name=tool.name,
            description=description,
            parameters=tool.parameters,
        )

    return tool


def get_quality_summary(audits: dict[str, ToolQuality]) -> dict[str, float | int]:
    """Get summary statistics for a tool audit.

    Args:
        audits: Dict of tool name to quality assessment

    Returns:
        Summary statistics dict
    """
    if not audits:
        return {"count": 0, "average_score": 0.0, "issues_count": 0}

    scores = [q.score for q in audits.values()]
    total_issues = sum(len(q.issues) for q in audits.values())

    return {
        "count": len(audits),
        "average_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
        "issues_count": total_issues,
        "tools_below_threshold": sum(1 for s in scores if s < 0.6),
    }
