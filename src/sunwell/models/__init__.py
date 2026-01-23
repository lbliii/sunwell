"""LLM model adapters and protocols.

Extended with tool calling support per RFC-012.
Tool emulation ensures every model is agentic.
"""

from sunwell.models.protocol import (
    GenerateOptions,
    GenerateResult,
    # RFC-012: Tool calling types
    Message,
    ModelProtocol,
    TokenUsage,
    Tool,
    ToolCall,
)
from sunwell.models.tool_emulator import ToolEmulatorModel, wrap_for_tools

__all__ = [
    "ModelProtocol",
    "GenerateOptions",
    "GenerateResult",
    "TokenUsage",
    # RFC-012: Tool calling
    "Message",
    "Tool",
    "ToolCall",
    # Tool emulation (ensures every model is agentic)
    "ToolEmulatorModel",
    "wrap_for_tools",
]
