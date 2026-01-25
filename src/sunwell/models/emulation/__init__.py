"""Tool emulation for models without native tool calling.

Ensures every model can use tools via JSON-structured output,
providing the agentic floor for all models.
"""

from sunwell.models.emulation.tool_emulator import (
    ModelCapability,
    ToolEmulatorModel,
    format_tool_descriptions,
    get_model_capability,
    has_native_tools,
    parse_tool_calls_from_text,
    wrap_for_tools,
)

__all__ = [
    "ToolEmulatorModel",
    "wrap_for_tools",
    "ModelCapability",
    "get_model_capability",
    "has_native_tools",
    "format_tool_descriptions",
    "parse_tool_calls_from_text",
]
