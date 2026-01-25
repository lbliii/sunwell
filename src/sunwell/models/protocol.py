"""Model protocol - provider-agnostic LLM interface.

Extended with tool calling support per RFC-012.
Includes LLM output sanitization per RFC-091.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sunwell.planning.skills.types import Skill

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Output Sanitization (RFC-091)
# =============================================================================


def sanitize_llm_content(text: str | None) -> str | None:
    """Remove control characters from LLM output.

    Preserves newlines, carriage returns, and tabs which are valid
    in JSON strings and needed for code formatting.

    Applied once at the model layer, not on every read.

    Args:
        text: Raw LLM output text (may be None for tool-only responses)

    Returns:
        Sanitized text with control characters removed, or None if input was None
    """
    if text is None:
        return None

    sanitized = "".join(c for c in text if not (ord(c) < 32 and c not in "\n\r\t"))

    # Log when sanitization actually removed characters (debug level)
    if len(sanitized) != len(text):
        logger.debug(
            "Sanitized control chars from LLM output",
            extra={
                "original_len": len(text),
                "sanitized_len": len(sanitized),
                "chars_removed": len(text) - len(sanitized),
            },
        )

    return sanitized


def _sanitize_dict_values(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize string values in a dict.

    Used for sanitizing tool call arguments which may contain control characters.

    Args:
        d: Dictionary with potentially unsanitized string values

    Returns:
        Dictionary with all string values sanitized
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = sanitize_llm_content(v)
        elif isinstance(v, dict):
            result[k] = _sanitize_dict_values(v)
        elif isinstance(v, list):
            result[k] = [
                _sanitize_dict_values(i)
                if isinstance(i, dict)
                else sanitize_llm_content(i)
                if isinstance(i, str)
                else i
                for i in v
            ]
        else:
            result[k] = v
    return result

# =============================================================================
# Message Types (RFC-012)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Message:
    """A conversation message for multi-turn interactions.

    Supports system, user, assistant, and tool result messages.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None

    # For assistant messages with tool calls
    tool_calls: tuple[ToolCall, ...] = ()

    # For tool result messages
    tool_call_id: str | None = None


# =============================================================================
# Tool Types (RFC-012)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable tool the LLM can invoke.

    Tools are defined with JSON Schema parameters and can be
    created from Sunwell skills.
    """

    name: str
    description: str
    parameters: dict  # JSON Schema

    @classmethod
    def from_skill(cls, skill: Skill) -> Tool:
        """Convert a Sunwell skill to a tool definition.

        Args:
            skill: A Skill object with name, description, and optional parameters_schema

        Returns:
            A Tool object suitable for LLM function calling
        """
        # Import here to avoid circular dependency

        return cls(
            name=skill.name,
            description=skill.description,
            parameters=skill.parameters_schema if hasattr(skill, 'parameters_schema') and skill.parameters_schema else {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task to perform with this skill",
                    }
                },
                "required": ["task"],
            },
        )


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation requested by the LLM.

    Contains the unique ID (for correlating results), tool name,
    and parsed arguments.
    """

    id: str
    name: str
    arguments: dict


# =============================================================================
# Generation Options & Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class GenerateOptions:
    """Options for model generation."""

    temperature: float = 0.7
    max_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    system_prompt: str | None = None
    tools: tuple[Tool, ...] | None = None  # RFC-027: Tools for self-directed generation


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Result from model generation.

    Migration note: `content` is now `str | None` to support
    tool-only responses. Use the `.text` property for backward
    compatibility with existing code.
    """

    content: str | None  # Text response (may be None when tool_calls present)
    model: str
    tool_calls: tuple[ToolCall, ...] = ()  # Tool requests from the model
    usage: TokenUsage | None = None
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if this result contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def text(self) -> str:
        """Get content as string, defaulting to empty string.

        Recommended for all existing code using result.content.
        This ensures backward compatibility when tools are not used.
        """
        return self.content or ""


# =============================================================================
# Model Protocol
# =============================================================================


@runtime_checkable
class ModelProtocol(Protocol):
    """Protocol for LLM providers.

    Implementations: OpenAI, Anthropic, Ollama, Mock, etc.

    Extended in RFC-012 to support:
    - Multi-turn conversations via Message tuples
    - Tool/function calling
    - Flexible tool_choice control
    """

    @property
    def model_id(self) -> str:
        """The model identifier (e.g., 'gpt-4', 'claude-3-opus')."""
        ...

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response.

        Args:
            prompt: Either a single string prompt, or a tuple of Messages
                    for multi-turn conversations.
            tools: Available tools the model can call. When provided,
                   the model may choose to call tools instead of generating text.
            tool_choice: Controls tool calling behavior:
                - "auto": Model decides whether to call tools (default)
                - "none": Never call tools
                - "required": Must call at least one tool
                - str: Force calling a specific tool by name
                - dict: Provider-specific tool_choice (passed through)
            options: Generation options (temperature, max_tokens, etc.)

        Returns:
            GenerateResult with content, tool_calls, and usage info.
            When tool_calls is non-empty, content may be None.
        """
        ...

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response for the given prompt.

        Note: Streaming with tools may yield partial tool calls.
        Use generate() for complete tool call handling.
        """
        ...

    async def list_models(self) -> list[str]:
        """List available models for this provider."""
        ...
