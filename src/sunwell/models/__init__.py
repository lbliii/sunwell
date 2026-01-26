"""LLM model adapters and protocols.

Extended with:
- Tool calling support (RFC-012)
- Tool emulation ensures every model is agentic
- Model registry for delegation patterns (RFC-137)
"""

# Core protocol
# Adapters
from sunwell.models.adapters import (
    AnthropicModel,
    MockModel,
    OllamaModel,
    OpenAIModel,
)
from sunwell.models.core.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    # RFC-012: Tool calling types
    Tool,
    ToolCall,
    sanitize_llm_content,
)

# Emulation
from sunwell.models.emulation import ToolEmulatorModel, wrap_for_tools

# Registry
from sunwell.models.registry import (
    ModelRegistry,
    get_registry,
    resolve_model,
)

__all__ = [
    # Protocol
    "ModelProtocol",
    "GenerateOptions",
    "GenerateResult",
    "TokenUsage",
    # RFC-012: Tool calling
    "Message",
    "Tool",
    "ToolCall",
    # Utilities
    "sanitize_llm_content",
    # Registry
    "ModelRegistry",
    "get_registry",
    "resolve_model",
    # Adapters
    "AnthropicModel",
    "OpenAIModel",
    "OllamaModel",
    "MockModel",
    # Tool emulation (ensures every model is agentic)
    "ToolEmulatorModel",
    "wrap_for_tools",
]
