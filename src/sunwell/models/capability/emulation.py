"""Adaptive tool emulation prompts for models without native tool support.

Provides model-size and capability-aware prompts that help smaller models
succeed at tool calling through JSON-structured output.

Key features:
- Compact prompts for small context windows
- Parallel tool calling prompts for capable models
- XML-style prompts for models that prefer it
- Tool definition optimization for context-constrained models
"""

from dataclasses import dataclass

from sunwell.models.capability.registry import ModelCapability
from sunwell.models.core.protocol import Tool


def format_tool_descriptions(tools: tuple[Tool, ...], compact: bool = False) -> str:
    """Format tools for prompt injection.

    Args:
        tools: Available tools
        compact: If True, use minimal format for small contexts

    Returns:
        Formatted tool descriptions
    """
    lines: list[str] = []

    for tool in tools:
        if compact:
            # Minimal format for small models
            params = tool.parameters.get("properties", {})
            param_names = ", ".join(params.keys())
            desc = tool.description[:80]
            if len(tool.description) > 80:
                desc = desc[:77] + "..."
            lines.append(f"- {tool.name}({param_names}): {desc}")
        else:
            # Full format
            lines.append(f"### {tool.name}")
            lines.append(tool.description)
            params = tool.parameters.get("properties", {})
            required = set(tool.parameters.get("required", []))

            if params:
                lines.append("Parameters:")
                for name, schema in params.items():
                    req = " (required)" if name in required else ""
                    param_type = schema.get("type", "any")
                    desc = schema.get("description", "")[:60]
                    lines.append(f"  - {name}: {param_type}{req} - {desc}")
            lines.append("")

    return "\n".join(lines)


# Standard JSON tool calling prompt
_STANDARD_PROMPT = """You have access to tools. When you need to use a tool, output ONLY a JSON block:

```json
{{"tool": "tool_name", "arguments": {{"arg1": "value1"}}}}
```

Available tools:
{tool_descriptions}

RULES:
1. Output ONLY the JSON block when calling a tool - no other text
2. For code tasks, use write_file tool - do NOT output code directly
3. After tool execution, you'll see the result and can continue
"""

# Compact prompt for small context windows
_COMPACT_PROMPT = """Tools available. Call with JSON:
{{"tool": "NAME", "arguments": {{...}}}}

{tool_descriptions}

Output ONLY JSON when calling tools."""

# Parallel tool calling prompt
_PARALLEL_PROMPT = """You have access to tools. You can call multiple tools in one response.

When calling tools, output JSON blocks (one per tool):

```json
{{"tool": "tool1", "arguments": {{...}}}}
```

```json
{{"tool": "tool2", "arguments": {{...}}}}
```

Available tools:
{tool_descriptions}
"""

# XML-style prompt for models that prefer structured markup
_XML_PROMPT = """You have access to tools. When calling a tool, use this format:

<tool_call>
<name>tool_name</name>
<arguments>
<arg1>value1</arg1>
<arg2>value2</arg2>
</arguments>
</tool_call>

Available tools:
{tool_descriptions}
"""


def build_emulation_prompt(
    tools: tuple[Tool, ...],
    capability: ModelCapability,
    task_hint: str | None = None,
) -> str:
    """Build a model-appropriate tool emulation prompt.

    Adapts prompt complexity based on:
    - Context window size
    - Parallel tool support
    - Preferred emulation style

    Args:
        tools: Available tools
        capability: Model capabilities
        task_hint: Optional hint about task complexity

    Returns:
        Formatted prompt for tool emulation
    """
    # Determine if we need compact format
    compact = capability.context_window is not None and capability.context_window < 8192

    tool_descriptions = format_tool_descriptions(tools, compact=compact)

    # Select prompt template
    if capability.emulation_style == "xml":
        template = _XML_PROMPT
    elif capability.parallel_tools:
        template = _PARALLEL_PROMPT
    elif compact:
        template = _COMPACT_PROMPT
    else:
        template = _STANDARD_PROMPT

    return template.format(tool_descriptions=tool_descriptions)


@dataclass(frozen=True, slots=True)
class OptimizedTool:
    """A tool with optimized description for context constraints."""

    name: str
    description: str
    parameters: dict
    original_description_length: int
    was_truncated: bool


def optimize_tool_definitions(
    tools: tuple[Tool, ...],
    capability: ModelCapability,
    task_hint: str | None = None,
) -> tuple[Tool, ...]:
    """Optimize tool set for available context (Journey E6).

    When models have limited context windows, we need to:
    1. Prioritize tools relevant to the task
    2. Truncate verbose descriptions
    3. Remove optional parameters if needed
    4. Limit total tool count

    Args:
        tools: All available tools
        capability: Model capabilities (for context_window)
        task_hint: Optional task description for prioritization

    Returns:
        Optimized tool set that fits context
    """
    context_window = capability.context_window or 128000

    # Plenty of room — no optimization needed
    if context_window >= 32000:
        return tools

    def estimate_tokens(tool: Tool) -> int:
        """Estimate token count for a tool definition."""
        # Rough estimate: ~4 chars per token
        return (
            len(tool.name)
            + len(tool.description) // 4
            + len(str(tool.parameters)) // 4
        )

    # Budget: 20% of context for tools
    tool_budget = context_window // 5

    # Sort by relevance if task_hint provided
    sorted_tools = list(tools)
    if task_hint:
        task_lower = task_hint.lower()

        def relevance_score(tool: Tool) -> float:
            score = 0.0
            # Name match
            if tool.name.lower() in task_lower:
                score += 10.0
            # Description overlap
            desc_words = set(tool.description.lower().split())
            task_words = set(task_lower.split())
            overlap = len(desc_words & task_words)
            score += overlap * 0.5
            return score

        sorted_tools.sort(key=relevance_score, reverse=True)

    # Greedily select tools within budget
    selected: list[Tool] = []
    used_tokens = 0

    for tool in sorted_tools:
        # Truncate descriptions for small contexts
        if context_window < 8192 and len(tool.description) > 200:
            tool = Tool(
                name=tool.name,
                description=tool.description[:200] + "...",
                parameters=tool.parameters,
            )

        tokens = estimate_tokens(tool)

        if used_tokens + tokens <= tool_budget:
            selected.append(tool)
            used_tokens += tokens
        else:
            # Stop if we can't fit more tools
            break

    return tuple(selected)
