"""Load tool meta-tool for explicit tool loading.

While synthetic loading means tools auto-enable on first call,
this meta-tool allows the LLM to explicitly pre-load tools
before using them (e.g., to explain what tools are available).
"""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="load_tool",
    simple_description="Load additional tools into context",
    trust_level=ToolTrust.READ_ONLY,
    essential=True,  # Always available for tool management
    usage_guidance=(
        "Use load_tool to explicitly enable tools before using them. "
        "Note: Tools auto-load on first use, so this is optional. "
        "Check tool_hints in your context for available tools."
    ),
)
class LoadToolTool(BaseTool):
    """Load tools on demand when standard tools are insufficient.

    Use this when you need capabilities not in your current toolset.
    Check tool_hints in your context for available tools.

    Note: With synthetic loading, tools auto-enable on first call,
    so explicit loading is optional but can be useful for:
    - Pre-loading tools before explaining what's available
    - Loading multiple related tools at once
    - Checking if a tool exists before attempting to use it
    """

    parameters = {
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tool names to load",
            },
        },
        "required": ["tools"],
    }

    async def execute(self, arguments: dict) -> str:
        """Load specified tools.

        Args:
            arguments: Must contain 'tools' array of tool names

        Returns:
            Summary of loaded tools and any errors
        """
        tools = arguments["tools"]
        loaded = []
        already_active = []
        not_found = []

        for name in tools:
            if self.registry.is_active(name):
                already_active.append(name)
            elif self.registry.is_known(name):
                if self.registry.enable(name):
                    loaded.append(name)
                else:
                    # Should not happen if is_known returned True
                    not_found.append(name)
            else:
                not_found.append(name)

        parts = []

        if loaded:
            parts.append(f"Loaded: {', '.join(loaded)}")

        if already_active:
            parts.append(f"Already active: {', '.join(already_active)}")

        if not_found:
            # Suggest similar tools if possible
            all_tools = self.registry.list_all_tools()
            suggestions = []
            for name in not_found:
                # Simple substring matching for suggestions
                similar = [t for t in all_tools if name.lower() in t.lower()]
                if similar:
                    suggestions.append(f"'{name}' not found, did you mean: {', '.join(similar[:3])}?")
                else:
                    suggestions.append(f"'{name}' not found")
            parts.append("Errors: " + "; ".join(suggestions))

        if loaded:
            parts.append("\nThese tools are now available for use.")

        return "\n".join(parts) if parts else "No tools specified."
