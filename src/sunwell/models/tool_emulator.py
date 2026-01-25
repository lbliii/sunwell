"""Tool emulation for models without native tool calling.

Any model can use tools via JSON-structured output. This module wraps models
that don't support native tool calling and adds the capability.

The floor is: every model is agentic. No exceptions.
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

    # Pattern: ```json ... ``` or just {...}
    json_pattern = r'```json\s*(\{[^`]+\})\s*```|(\{["\']tool["\']:\s*["\'][^}]+\})'

    for match in re.finditer(json_pattern, text, re.DOTALL):
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


@dataclass(slots=True)
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
    # We do this by checking model capabilities or trying to detect
    model_id = getattr(model, "model_id", "") or getattr(model, "model", "")

    # Known models with native tool support
    # TODO: Move this to a proper capability registry
    native_tool_models = {
        "gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo",
        "claude-3", "claude-3.5", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
        "llama3", "llama3.1", "llama3.2", "llama3:8b", "llama3:70b",
        "qwen2.5", "mistral", "mixtral",
    }

    # Check if any known model is a prefix
    for known in native_tool_models:
        if known in model_id.lower():
            return model  # Has native support

    # Check via capability registry if available
    try:
        from sunwell.runtime.model_router import get_model_capability

        cap = get_model_capability(model_id)
        if cap and cap.tools:
            return model  # Has native support
    except ImportError:
        pass

    # Wrap with emulator
    return ToolEmulatorModel(inner_model=model)
