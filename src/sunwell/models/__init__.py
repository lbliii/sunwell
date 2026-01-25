"""LLM model adapters and protocols.

Extended with:
- Tool calling support (RFC-012)
- Tool emulation ensures every model is agentic
- Model registry for delegation patterns (RFC-137)
"""

# Core protocol
from sunwell.models.core.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    # RFC-012: Tool calling types
    Tool,
    ToolCall,
)

# Registry
from sunwell.models.registry import (
    ModelRegistry,
    get_registry,
    resolve_model,
)

# Adapters
from sunwell.models.adapters import (
    AnthropicModel,
    MockModel,
    OllamaModel,
    OpenAIModel,
)

# Emulation
from sunwell.models.emulation import ToolEmulatorModel, wrap_for_tools

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
