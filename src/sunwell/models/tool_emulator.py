"""Tool emulation for models without native tool calling.

Any model can use tools via JSON-structured output. This module wraps models
that don't support native tool calling and adds the capability.

The floor is: every model is agentic. No exceptions.

Model capability registry enables intelligent routing:
- Native tools: Use structured tool calling
- Parallel tools: Execute multiple tools in one turn
- Tool streaming: Stream tool call arguments
- JSON mode: Structured output without tools
"""

import json
import re
from dataclasses import dataclass
from typing import Literal

from sunwell.models.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    Tool,
    ToolCall,
)

# Pre-compiled regex for parsing tool calls from text (O(1) vs O(n) per call)
_TOOL_JSON_PATTERN = re.compile(
    r'```json\s*(\{[^`]+\})\s*```|(\{["\']tool["\']:\s*["\'][^}]+\})',
    re.DOTALL,
)


# =============================================================================
# Model Capability Registry (S-Tier Tool Calling)
# =============================================================================


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """Capabilities of a model for intelligent routing.

    This enables Sunwell to adapt its execution strategy based on what
    the model supports:
    - native_tools: Use structured tool calling (preferred)
    - parallel_tools: Can execute multiple tools in one turn
    - tool_streaming: Can stream tool call arguments as they're generated
    - json_mode: Can produce structured JSON output reliably
    - reasoning: Supports extended thinking/reasoning (e.g., Claude thinking)
    """

    native_tools: bool = False
    """Model supports native function/tool calling."""

    parallel_tools: bool = False
    """Model can call multiple tools in a single turn."""

    tool_streaming: bool = False
    """Model supports streaming tool call arguments."""

    json_mode: bool = False
    """Model has reliable JSON output mode."""

    reasoning: bool = False
    """Model supports extended thinking/reasoning blocks."""

    max_output_tokens: int | None = None
    """Maximum output tokens (for budget calculations)."""

    context_window: int | None = None
    """Maximum context window size."""


# Comprehensive model capability registry
# Keys are model name prefixes (matched case-insensitively)
MODEL_CAPABILITIES: dict[str, ModelCapability] = {
    # OpenAI models
    "gpt-4o": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        max_output_tokens=16384,
        context_window=128000,
    ),
    "gpt-4o-mini": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        max_output_tokens=16384,
        context_window=128000,
    ),
    "gpt-4-turbo": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=4096,
        context_window=128000,
    ),
    "gpt-4": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        max_output_tokens=8192,
        context_window=8192,
    ),
    "gpt-3.5-turbo": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=4096,
        context_window=16385,
    ),
    "o1": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        reasoning=True,
        max_output_tokens=100000,
        context_window=200000,
    ),
    "o3": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        reasoning=True,
        max_output_tokens=100000,
        context_window=200000,
    ),

    # Anthropic models
    "claude-4": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        reasoning=True,
        max_output_tokens=64000,
        context_window=200000,
    ),
    "claude-3.5-sonnet": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=200000,
    ),
    "claude-3.5-haiku": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=200000,
    ),
    "claude-3-opus": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        max_output_tokens=4096,
        context_window=200000,
    ),
    "claude-3-sonnet": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        max_output_tokens=4096,
        context_window=200000,
    ),
    "claude-3-haiku": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        max_output_tokens=4096,
        context_window=200000,
    ),

    # Llama models (via Ollama or cloud providers)
    "llama3.3": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=128000,
    ),
    "llama3.2": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=128000,
    ),
    "llama3.1": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=128000,
    ),
    "llama3": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        max_output_tokens=4096,
        context_window=8192,
    ),

    # Qwen models
    "qwen2.5": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=32768,
    ),
    "qwen3": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        reasoning=True,
        max_output_tokens=8192,
        context_window=128000,
    ),

    # Mistral models
    "mistral-large": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=128000,
    ),
    "mistral": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        max_output_tokens=4096,
        context_window=32768,
    ),
    "mixtral": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        max_output_tokens=4096,
        context_window=32768,
    ),

    # Google models
    "gemini-2": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        tool_streaming=True,
        json_mode=True,
        reasoning=True,
        max_output_tokens=8192,
        context_window=1000000,
    ),
    "gemini-1.5-pro": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=1000000,
    ),
    "gemini-1.5-flash": ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=1000000,
    ),

    # DeepSeek models
    "deepseek-r1": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        reasoning=True,
        max_output_tokens=8192,
        context_window=64000,
    ),
    "deepseek-v3": ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=64000,
    ),

    # Models that DON'T support native tools (need emulation)
    "gemma": ModelCapability(native_tools=False),
    "phi": ModelCapability(native_tools=False),
    "codellama": ModelCapability(native_tools=False),
    "starcoder": ModelCapability(native_tools=False),
}


def get_model_capability(model_id: str) -> ModelCapability:
    """Get capabilities for a model.

    Matches model_id against known prefixes (case-insensitive).
    Returns default (no capabilities) if model is unknown.

    Args:
        model_id: The model identifier (e.g., "gpt-4o", "claude-3.5-sonnet")

    Returns:
        ModelCapability for the model
    """
    model_lower = model_id.lower()

    # Check exact match first, then prefix matches (longest first)
    for key in sorted(MODEL_CAPABILITIES.keys(), key=len, reverse=True):
        if key.lower() in model_lower:
            return MODEL_CAPABILITIES[key]

    # Unknown model - assume no native tools
    return ModelCapability()


