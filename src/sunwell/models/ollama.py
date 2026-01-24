"""Ollama model adapter with native and OpenAI-compatible API support.

Ollama exposes:
- Native API at http://localhost:11434/api (better system prompt override)
- OpenAI-compatible API at http://localhost:11434/v1

The native API's /api/generate endpoint has an explicit `system` field that
properly overrides the model's built-in system prompt. This is more reliable
than the OpenAI-compatible /v1/chat endpoint for identity enforcement.

See: https://docs.ollama.com/api/generate
"""


import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from sunwell.core.errors import from_openai_error
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
    import httpx
    from openai import AsyncOpenAI


@dataclass
class OllamaModel:
    """Ollama model adapter with native API support for better system prompts.

    Requires: pip install sunwell[ollama] (or just openai>=1.0)

    Ollama must be running locally: ollama serve

    Usage:
        model = OllamaModel(model="gemma3:1b")
        result = await model.generate("Hello!")

    For better system prompt handling (identity enforcement):
        model = OllamaModel(model="gemma3:1b", use_native_api=True)

    For high parallelism (requires OLLAMA_NUM_PARALLEL >= connections):
        model = OllamaModel(
            model="gemma3:1b",
            max_connections=8,  # Match your OLLAMA_NUM_PARALLEL
        )
    """

    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434/v1"
    use_native_api: bool = False  # Use /api/generate instead of /v1/chat for better system prompts
    max_connections: int = 10  # Connection pool size for parallel requests
    request_timeout: float = 120.0  # Request timeout in seconds
    _client: AsyncOpenAI | None = field(default=None, init=False)
    _httpx_client: httpx.AsyncClient | None = field(default=None, init=False)

    @property
    def model_id(self) -> str:
        return f"ollama/{self.model}"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client configured for Ollama.

        Configures connection pooling for better parallel request throughput.
        """
        if self._client is None:
            try:
                import httpx
                from openai import AsyncOpenAI
            except ImportError as e:
                raise ImportError(
                    "OpenAI client not installed. Run: pip install openai>=1.0"
                ) from e

            # Configure connection pool for parallel requests
            # This allows multiple concurrent requests to the same Ollama server
            limits = httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_connections,
            )
            timeout = httpx.Timeout(
                timeout=self.request_timeout,
                connect=10.0,
            )

            # Create custom httpx client with connection pooling
            http_client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
            )

            # Ollama doesn't need an API key, but OpenAI client requires one
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key="ollama",  # Placeholder - Ollama ignores this
                http_client=http_client,
            )
        return self._client

    def _get_httpx_client(self) -> httpx.AsyncClient:
        """Get or create httpx client for native API calls."""
        if self._httpx_client is None:
            import httpx

            limits = httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_connections,
            )
            timeout = httpx.Timeout(
                timeout=self.request_timeout,
                connect=10.0,
            )

            self._httpx_client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
            )
        return self._httpx_client

    def _convert_messages(
        self,
        prompt: str | tuple[Message, ...],
        system_prompt: str | None = None,
    ) -> list[dict]:
        """Convert prompt to OpenAI message format."""
        messages = []

        if isinstance(prompt, str):
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        else:
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
        """Convert Sunwell tools to OpenAI/Ollama function format."""
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
        """Convert tool_choice to OpenAI/Ollama format."""
        if tool_choice is None:
            return None

        if isinstance(tool_choice, dict) or tool_choice in ("auto", "none", "required"):
            return tool_choice

        # Force specific tool
        return {"type": "function", "function": {"name": tool_choice}}

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response using Ollama.

        Raises:
            SunwellError: On API errors with structured error info for recovery
        """
        client = self._get_client()
        opts = options or GenerateOptions()

        # Merge tools from parameter and options
        effective_tools = tools or opts.tools

        # Check if model supports native tools - if not, use emulation
        if effective_tools:
            from sunwell.runtime.model_router import get_model_capability

            cap = get_model_capability(self.model)
            if cap and not cap.tools:
                # Use JSON emulation for tool calling
                from sunwell.models.tool_emulator import ToolEmulatorModel

                emulator = ToolEmulatorModel(inner_model=self)
                # Delegate to emulator (but don't pass tools to avoid recursion)
                return await emulator.generate(
                    prompt, tools=effective_tools, tool_choice=tool_choice, options=opts
                )

        messages = self._convert_messages(prompt, opts.system_prompt)

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": opts.temperature,
        }

        # Pass tools to Ollama
        converted_tools = self._convert_tools(effective_tools)
        if converted_tools:
            kwargs["tools"] = converted_tools
            if tool_choice:
                kwargs["tool_choice"] = self._convert_tool_choice(tool_choice)

        if opts.max_tokens:
            kwargs["max_tokens"] = opts.max_tokens

        if opts.stop_sequences:
            kwargs["stop"] = list(opts.stop_sequences)

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            # Translate to structured SunwellError
            raise from_openai_error(e, self.model, "ollama") from e

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
            model=self.model,
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
        """Stream a response using Ollama.

        If use_native_api=True, uses /api/generate with explicit system override.
        Otherwise uses OpenAI-compatible /v1/chat/completions.
        """
        if self.use_native_api:
            async for chunk in self._generate_stream_native(prompt, options=options):
                yield chunk
        else:
            async for chunk in self._generate_stream_openai(prompt, options=options):
                yield chunk

    async def _generate_stream_openai(
        self,
        prompt: str | tuple[Message, ...],
        *,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream using OpenAI-compatible API."""
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

        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield sanitize_llm_content(chunk.choices[0].delta.content) or ""

    async def _generate_stream_native(
        self,
        prompt: str | tuple[Message, ...],
        *,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream using native Ollama /api/generate with explicit system override.

        The native API's `system` field properly overrides the model's built-in
        system prompt, which is more reliable for identity enforcement.

        See: https://docs.ollama.com/api/generate
        """
        opts = options or GenerateOptions()
        native_url = self.base_url.replace("/v1", "/api/generate")

        # Extract system prompt and build user prompt from messages
        system_prompt = ""
        user_prompt = ""

        if isinstance(prompt, str):
            user_prompt = prompt
            system_prompt = opts.system_prompt or ""
        else:
            # Extract system message and concatenate user/assistant messages
            # NOTE: Do NOT use "Assistant:" prefix - models will echo it infinitely
            parts = []
            for msg in prompt:
                if msg.role == "system":
                    system_prompt = msg.content or ""
                elif msg.role == "user":
                    parts.append(f"[USER]\n{msg.content}")
                elif msg.role == "assistant":
                    parts.append(f"[RESPONSE]\n{msg.content}")
            user_prompt = "\n\n".join(parts) if parts else ""

        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "stream": True,
        }

        # Explicit system override - this is the key difference
        if system_prompt:
            payload["system"] = system_prompt

        # Add stop sequences to prevent role echoing
        payload["options"] = payload.get("options", {})
        payload["options"]["stop"] = ["[USER]", "[RESPONSE]"]

        if opts.temperature is not None:
            payload["options"]["temperature"] = opts.temperature

        # Use pooled client for better parallelism
        client = self._get_httpx_client()
        async with client.stream("POST", native_url, json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield sanitize_llm_content(data["response"]) or ""
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> list[str]:
        """List available models in local Ollama instance."""
        client = self._get_client()
        try:
            response = await client.models.list()
            return [m.id for m in response.data]
        except Exception:
            # Fallback if OpenAI-compatible models list fails
            return [self.model]
