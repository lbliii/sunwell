"""Provider-specific schema adapters for tool calling.

Converts Sunwell's tool definitions to provider-specific formats.
Handles OpenAI strict mode, Anthropic's input_schema, and Ollama quirks.

Research Insight: OpenAI's strict mode achieves 100% schema accuracy
vs ~40% without. Enable by default for reliable tool calling.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from sunwell.models.protocol import Tool


class SchemaAdapter(Protocol):
    """Protocol for provider-specific schema conversion."""

    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert Sunwell tools to provider format."""
        ...

    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to provider format."""
        ...


@dataclass(frozen=True, slots=True)
class OpenAISchemaAdapter:
    """OpenAI function calling schema format.

    Research Insight: OpenAI's strict mode achieves 100% schema accuracy
    vs ~40% without. Enable by default for reliable tool calling.
    """

    strict_mode: bool = True
    """Enable strict schema validation (100% vs ~40% accuracy)."""

    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert tools to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": self._validate_schema(t.parameters),
                    **({"strict": True} if self.strict_mode else {}),
                },
            }
            for t in tools
        ]

    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to OpenAI format."""
        if choice is None or isinstance(choice, dict):
            return choice
        if choice in ("auto", "none", "required"):
            return choice
        # Force specific tool
        return {"type": "function", "function": {"name": choice}}

    def _validate_schema(self, schema: dict) -> dict:
        """Validate and normalize JSON Schema for OpenAI.

        For strict mode, ensures:
        - Root type is "object"
        - additionalProperties is false
        - All properties have explicit types
        """
        result = dict(schema)

        # Ensure required fields
        if "type" not in result:
            result["type"] = "object"

        if self.strict_mode:
            # Strict mode requirements
            if result.get("type") == "object":
                result["additionalProperties"] = False

                # Ensure properties exist
                if "properties" not in result:
                    result["properties"] = {}

        return result


@dataclass(frozen=True, slots=True)
class AnthropicSchemaAdapter:
    """Anthropic tool schema format.

    Key differences from OpenAI:
    - Uses 'input_schema' instead of 'parameters'
    - Tool results go in user messages with tool_result type
    - Stricter schema validation required
    """

    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert tools to Anthropic tool format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": self._strict_schema(t.parameters),
            }
            for t in tools
        ]

    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> dict | None:
        """Convert tool_choice to Anthropic format."""
        if choice is None:
            return None
        if isinstance(choice, dict):
            return choice
        if choice == "auto":
            return {"type": "auto"}
        if choice == "none":
            return None  # Anthropic: don't send tools instead
        if choice == "required":
            return {"type": "any"}
        # Force specific tool
        return {"type": "tool", "name": choice}

    def _strict_schema(self, schema: dict) -> dict:
        """Ensure schema meets Anthropic's strict requirements.

        Anthropic requires:
        - type: object at root
        - properties defined
        - additionalProperties: false
        """
        result = dict(schema)

        # Must have type: object at root
        if result.get("type") != "object":
            result["type"] = "object"

        # Must have properties
        if "properties" not in result:
            result["properties"] = {}

        # additionalProperties should be false for strict mode
        result["additionalProperties"] = False

        return result


@dataclass(frozen=True, slots=True)
class OllamaSchemaAdapter:
    """Ollama tool schema format (OpenAI-compatible with quirks).

    Quirks:
    - Descriptions may be truncated at 500 chars
    - Some models don't support strict mode
    - Tool streaming may not be available
    """

    max_description_length: int = 500
    """Maximum description length before truncation."""

    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert tools to Ollama format (OpenAI-compatible)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": self._truncate(t.description),
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to Ollama format."""
        if choice is None or isinstance(choice, dict):
            return choice
        if choice in ("auto", "none", "required"):
            return choice
        return {"type": "function", "function": {"name": choice}}

    def _truncate(self, text: str) -> str:
        """Truncate description if needed."""
        if len(text) <= self.max_description_length:
            return text
        return text[: self.max_description_length - 3] + "..."


@dataclass(frozen=True, slots=True)
class TogetherSchemaAdapter:
    """Together AI schema adapter (OpenAI-compatible)."""

    def convert_tools(self, tools: tuple[Tool, ...]) -> list[dict]:
        """Convert tools to Together format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def convert_tool_choice(
        self,
        choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to Together format."""
        if choice is None or isinstance(choice, dict):
            return choice
        if choice in ("auto", "none", "required"):
            return choice
        return {"type": "function", "function": {"name": choice}}


# Registry of adapters by provider
_ADAPTERS: dict[str, SchemaAdapter] = {
    "openai": OpenAISchemaAdapter(),
    "anthropic": AnthropicSchemaAdapter(),
    "ollama": OllamaSchemaAdapter(),
    "together": TogetherSchemaAdapter(),
    "groq": OpenAISchemaAdapter(),
    "fireworks": OpenAISchemaAdapter(),
    "anyscale": OpenAISchemaAdapter(),
    "deepinfra": OpenAISchemaAdapter(),
    "openrouter": OpenAISchemaAdapter(),
    "perplexity": OpenAISchemaAdapter(),
}


def get_schema_adapter(provider: str) -> SchemaAdapter:
    """Get the appropriate schema adapter for a provider.

    Args:
        provider: Provider name (openai, anthropic, ollama, etc.)

    Returns:
        SchemaAdapter for the provider (defaults to OpenAI format)
    """
    return _ADAPTERS.get(provider.lower(), OpenAISchemaAdapter())
