"""Session cost tracking for token and dollar budgets.

Tracks model costs across a session for budget monitoring and reporting.
Local models are tracked as free (zero cost).

Example:
    >>> tracker = SessionCostTracker(session_id="sess-123", budget_usd=1.0)
    >>> tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)
    >>> print(tracker.summary())
    {'total_cost_usd': 0.0125, 'total_tokens': 1500, ...}
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelCost:
    """Per-model cost configuration (USD per 1K tokens).

    Attributes:
        input_per_1k: Cost per 1K input tokens
        output_per_1k: Cost per 1K output tokens
        cache_read_per_1k: Cost per 1K cached input tokens (if applicable)
        cache_write_per_1k: Cost per 1K cache write tokens (if applicable)
    """

    input_per_1k: float = 0.0
    output_per_1k: float = 0.0
    cache_read_per_1k: float = 0.0
    cache_write_per_1k: float = 0.0


# Common model costs (as of 2026)
# Note: Local models are free (zero cost)
MODEL_COSTS: dict[str, ModelCost] = {
    # OpenAI
    "gpt-4o": ModelCost(input_per_1k=0.005, output_per_1k=0.015),
    "gpt-4o-mini": ModelCost(input_per_1k=0.00015, output_per_1k=0.0006),
    "gpt-4-turbo": ModelCost(input_per_1k=0.01, output_per_1k=0.03),
    "gpt-3.5-turbo": ModelCost(input_per_1k=0.0005, output_per_1k=0.0015),
    # Anthropic
    "claude-3-5-sonnet": ModelCost(input_per_1k=0.003, output_per_1k=0.015),
    "claude-3-5-haiku": ModelCost(input_per_1k=0.0008, output_per_1k=0.004),
    "claude-3-opus": ModelCost(input_per_1k=0.015, output_per_1k=0.075),
    # Google
    "gemini-1.5-pro": ModelCost(input_per_1k=0.00125, output_per_1k=0.005),
    "gemini-1.5-flash": ModelCost(input_per_1k=0.000075, output_per_1k=0.0003),
    # Local (free)
    "llama-local": ModelCost(),
    "llama3": ModelCost(),
    "llama3.1": ModelCost(),
    "mistral-local": ModelCost(),
    "mistral": ModelCost(),
    "codellama": ModelCost(),
    "deepseek-coder": ModelCost(),
    "qwen2.5-coder": ModelCost(),
}


def get_model_cost(model_name: str) -> ModelCost:
    """Get cost configuration for a model.

    Args:
        model_name: Model identifier

    Returns:
        ModelCost configuration (defaults to free if unknown)
    """
    # Normalize model name (lowercase, strip version suffixes for matching)
    normalized = model_name.lower()

    # Direct match
    if normalized in MODEL_COSTS:
        return MODEL_COSTS[normalized]

    # Partial match (e.g., "gpt-4o-2024-08-06" matches "gpt-4o")
    for key in MODEL_COSTS:
        if normalized.startswith(key):
            return MODEL_COSTS[key]

    # Default to free (local model assumption)
    return ModelCost()


@dataclass(frozen=True, slots=True)
class CostEntry:
    """Single cost tracking entry.

    Attributes:
        timestamp: When the call was made
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_usd: Calculated cost in USD
        operation: Type of operation (generate, embed, etc.)
    """

    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    operation: str


@dataclass
class SessionCostTracker:
    """Tracks costs across a session.

    Attributes:
        session_id: Unique session identifier
        budget_usd: Optional budget limit in USD
    """

    session_id: str
    budget_usd: float | None = None

    _entries: list[CostEntry] = field(default_factory=list, init=False)

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "generate",
    ) -> CostEntry:
        """Record a model call and its cost.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation: Type of operation

        Returns:
            CostEntry with calculated cost
        """
        cost_config = get_model_cost(model)
        cost_usd = (
            (input_tokens / 1000) * cost_config.input_per_1k +
            (output_tokens / 1000) * cost_config.output_per_1k
        )

        entry = CostEntry(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            operation=operation,
        )
        self._entries.append(entry)
        return entry

    @property
    def total_cost_usd(self) -> float:
        """Total cost in USD."""
        return sum(e.cost_usd for e in self._entries)

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return sum(e.input_tokens + e.output_tokens for e in self._entries)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens used."""
        return sum(e.input_tokens for e in self._entries)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens used."""
        return sum(e.output_tokens for e in self._entries)

    @property
    def budget_remaining(self) -> float | None:
        """Remaining budget in USD (None if no budget set)."""
        if self.budget_usd is None:
            return None
        return max(0.0, self.budget_usd - self.total_cost_usd)

    @property
    def budget_percentage_used(self) -> float | None:
        """Percentage of budget used (None if no budget set)."""
        if self.budget_usd is None or self.budget_usd == 0:
            return None
        return min(100.0, (self.total_cost_usd / self.budget_usd) * 100)

    @property
    def is_over_budget(self) -> bool:
        """Whether total cost exceeds budget."""
        if self.budget_usd is None:
            return False
        return self.total_cost_usd >= self.budget_usd

    @property
    def call_count(self) -> int:
        """Number of model calls recorded."""
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        """Get summary of session costs.

        Returns:
            Dictionary with cost statistics
        """
        return {
            "session_id": self.session_id,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "call_count": self.call_count,
            "budget_usd": self.budget_usd,
            "budget_remaining": (
                round(self.budget_remaining, 6) if self.budget_remaining is not None else None
            ),
            "budget_percentage_used": (
                round(self.budget_percentage_used, 1) if self.budget_percentage_used is not None else None
            ),
            "is_over_budget": self.is_over_budget,
        }

    def cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model.

        Returns:
            Dictionary of model -> total cost
        """
        costs: dict[str, float] = {}
        for entry in self._entries:
            costs[entry.model] = costs.get(entry.model, 0.0) + entry.cost_usd
        return costs

    def reset(self) -> None:
        """Reset all tracked entries."""
        self._entries = []
