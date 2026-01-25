"""Version-aware model capability registry.

Provides accurate capability detection using structured model parsing
instead of brittle string prefix matching.

Key capabilities tracked:
- native_tools: Model supports structured tool/function calling
- parallel_tools: Model can call multiple tools in one turn
- tool_streaming: Model supports streaming tool call arguments
- json_mode: Model has reliable JSON output mode
- reasoning: Model supports extended thinking (o1, R1, etc.)
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sunwell.models.capability.parser import ModelSpec, parse_model_id


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """Capabilities for intelligent routing and adaptation.

    Attributes:
        native_tools: Model supports structured tool/function calling.
        parallel_tools: Model can call multiple tools in one turn.
        tool_streaming: Model supports streaming tool call arguments.
        json_mode: Model has reliable JSON output mode.
        reasoning: Model supports extended thinking (o1, DeepSeek-R1, etc.).
        max_output_tokens: Maximum output tokens for budget calculations.
        context_window: Maximum context window size.
        needs_tool_schema_strict: Anthropic-style strict schema validation.
        tool_result_in_user_message: Anthropic: tool results go in user message.
        supports_tool_choice_required: Model supports tool_choice: required.
        emulation_style: For non-native tools: 'json', 'xml', or 'markdown'.
    """

    native_tools: bool = False
    parallel_tools: bool = False
    tool_streaming: bool = False
    json_mode: bool = False
    reasoning: bool = False
    max_output_tokens: int | None = None
    context_window: int | None = None

    # Provider-specific quirks
    needs_tool_schema_strict: bool = False
    tool_result_in_user_message: bool = False
    supports_tool_choice_required: bool = True
    emulation_style: Literal["json", "xml", "markdown"] = "json"


# Type for capability matcher functions
CapabilityMatcher = Callable[[ModelSpec], ModelCapability | None]


def _match_gpt(spec: ModelSpec) -> ModelCapability | None:
    """Match GPT family capabilities."""
    if spec.family != "gpt":
        return None

    # GPT-4o variants (including mini)
    if spec.version >= (4,) and (spec.variant == "o" or spec.variant == "mini"):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            max_output_tokens=16384,
            context_window=128000,
        )

    # GPT-4 Turbo
    if spec.version >= (4,) and spec.variant == "turbo":
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=4096,
            context_window=128000,
        )

    # GPT-4 base
    if spec.version >= (4,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            max_output_tokens=8192,
            context_window=8192,
        )

    # GPT-3.5
    if spec.version >= (3, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=4096,
            context_window=16385,
        )

    return None


def _match_o_series(spec: ModelSpec) -> ModelCapability | None:
    """Match OpenAI o1/o3 reasoning models."""
    if not spec.family.startswith("o") or len(spec.family) < 2:
        return None

    # Check if it's o1, o3, etc. (o followed by digit)
    suffix = spec.family[1:]
    if not suffix.isdigit():
        return None

    return ModelCapability(
        native_tools=True,
        parallel_tools=True,
        reasoning=True,
        json_mode=True,
        max_output_tokens=100000,
        context_window=200000,
        # o1 doesn't support tool_choice: required during reasoning
        supports_tool_choice_required=False,
    )


def _match_claude(spec: ModelSpec) -> ModelCapability | None:
    """Match Claude family capabilities."""
    if spec.family != "claude":
        return None

    # Claude 4 (Opus 4, Sonnet 4)
    if spec.version >= (4,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=64000,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )

    # Claude 3.5 (Sonnet, Haiku)
    if spec.version >= (3, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )

    # Claude 3 (Opus, Sonnet, Haiku)
    if spec.version >= (3,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            max_output_tokens=4096,
            context_window=200000,
            needs_tool_schema_strict=True,
            tool_result_in_user_message=True,
        )

    return None


def _match_llama(spec: ModelSpec) -> ModelCapability | None:
    """Match Llama family capabilities."""
    if spec.family != "llama":
        return None

    # Llama 3.3 (70B+)
    if spec.version >= (3, 3):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,  # Llama struggles with parallel
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )

    # Llama 3.1/3.2
    if spec.version >= (3, 1):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )

    # Llama 3.0
    if spec.version >= (3,):
        size = spec.size or 8_000_000_000
        if size >= 70_000_000_000:
            return ModelCapability(
                native_tools=True,
                parallel_tools=False,
                max_output_tokens=4096,
                context_window=8192,
            )
        # Smaller Llama 3 models need emulation
        return ModelCapability(
            native_tools=False,
            json_mode=True,
            emulation_style="json",
        )

    # Llama 2 and earlier - use emulation
    return ModelCapability(
        native_tools=False,
        emulation_style="json",
    )


def _match_qwen(spec: ModelSpec) -> ModelCapability | None:
    """Match Qwen family capabilities."""
    if spec.family != "qwen":
        return None

    # Qwen 3
    if spec.version >= (3,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=128000,
        )

    # Qwen 2.5
    if spec.version >= (2, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=32768,
        )

    # Older Qwen - use emulation
    return ModelCapability(
        native_tools=False,
        json_mode=True,
        emulation_style="json",
    )


def _match_mistral(spec: ModelSpec) -> ModelCapability | None:
    """Match Mistral/Mixtral family capabilities."""
    if spec.family not in ("mistral", "mixtral"):
        return None

    # Mistral Large
    if spec.variant == "large":
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=128000,
        )

    # Mixtral (MoE models)
    if spec.family == "mixtral":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            max_output_tokens=4096,
            context_window=32768,
        )

    # Base Mistral
    return ModelCapability(
        native_tools=True,
        parallel_tools=False,
        max_output_tokens=4096,
        context_window=32768,
    )


def _match_gemini(spec: ModelSpec) -> ModelCapability | None:
    """Match Gemini family capabilities."""
    if spec.family != "gemini":
        return None

    # Gemini 2.0
    if spec.version >= (2,):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            tool_streaming=True,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=1000000,
        )

    # Gemini 1.5
    if spec.version >= (1, 5):
        return ModelCapability(
            native_tools=True,
            parallel_tools=True,
            json_mode=True,
            max_output_tokens=8192,
            context_window=1000000,
        )

    # Experimental or older
    return ModelCapability(
        native_tools=True,
        parallel_tools=True,
        json_mode=True,
        max_output_tokens=8192,
        context_window=32000,
    )


def _match_deepseek(spec: ModelSpec) -> ModelCapability | None:
    """Match DeepSeek family capabilities."""
    if spec.family != "deepseek":
        return None

    # DeepSeek R1 (reasoning)
    if spec.variant == "r1":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            reasoning=True,
            max_output_tokens=8192,
            context_window=64000,
            supports_tool_choice_required=False,  # Like o1, R1 has reasoning constraints
        )

    # DeepSeek V3
    if spec.variant == "v3":
        return ModelCapability(
            native_tools=True,
            parallel_tools=False,
            json_mode=True,
            max_output_tokens=8192,
            context_window=64000,
        )

    # DeepSeek coder and others
    return ModelCapability(
        native_tools=True,
        parallel_tools=False,
        json_mode=True,
        max_output_tokens=8192,
        context_window=32000,
    )


def _match_phi(spec: ModelSpec) -> ModelCapability | None:
    """Match Phi family capabilities."""
    if spec.family != "phi":
        return None

    # Phi-3.5 and later have improved tool use
    if spec.version >= (3, 5):
        return ModelCapability(
            native_tools=False,
            json_mode=True,
            max_output_tokens=4096,
            context_window=128000,
            emulation_style="json",
        )

    # Phi-3
    if spec.version >= (3,):
        return ModelCapability(
            native_tools=False,
            json_mode=True,
            max_output_tokens=4096,
            context_window=128000,
            emulation_style="json",
        )

    return ModelCapability(
        native_tools=False,
        emulation_style="json",
    )


# Models known to not support native tools
_NO_NATIVE_TOOLS = frozenset({
    "gemma",
    "codellama",
    "starcoder",
    "yi",
    "falcon",
    "vicuna",
    "wizardcoder",
})


def _match_no_tools(spec: ModelSpec) -> ModelCapability | None:
    """Match models known to not support native tools."""
    if spec.family in _NO_NATIVE_TOOLS:
        return ModelCapability(
            native_tools=False,
            json_mode=True,
            emulation_style="json",
        )
    return None


# Ordered list of matchers (first match wins)
_MATCHERS: list[CapabilityMatcher] = [
    _match_o_series,
    _match_gpt,
    _match_claude,
    _match_llama,
    _match_qwen,
    _match_mistral,
    _match_gemini,
    _match_deepseek,
    _match_phi,
    _match_no_tools,
]


def get_capability(model_id: str) -> ModelCapability:
    """Get capabilities for a model ID.

    Uses structured parsing + version-aware matchers for accurate routing.

    Args:
        model_id: Raw model identifier

    Returns:
        ModelCapability with appropriate settings
    """
    spec = parse_model_id(model_id)

    for matcher in _MATCHERS:
        result = matcher(spec)
        if result is not None:
            return result

    # Unknown model — conservative defaults
    # Custom/fine-tuned models inherit base model capabilities
    if spec.custom and spec.family != "unknown":
        # Try to match the base family with extracted version
        base_spec = ModelSpec(family=spec.family, version=spec.version)
        for matcher in _MATCHERS:
            result = matcher(base_spec)
            if result is not None:
                return result

    # Truly unknown — assume no native tools, use JSON emulation
    return ModelCapability(
        native_tools=False,
        emulation_style="json",
    )