def has_native_tools(model_id: str) -> bool:
    """Check if a model supports native tool calling.

    Quick check for routing decisions.
    """
    return get_model_capability(model_id).native_tools


# Legacy: Keep old frozenset for backward compatibility
_NATIVE_TOOL_MODELS: frozenset[str] = frozenset(
    key for key, cap in MODEL_CAPABILITIES.items() if cap.native_tools
)

# System prompt that teaches the model to use tools via JSON
# Note: Double braces {{ }} are escaped for .format() - they become single braces
TOOL_EMULATION_PROMPT = """You have access to tools. When you need to use a tool, output a JSON block:

```json
{{"tool": "tool_name", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}
```

Available tools:
{tool_descriptions}

IMPORTANT:
- Output ONLY the JSON block when calling a tool, nothing else
- After receiving tool results, continue your response
- You can call multiple tools by outputting multiple JSON blocks
- When you're done and have your final answer, just output text normally (no JSON)
"""


def format_tool_descriptions(tools: tuple[Tool, ...]) -> str:
    """Format tools for inclusion in prompt."""
    lines = []
    for tool in tools:
        lines.append(f"### {tool.name}")
        lines.append(f"{tool.description}")
        if tool.parameters:
            params = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])
            if params:
                lines.append("Parameters:")
                for name, schema in params.items():
                    req = " (required)" if name in required else ""
                    desc = schema.get("description", "")
                    lines.append(f"  - {name}{req}: {desc}")
        lines.append("")
    return "\n".join(lines)


def parse_tool_calls_from_text(text: str) -> tuple[list[ToolCall], str]:
    """Parse tool calls from model output.

    Returns:
        (tool_calls, remaining_text) - tool calls found and text after them
    """
    tool_calls = []
    remaining = text

    for match in _TOOL_JSON_PATTERN.finditer(text):
        json_str = match.group(1) or match.group(2)
        try:
            data = json.loads(json_str)
            if "tool" in data:
                tool_calls.append(
                    ToolCall(
                        id=f"emulated_{len(tool_calls)}",
                        name=data["tool"],
                        arguments=data.get("arguments", {}),
                    )
                )
                # Remove this JSON from remaining text
                remaining = remaining.replace(match.group(0), "", 1)
        except json.JSONDecodeError:
            continue

    return tool_calls, remaining.strip()


@dataclass(frozen=True, slots=True)
class ToolEmulatorModel:
    """Wraps a model to add tool calling via JSON emulation.

    This ensures EVERY model can use tools, even if it doesn't support
    native function calling. The floor is agentic.

    Usage:
        base_model = OllamaModel(model="gemma3:4b")  # No native tool support
        model = ToolEmulatorModel(base_model)
        result = await model.generate(prompt, tools=my_tools)  # Works!
    """

    inner_model: object  # The wrapped model (any ModelProtocol)

    @property
    def model_id(self) -> str:
        """Delegate to inner model."""
        return self.inner_model.model_id  # type: ignore

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate with tool emulation.

        If tools are provided, we inject them into the prompt and parse
        JSON tool calls from the response.
        """
        opts = options or GenerateOptions()

        # No tools? Just delegate
        if not tools:
            return await self.inner_model.generate(prompt, options=opts)  # type: ignore

        # Build tool-aware prompt
        tool_descriptions = format_tool_descriptions(tools)
        tool_system = TOOL_EMULATION_PROMPT.format(tool_descriptions=tool_descriptions)

        # Prepend to system prompt
        if opts.system_prompt:
            enhanced_system = f"{tool_system}\n\n---\n\n{opts.system_prompt}"
        else:
            enhanced_system = tool_system

        enhanced_opts = GenerateOptions(
            system_prompt=enhanced_system,
            temperature=opts.temperature,
            max_tokens=opts.max_tokens,
            stop_sequences=opts.stop_sequences,
        )

        # Generate without passing tools (model doesn't support them)
        result = await self.inner_model.generate(prompt, options=enhanced_opts)  # type: ignore

        # Parse tool calls from the text
        if result.content:
            tool_calls, remaining_text = parse_tool_calls_from_text(result.content)
            if tool_calls:
                return GenerateResult(
                    content=remaining_text or None,
                    model=result.model,
                    tool_calls=tuple(tool_calls),
                    usage=result.usage,
                    finish_reason=result.finish_reason,
                )

        return result

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ):
        """Stream generation - delegates to inner model.

        Note: Streaming with tool emulation collects full response for parsing.
        """
        # For streaming with tools, we need to collect and parse
        # This is a simplification - could be improved later
        if tools:
            result = await self.generate(prompt, tools=tools, options=options)
            if result.content:
                yield result.content
        else:
            async for chunk in self.inner_model.generate_stream(prompt, options=options):  # type: ignore
                yield chunk


def wrap_for_tools(model: object) -> object:
    """Wrap a model with tool emulation if it doesn't support native tools.

    This is the key function that ensures the agentic floor:
    - If model supports tools → return as-is
    - If model doesn't → wrap with ToolEmulatorModel

    Usage:
        model = wrap_for_tools(any_model)  # Now always has tool support
    """
    # Check if model already supports tools
    model_id = getattr(model, "model_id", "") or getattr(model, "model", "")

    # Use capability registry
    if has_native_tools(model_id):
        return model  # Has native support

    # Wrap with emulator
    return ToolEmulatorModel(inner_model=model)
