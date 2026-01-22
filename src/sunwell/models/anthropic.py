"""Anthropic (Claude) model adapter with tool calling support (RFC-012)."""


from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from sunwell.core.errors import from_anthropic_error
from sunwell.models.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    TokenUsage,
    Tool,
    ToolCall,
    _sanitize_dict_values,
    sanitize_llm_content,
)

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic


@dataclass
class AnthropicModel:
    """Anthropic Claude model adapter with tool calling support.

    Requires: pip install sunwell[anthropic]

    Supports:
    - Standard text generation
    - Multi-turn conversations via Message tuples
    - Tool calling per RFC-012 (using Anthropic's tool_use blocks)
    """

    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None
    max_tokens: int = 4096
    _client: AsyncAnthropic | None = field(default=None, init=False)

    @property
    def model_id(self) -> str:
        return self.model

    def _get_client(self) -> AsyncAnthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as e:
                raise ImportError(
                    "Anthropic not installed. Run: pip install sunwell[anthropic]"
                ) from e

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _convert_messages(
        self,
        prompt: str | tuple[Message, ...],
    ) -> tuple[list[dict], str | None]:
        """Convert prompt to Anthropic message format.

        Returns:
            Tuple of (messages list, system prompt or None)
        """
        system_prompt = None
        messages = []

        if isinstance(prompt, str):
            # Simple string prompt
            messages.append({"role": "user", "content": prompt})
        else:
            # Multi-turn conversation
            for msg in prompt:
                if msg.role == "system":
                    # Anthropic uses a separate system parameter
                    system_prompt = msg.content
                elif msg.role == "user":
                    messages.append({"role": "user", "content": msg.content or ""})
                elif msg.role == "assistant":
                    # Build content blocks for assistant message
                    content_blocks = []
                    if msg.content:
                        content_blocks.append({"type": "text", "text": msg.content})
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                    if content_blocks:
                        messages.append({"role": "assistant", "content": content_blocks})
                elif msg.role == "tool":
                    # Tool result goes in a user message with tool_result block
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or "",
                            }
                        ],
                    })

        return messages, system_prompt

    def _convert_tools(self, tools: tuple[Tool, ...] | None) -> list[dict] | None:
        """Convert Sunwell tools to Anthropic tool format."""
        if not tools:
            return None

        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _convert_tool_choice(
        self,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> dict | None:
        """Convert tool_choice to Anthropic format."""
        if tool_choice is None:
            return None

        if isinstance(tool_choice, dict):
            # Pass through provider-specific format
            return tool_choice

        if tool_choice == "auto":
            return {"type": "auto"}
        elif tool_choice == "none":
            # Anthropic doesn't have "none" - just don't send tools
            return None
        elif tool_choice == "required":
            return {"type": "any"}
        else:
            # Assume it's a tool name - force that specific tool
            return {"type": "tool", "name": tool_choice}

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response using Claude.

        Supports both simple prompts and multi-turn conversations with tools.
        """
        client = self._get_client()
        opts = options or GenerateOptions()

        messages, extracted_system = self._convert_messages(prompt)

        kwargs: dict = {
            "model": self.model,
            "max_tokens": opts.max_tokens or self.max_tokens,
            "messages": messages,
        }

        # System prompt from options takes precedence
        system = opts.system_prompt or extracted_system
        if system:
            kwargs["system"] = system

        if opts.temperature != 0.7:
            kwargs["temperature"] = opts.temperature

        if opts.stop_sequences:
            kwargs["stop_sequences"] = list(opts.stop_sequences)

        # Add tools if provided
        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

            converted_choice = self._convert_tool_choice(tool_choice)
            if converted_choice:
                kwargs["tool_choice"] = converted_choice

        try:
            response = await client.messages.create(**kwargs)
        except Exception as e:
            raise from_anthropic_error(e, self.model) from e

        # Parse response content blocks (with sanitization per RFC-091)
        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = sanitize_llm_content(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=_sanitize_dict_values(block.input),
                ))

        return GenerateResult(
            content=content,
            model=response.model,
            tool_calls=tuple(tool_calls),
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            finish_reason=response.stop_reason,
        )

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response using Claude.

        Note: Tool calls are not yielded during streaming.
        Use generate() for complete tool call handling.
        """
        client = self._get_client()
        opts = options or GenerateOptions()

        messages, extracted_system = self._convert_messages(prompt)

        kwargs: dict = {
            "model": self.model,
            "max_tokens": opts.max_tokens or self.max_tokens,
            "messages": messages,
        }

        system = opts.system_prompt or extracted_system
        if system:
            kwargs["system"] = system

        if opts.temperature != 0.7:
            kwargs["temperature"] = opts.temperature

        # Add tools if provided
        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield sanitize_llm_content(text) or ""
        except Exception as e:
            raise from_anthropic_error(e, self.model) from e

    async def list_models(self) -> list[str]:
        """List commonly used Anthropic models (no direct API available)."""
        return [
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
