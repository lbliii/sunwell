"""LLM model adapters and protocols.

Extended with tool calling support per RFC-012.
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

__all__ = [
    "ModelProtocol",
    "GenerateOptions",
    "GenerateResult",
    "TokenUsage",
    # RFC-012
    "Message",
    "Tool",
    "ToolCall",
]
