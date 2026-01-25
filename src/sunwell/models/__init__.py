"""LLM model adapters and protocols.

Extended with:
- Tool calling support (RFC-012)
- Tool emulation ensures every model is agentic
- Model registry for delegation patterns (RFC-137)
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
from sunwell.models.registry import (
    ModelRegistry,
    get_registry,
    resolve_model,
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
    # RFC-137: Model registry for delegation
    "ModelRegistry",
    "get_registry",
    "resolve_model",
]
