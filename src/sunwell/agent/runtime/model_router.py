"""Model routing logic - automatically picks the best model for the task.

RFC-015: Adaptive Model Selection
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.foundation.errors import tools_not_supported
from sunwell.core.types.types import Tier
from sunwell.models import ModelProtocol

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """Represents the capabilities of a specific model."""
    name: str
    tier: Tier
    tools: bool = False
    streaming: bool = True
    context_window: int = 8192
    cost_index: int = 1  # 1-10 (1=cheapest, 10=most expensive)


# Known model capabilities (for routing)
# 2-Tier Architecture: classifier (1b) + worker (20b)
# Middle-tier models (4b-12b) removed - quality gap not worth latency savings
MODEL_REGISTRY: dict[str, ModelCapability] = {
    # ==========================================================================
    # PRIMARY: 2-Tier Local Stack (Recommended)
    # ==========================================================================
    # Tier 0: Classifier - routing, classification, trivial answers
    "gemma3:1b": ModelCapability("gemma3:1b", Tier.FAST_PATH, tools=False, context_window=8192, cost_index=0),

    # Tier 1+2: Worker - generation, judging, complex reasoning (merged)
    "gpt-oss:20b": ModelCapability("gpt-oss:20b", Tier.DEEP_LENS, tools=False, context_window=128000, cost_index=0),

    # ==========================================================================
    # CLOUD: For burst capacity or when local unavailable
    # ==========================================================================
    # OpenAI
    "gpt-4o": ModelCapability("gpt-4o", Tier.DEEP_LENS, tools=True, context_window=128000, cost_index=8),
    "gpt-4o-mini": ModelCapability("gpt-4o-mini", Tier.STANDARD, tools=True, context_window=128000, cost_index=2),
    "o1-preview": ModelCapability("o1-preview", Tier.DEEP_LENS, tools=True, context_window=128000, cost_index=10),

    # Anthropic
    "claude-3-5-sonnet-20240620": ModelCapability("claude-3-5-sonnet", Tier.DEEP_LENS, tools=True, context_window=200000, cost_index=7),
    "claude-3-opus-20240229": ModelCapability("claude-3-opus", Tier.DEEP_LENS, tools=True, context_window=200000, cost_index=9),
    "claude-3-haiku-20240307": ModelCapability("claude-3-haiku", Tier.STANDARD, tools=True, context_window=200000, cost_index=1),

    # ==========================================================================
    # Deprecated models (not recommended for new setups)
    # ==========================================================================
    "gemma3:4b": ModelCapability("gemma3:4b", Tier.STANDARD, tools=False, context_window=128000, cost_index=0),
    "gemma3:12b": ModelCapability("gemma3:12b", Tier.DEEP_LENS, tools=False, context_window=128000, cost_index=0),
    "gemma2:9b": ModelCapability("gemma2:9b", Tier.STANDARD, tools=False, context_window=8192, cost_index=0),
    "llama3:8b": ModelCapability("llama3:8b", Tier.STANDARD, tools=True, context_window=8192, cost_index=0),
    "llama3.1:8b": ModelCapability("llama3.1:8b", Tier.STANDARD, tools=True, context_window=128000, cost_index=0),
    "llama3.2:3b": ModelCapability("llama3.2:3b", Tier.FAST_PATH, tools=True, context_window=128000, cost_index=0),
    "llama3:70b": ModelCapability("llama3:70b", Tier.DEEP_LENS, tools=True, context_window=8192, cost_index=0),
    "qwen2.5:7b": ModelCapability("qwen2.5:7b", Tier.STANDARD, tools=True, context_window=32000, cost_index=0),
    "mistral:7b": ModelCapability("mistral:7b", Tier.STANDARD, tools=True, context_window=32000, cost_index=0),
}

# Pre-built prefix index for O(1) lookups of model families
_MODEL_PREFIX_INDEX: dict[str, ModelCapability] = {}
for _key, _cap in MODEL_REGISTRY.items():
    _prefix = _key.split(":")[0]
    if _prefix not in _MODEL_PREFIX_INDEX:
        _MODEL_PREFIX_INDEX[_prefix] = _cap


def get_model_capability(model_name: str) -> ModelCapability | None:
    """Look up model capability from registry.

    Args:
        model_name: The model name (e.g., "gemma3:1b", "gpt-4o")

    Returns:
        ModelCapability if found, None if unknown model
    """
    # Direct lookup - O(1)
    if model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name]

    # Prefix lookup - O(1) via pre-built index
    base_name = model_name.split(":")[0]
    return _MODEL_PREFIX_INDEX.get(base_name)


def supports_tools(model_name: str) -> bool:
    """Check if a model supports tool calling.

    Args:
        model_name: The model name

    Returns:
        True if model supports tools, False if not or unknown
    """
    cap = get_model_capability(model_name)
    return cap.tools if cap else False


def check_tools_support(model_name: str, provider: str = "unknown") -> None:
    """Raise SunwellError if model doesn't support tools.

    Args:
        model_name: The model name
        provider: The provider name for error context

    Raises:
        SunwellError: If model is known to not support tools
    """
    cap = get_model_capability(model_name)
    if cap and not cap.tools:
        raise tools_not_supported(model_name, provider)


def get_tools_fallback(model_name: str, available_models: list[str] | None = None) -> str | None:
    """Get a fallback model that supports tools.

    Args:
        model_name: Current model that doesn't support tools
        available_models: List of available models to choose from

    Returns:
        A model name that supports tools, or None if no fallback available
    """
    # Filter to models that support tools
    candidates = []

    if available_models:
        for m in available_models:
            cap = get_model_capability(m)
            if cap and cap.tools:
                candidates.append((m, cap))
    else:
        # Use registry
        candidates = [(name, cap) for name, cap in MODEL_REGISTRY.items() if cap.tools]

    if not candidates:
        return None

    # Sort by cost (cheapest first)
    candidates.sort(key=lambda x: x[1].cost_index)
    return candidates[0][0]


@dataclass(slots=True)
class ModelRouter:
    """Orchestrates model selection based on task complexity and availability."""

    primary_model: ModelProtocol
    stupid_model: ModelProtocol | None = None
    lens: Lens | None = None

    async def route(self, prompt: str, tier: Tier | None = None, requires_tools: bool = False) -> str:
        """Determines the best model name for the task.

        Args:
            prompt: The user's request
            tier: Optional forced tier
            requires_tools: If True, only models that support tool calling are returned.

        Returns:
            The recommended model ID string
        """
        # 1. Use stupid model to classify if available and no tier forced
        if self.stupid_model and tier is None:
            tier = await self._classify_with_stupid_model(prompt)

        # 2. Get available models from the provider
        available = await self.primary_model.list_models()

        # 3. Filter registry to only available models that meet tool requirements
        candidates = [
            MODEL_REGISTRY[m] for m in available
            if m in MODEL_REGISTRY
        ]

        if requires_tools:
            candidates = [c for c in candidates if c.tools]

        if not candidates:
            # Fallback to whatever we have
            return self.primary_model.model_id

        # 4. Pick the best model for the tier
        # Sort by tier desc, then cost index (cheapest first for that tier)
        tier_val = tier.value if tier else Tier.STANDARD.value

        # Exact match tier if possible
        tier_matches = [c for c in candidates if c.tier.value == tier_val]
        if tier_matches:
            # Pick cheapest in that tier
            return min(tier_matches, key=lambda c: c.cost_index).name

        # If no exact tier match, pick the closest one upwards
        better_matches = [c for c in candidates if c.tier.value > tier_val]
        if better_matches:
            return min(better_matches, key=lambda c: (c.tier.value, c.cost_index)).name

        # Last resort: pick the most capable available
        return max(candidates, key=lambda c: (c.tier.value, -c.cost_index)).name

    async def _classify_with_stupid_model(self, prompt: str) -> Tier:
        """Use a small, fast model to determine the task complexity."""
        if not self.stupid_model:
            return Tier.STANDARD

        classification_prompt = f"""Classify the complexity of this user request into one of:
- TRIVIAL: Simple greetings, typos, or one-word answers.
- STANDARD: General questions, writing short emails, basic facts.
- COMPLEX: Architecture design, security audits, multi-file refactoring, deep analysis.

User Request: "{prompt[:500]}"

Respond with exactly one word: TRIVIAL, STANDARD, or COMPLEX."""

        try:
            result = await self.stupid_model.generate(classification_prompt)
            text = result.text.upper().strip()

            if "TRIVIAL" in text:
                return Tier.FAST_PATH
            if "COMPLEX" in text:
                return Tier.DEEP_LENS
            return Tier.STANDARD
        except Exception:
            return Tier.STANDARD
