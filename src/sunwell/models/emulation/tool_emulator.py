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

from sunwell.models.core.protocol import (
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


def get_model_capability(model_id: str) -> ModelCapability:
    """Get capabilities for a model.

    Uses the new RFC-136 capability system with structured model parsing
    and version-aware capability matching.

    Args:
        model_id: The model identifier (e.g., "gpt-4o", "claude-3.5-sonnet")

    Returns:
        ModelCapability for the model
    """
    # Use new RFC-136 capability system
    from sunwell.models.capability.registry import get_capability as _get_capability

    new_cap = _get_capability(model_id)

    # Convert to local ModelCapability (compatible fields)
    return ModelCapability(
        native_tools=new_cap.native_tools,
        parallel_tools=new_cap.parallel_tools,
        tool_streaming=new_cap.tool_streaming,
        json_mode=new_cap.json_mode,
        reasoning=new_cap.reasoning,
        max_output_tokens=new_cap.max_output_tokens,
        context_window=new_cap.context_window,
    )


def has_native_tools(model_id: str) -> bool:
    """Check if a model supports native tool calling.

    Quick check for routing decisions.
    """
    return get_model_capability(model_id).native_tools


# System prompt that teaches the model to use tools via JSON
# Note: Double braces {{ }} are escaped for .format() - they become single braces
# Based on Google's function calling guidance for non-native tool models
TOOL_EMULATION_PROMPT = """You have access to tools. You MUST use them to complete tasks.

When you need to use a tool, output ONLY a JSON block in this exact format:

```json
{{"tool": "tool_name", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}
```

Available tools:
{tool_descriptions}

CRITICAL RULES:
1. When calling a tool, output ONLY the JSON block - no other text
2. For code generation tasks, you MUST use the write_file tool
3. Do NOT output code directly in your response - always use write_file
4. After tool execution, you will receive the result and can continue
5. You can call multiple tools by outputting multiple JSON blocks
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


def _looks_like_code(text: str) -> bool:
    """Detect if text looks like code output (not tool call JSON).

    Used to catch when models output code directly instead of calling write_file.
    """
    # Strip markdown fences if present
    content = text.strip()
    if content.startswith("```"):
        # Has markdown fence - definitely looks like code
        return True

    # Check for common code patterns
    code_indicators = [
        "def ",       # Python function
        "class ",     # Python/JS class
        "import ",    # Python import
        "from ",      # Python from import
        "function ",  # JS function
        "const ",     # JS const
        "let ",       # JS let
        "export ",    # JS/TS export
        "async ",     # Async function
        "if __name__",  # Python main guard
        "#!/",        # Shebang
    ]

    # Check first 500 chars for code patterns
    sample = content[:500]
    return any(indicator in sample for indicator in code_indicators)


def _extract_code_from_markdown(text: str) -> str:
    """Extract code content from markdown fences if present."""
    content = text.strip()

    # Match ```language\ncode\n``` pattern
    fence_pattern = re.compile(r'^```\w*\n(.*?)```', re.DOTALL)
    match = fence_pattern.match(content)
    if match:
        return match.group(1).strip()

    # No fence, return as-is
    return content


def parse_tool_calls_from_text(
    text: str,
    expected_tool: str | None = None,
    target_path: str | None = None,
) -> tuple[list[ToolCall], str]:
    """Parse tool calls from model output.

    Enhanced with code detection fallback: if no tool calls are found but
    the output looks like code and we expected write_file, auto-construct
    the tool call. This handles models that ignore tool-calling instructions.

    Args:
        text: Model output text to parse
        expected_tool: If set and no tool calls found, check if we should
                       auto-construct a call (e.g., "write_file")
        target_path: Target path for auto-constructed write_file calls

    Returns:
        (tool_calls, remaining_text) - tool calls found and text after them
    """
    tool_calls: list[ToolCall] = []
    remaining = text

    # Try to parse explicit tool call JSON
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

    # CODE DETECTION FALLBACK:
    # If no tool calls found, model might have output code directly.
    # Auto-construct a write_file call ONLY if we have a specific target_path.
    # Don't create generic "generated_code.py" - that's confusing and pollutes projects.
    if not tool_calls and expected_tool == "write_file" and target_path and _looks_like_code(text):
        code_content = _extract_code_from_markdown(text)
        if code_content:
            tool_calls.append(
                ToolCall(
                    id="auto_write_fallback",
                    name="write_file",
                    arguments={
                        "path": target_path,
                        "content": code_content,
                    },
                )
            )
            remaining = ""  # Consumed by the auto-constructed call

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

        # Check if write_file is one of the tools (for code detection fallback)
        has_write_file = any(t.name == "write_file" for t in tools)
        expected_tool = "write_file" if has_write_file else None

        # Parse tool calls from the text (with code detection fallback)
        if result.content:
            tool_calls, remaining_text = parse_tool_calls_from_text(
                result.content,
                expected_tool=expected_tool,
            )
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
