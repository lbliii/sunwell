"""Mock model for testing with tool calling support (RFC-012)."""


from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from sunwell.models.core.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    Tool,
    sanitize_llm_content,
)


@dataclass(slots=True)
class MockModel:
    """Mock model for testing.

    Returns predefined responses or echoes the prompt.
    Supports tool calling for test scenarios.
    """

    responses: list[str] = field(default_factory=list)
    _call_count: int = field(default=0, init=False)
    _prompts: list[str] = field(default_factory=list, init=False)

    @property
    def model_id(self) -> str:
        return "mock-model"

    @property
    def call_count(self) -> int:
        """Number of times generate was called."""
        return self._call_count

    @property
    def prompts(self) -> list[str]:
        """All prompts received."""
        return self._prompts

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a mock response."""
        # Extract prompt text
        if isinstance(prompt, str):
            prompt_text = prompt
        else:
            prompt_text = "\n".join(
                m.content or "" for m in prompt if m.role in ("user", "system")
            )

        self._prompts.append(prompt_text)
        self._call_count += 1

        if self.responses:
            response = self.responses[(self._call_count - 1) % len(self.responses)]
        else:
            response = f"Mock response to: {prompt_text[:50]}..."

        # RFC-091: Sanitize for test parity with real models
        sanitized_response = sanitize_llm_content(response)

        return GenerateResult(
            content=sanitized_response,
            model=self.model_id,
            tool_calls=(),
            usage=TokenUsage(
                prompt_tokens=len(prompt_text.split()),
                completion_tokens=len(response.split()),
                total_tokens=len(prompt_text.split()) + len(response.split()),
            ),
            finish_reason="stop",
        )

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a mock response."""
        result = await self.generate(prompt, tools=tools, options=options)
        words = result.text.split()
        for word in words:
            yield word + " "


@dataclass(slots=True)
class MockModelWithTools:
    """Mock model with configurable tool call responses.

    Use this for testing tool calling scenarios. Provide a sequence
    of GenerateResult objects that will be returned in order.

    Example:
        mock = MockModelWithTools([
            GenerateResult(
                content=None,
                model="mock",
                tool_calls=(ToolCall(id="1", name="read_file", arguments={"path": "x.txt"}),),
            ),
            GenerateResult(content="Done reading!", model="mock"),
        ])
    """

    responses: list[GenerateResult] = field(default_factory=list)
    _call_count: int = field(default=0, init=False)
    _prompts: list[str | tuple[Message, ...]] = field(default_factory=list, init=False)
    _tools_provided: list[tuple[Tool, ...] | None] = field(default_factory=list, init=False)

    @property
    def model_id(self) -> str:
        return "mock-model-with-tools"

    @property
    def call_count(self) -> int:
        """Number of times generate was called."""
        return self._call_count

    @property
    def prompts(self) -> list[str | tuple[Message, ...]]:
        """All prompts received."""
        return self._prompts

    @property
    def tools_provided(self) -> list[tuple[Tool, ...] | None]:
        """Tools provided in each call."""
        return self._tools_provided

    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | dict | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Return the next pre-configured response."""
        self._prompts.append(prompt)
        self._tools_provided.append(tools)
        self._call_count += 1

        if self.responses:
            result = self.responses[(self._call_count - 1) % len(self.responses)]
            return result

        # Default: simple text response
        prompt_text = prompt if isinstance(prompt, str) else str(prompt)
        return GenerateResult(
            content=f"Mock response #{self._call_count}",
            model=self.model_id,
            usage=TokenUsage(
                prompt_tokens=len(prompt_text.split()),
                completion_tokens=3,
                total_tokens=len(prompt_text.split()) + 3,
            ),
        )

    async def generate_stream(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a mock response (ignores tool calls)."""
        result = await self.generate(prompt, tools=tools, options=options)
        words = result.text.split()
        for word in words:
            yield word + " "


# Verify MockModel implements ModelProtocol
def _verify_protocol() -> None:
    model: ModelProtocol = MockModel()
    assert isinstance(model, ModelProtocol)

    model_with_tools: ModelProtocol = MockModelWithTools()
    assert isinstance(model_with_tools, ModelProtocol)
