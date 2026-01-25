"""OpenAI model adapter with tool calling support (RFC-012)."""


import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from sunwell.foundation.errors import ErrorCode, SunwellError, from_openai_error
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
    from openai import AsyncOpenAI


@dataclass(slots=True)
class OpenAIModel:
    """OpenAI GPT model adapter with tool/function calling support.

    Requires: pip install sunwell[openai]

    Supports:
    - Standard text generation
    - Multi-turn conversations via Message tuples
    - Tool/function calling per RFC-012
    """

    model: str = "gpt-4o"
    api_key: str | None = None
    _client: AsyncOpenAI | None = field(default=None, init=False)

    @property
    def model_id(self) -> str:
        return self.model

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise ImportError(
                    "OpenAI not installed. Run: pip install sunwell[openai]"
                ) from e

            # Check for API key BEFORE creating client (gives clear error)
            if not self.api_key:
                raise SunwellError(
                    code=ErrorCode.CONFIG_ENV_MISSING,
                    context={
                        "var": "OPENAI_API_KEY",
                        "provider": "openai",
                        "flag": "provider ollama",
                    },
                )

            try:
                self._client = AsyncOpenAI(api_key=self.api_key)
            except Exception as e:
                raise from_openai_error(e, self.model, "openai") from e

        return self._client

    def _convert_messages(
        self,
        prompt: str | tuple[Message, ...],
        system_prompt: str | None = None,
    ) -> list[dict]:
        """Convert prompt to OpenAI message format.

        Handles both simple string prompts and multi-turn Message tuples.
        """
        messages = []

        if isinstance(prompt, str):
            # Simple string prompt
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        else:
            # Multi-turn conversation
            for msg in prompt:
                if msg.role == "system":
                    messages.append({"role": "system", "content": msg.content or ""})
                elif msg.role == "user":
                    messages.append({"role": "user", "content": msg.content or ""})
                elif msg.role == "assistant":
                    assistant_msg: dict = {"role": "assistant"}
                    if msg.content:
                        assistant_msg["content"] = msg.content
                    if msg.tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in msg.tool_calls
                        ]
                    messages.append(assistant_msg)
                elif msg.role == "tool":
                    messages.append({
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content or "",
                    })

        return messages

    def _convert_tools(self, tools: tuple[Tool, ...] | None) -> list[dict] | None:
        """Convert Sunwell tools to OpenAI function format."""
        if not tools:
            return None

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

    def _convert_tool_choice(
        self,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None,
    ) -> str | dict | None:
        """Convert tool_choice to OpenAI format."""
        if tool_choice is None:
            return None

        if isinstance(tool_choice, dict):
            # Pass through provider-specific format
            return tool_choice

        if tool_choice in ("auto", "none", "required"):
            return tool_choice

        # Assume it's a tool name - force that specific tool
        return {"type": "function", "function": {"name": tool_choice}}

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response using OpenAI.

        Supports both simple prompts and multi-turn conversations with tools.
        """
        client = self._get_client()
        opts = options or GenerateOptions()

        messages = self._convert_messages(prompt, opts.system_prompt)

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": opts.temperature,
        }

        if opts.max_tokens:
            kwargs["max_tokens"] = opts.max_tokens

        if opts.stop_sequences:
            kwargs["stop"] = list(opts.stop_sequences)

        # Add tools if provided
        openai_tools = self._convert_tools(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools

            converted_choice = self._convert_tool_choice(tool_choice)
            if converted_choice:
                kwargs["tool_choice"] = converted_choice

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            raise from_openai_error(e, self.model, "openai") from e

        message = response.choices[0].message
        content = sanitize_llm_content(message.content)  # RFC-091: Sanitize at source
        usage = response.usage

        # Parse tool calls if present (with sanitized arguments)
        tool_calls: tuple[ToolCall, ...] = ()
        if message.tool_calls:
            tool_calls = tuple(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_sanitize_dict_values(json.loads(tc.function.arguments)),
                )
                for tc in message.tool_calls
            )

        return GenerateResult(
            content=content,
            model=response.model,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ) if usage else None,
            finish_reason=response.choices[0].finish_reason,
        )

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response using OpenAI.

        Note: Tool calls are accumulated but not yielded during streaming.
        Use generate() for complete tool call handling.
        """
        client = self._get_client()
        opts = options or GenerateOptions()

        messages = self._convert_messages(prompt, opts.system_prompt)

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": opts.temperature,
            "stream": True,
        }

        if opts.max_tokens:
            kwargs["max_tokens"] = opts.max_tokens

        # Add tools if provided
        openai_tools = self._convert_tools(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools

        try:
            stream = await client.chat.completions.create(**kwargs)
        except Exception as e:
            raise from_openai_error(e, self.model, "openai") from e

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield sanitize_llm_content(chunk.choices[0].delta.content) or ""

    async def list_models(self) -> list[str]:
        """List available models via OpenAI API."""
        client = self._get_client()
        response = await client.models.list()
        return [m.id for m in response.data]
