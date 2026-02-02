"""Dynamic tool registry for self-registering tools.

This module implements a MIRA-inspired dynamic tool registry that:
- Discovers tools via pkgutil scanning of implementations/
- Enables runtime enable/disable of tools
- Provides synthetic loading (auto-enable on first call)
- Supports tool-specific usage guidance

Example:
    >>> from sunwell.tools.registry import DynamicToolRegistry, BaseTool, tool_metadata
    >>>
    >>> @tool_metadata(
    ...     name="my_tool",
    ...     simple_description="A custom tool",
    ... )
    >>> class MyTool(BaseTool):
    ...     parameters = {"type": "object", "properties": {}}
    ...     async def execute(self, arguments: dict) -> str:
    ...         return "Done"
"""

from sunwell.tools.registry.base import (
    BaseTool,
    ToolContext,
    ToolMetadata,
    tool_metadata,
)
from sunwell.tools.registry.context import (
    build_tool_context,
    build_tool_guidance,
    build_tool_hints,
    format_tool_summary,
)
from sunwell.tools.registry.dynamic import DynamicToolRegistry

__all__ = [
    # Core classes
    "BaseTool",
    "DynamicToolRegistry",
    "ToolContext",
    "ToolMetadata",
    # Decorator
    "tool_metadata",
    # Context helpers
    "build_tool_context",
    "build_tool_guidance",
    "build_tool_hints",
    "format_tool_summary",
]
