"""Tool context helpers for system prompt construction.

Provides functions to build tool hints and usage guidance sections
for injection into agent system prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.tools.registry.dynamic import DynamicToolRegistry


def build_tool_hints(registry: DynamicToolRegistry) -> str:
    """Build lightweight tool hints for inactive tools.

    Shows the LLM what additional tools are available without
    including their full schemas (which would bloat the context).

    Args:
        registry: DynamicToolRegistry to get hints from

    Returns:
        Formatted hints section or empty string if no inactive tools
    """
    hints = registry.get_hints()
    if not hints:
        return ""

    lines = ["<available_tools>"]
    lines.append("Additional tools available (will auto-load on first use):")
    for name, desc in sorted(hints.items()):
        lines.append(f"  - {name}: {desc}")
    lines.append("</available_tools>")
    return "\n".join(lines)


def build_tool_guidance(registry: DynamicToolRegistry) -> str:
    """Build usage guidance for active tools.

    Collects usage_guidance from all active tools that have it
    and formats for system prompt injection.

    Args:
        registry: DynamicToolRegistry to get guidance from

    Returns:
        Formatted guidance section or empty string if no guidance
    """
    return registry.get_active_guidance()


def build_tool_context(registry: DynamicToolRegistry) -> str:
    """Build combined tool hints AND usage guidance.

    This is the main entry point for system prompt tool context.
    Combines both hints (what tools exist) and guidance (how to use
    active tools well).

    Args:
        registry: DynamicToolRegistry to get context from

    Returns:
        Combined tool context for system prompt, or empty string

    Example:
        >>> context = build_tool_context(registry)
        >>> system_prompt = f"{base_prompt}\\n\\n{context}"
    """
    parts = []

    # Tool hints for inactive tools
    hints = build_tool_hints(registry)
    if hints:
        parts.append(hints)

    # Usage guidance for active tools
    guidance = build_tool_guidance(registry)
    if guidance:
        parts.append(guidance)

    return "\n\n".join(parts)


def format_tool_summary(registry: DynamicToolRegistry) -> str:
    """Build a summary of tool state for debugging/logging.

    Args:
        registry: DynamicToolRegistry to summarize

    Returns:
        Human-readable summary of tool state
    """
    active = registry.list_active_tools()
    all_tools = registry.list_all_tools()
    inactive = [t for t in all_tools if t not in active]

    lines = [
        f"Tools: {len(active)} active, {len(inactive)} available",
    ]

    if active:
        essential = [
            name for name in active
            if registry.tool_classes[name].metadata.essential
        ]
        if essential:
            lines.append(f"  Essential: {', '.join(essential)}")

        loaded = [name for name in active if name not in essential]
        if loaded:
            lines.append(f"  Loaded: {', '.join(loaded)}")

    return "\n".join(lines)
