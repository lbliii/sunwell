"""Core model protocol and types.

This package contains the fundamental ModelProtocol interface and
related types used throughout the models system.
"""

from sunwell.models.core.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    Tool,
    ToolCall,
    _sanitize_dict_values,
    sanitize_llm_content,
    tool_from_skill,
)

__all__ = [
    "ModelProtocol",
    "GenerateOptions",
    "GenerateResult",
    "TokenUsage",
    "Message",
    "Tool",
    "ToolCall",
    "sanitize_llm_content",
    "_sanitize_dict_values",
    "tool_from_skill",
]
