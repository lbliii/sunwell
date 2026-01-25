"""Model adapters for different providers.

This package contains provider-specific implementations of ModelProtocol:
- Anthropic (Claude)
- OpenAI (GPT)
- Ollama (local models)
- Mock (testing)
"""

from sunwell.models.adapters.anthropic import AnthropicModel
from sunwell.models.adapters.mock import MockModel, MockModelWithTools
from sunwell.models.adapters.ollama import OllamaModel
from sunwell.models.adapters.openai import OpenAIModel

__all__ = [
    "AnthropicModel",
    "OpenAIModel",
    "OllamaModel",
    "MockModel",
    "MockModelWithTools",
]
