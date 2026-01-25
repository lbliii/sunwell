"""Budget-aware technique selection (RFC-042).

The adaptive system automatically downgrades techniques when budget is tight:
- Vortex (15x) → Interference (3x) → Single-shot (1x)
- Harmonic 5 (6x) → Harmonic 3 (3.5x) → Single-shot (1x)
- Compound Eye (5x) → Lateral only (2x)

Budget tracking ensures we don't exceed token limits while
maximizing technique power within constraints.
"""

from dataclasses import dataclass
from typing import Literal

# Default cost multipliers (relative to single-shot) — single source of truth
DEFAULT_TECHNIQUE_MULTIPLIERS: dict[str, float] = {
    "single_shot": 1.0,
    "interference": 3.0,
    "harmonic_3": 3.5,
    "harmonic_5": 6.0,
    "vortex": 15.0,
    "compound_eye": 5.0,
    "lateral_only": 2.0,
    "resonance": 2.0,
}


@dataclass
class AdaptiveBudget:
    """Token budget with automatic economization.

    Tracks spending and provides route recommendations
    that respect budget constraints.
    """

    total_budget: int = 50_000
    """Total token budget for the run."""

    spent: int = 0
    """Tokens spent so far."""

    reserve_ratio: float = 0.2
    """Fraction of budget reserved for fixes."""

    # Cost multipliers (relative to single-shot)
    single_shot: float = 1.0
    interference: float = 3.0
    harmonic_3: float = 3.5
    harmonic_5: float = 6.0
    vortex: float = 15.0
    compound_eye: float = 5.0
    resonance_per_loop: float = 2.0

    @property
    def remaining(self) -> int:
        """Remaining budget."""
        return max(0, self.total_budget - self.spent)

    @property
    def available_for_tasks(self) -> int:
        """Budget available for tasks (excluding reserve)."""
        reserved = int(self.total_budget * self.reserve_ratio)
        return max(0, self.remaining - reserved)

    @property
    def is_low(self) -> bool:
        """Whether budget is getting low (<30% remaining)."""
        return self.remaining < self.total_budget * 0.3

    @property
    def is_critical(self) -> bool:
        """Whether budget is critical (<10% remaining)."""
        return self.remaining < self.total_budget * 0.1

    def can_afford(self, technique: str, base_cost: int) -> bool:
        """Check if we can afford a technique.

        Args:
            technique: Technique name (vortex, harmonic_5, etc.)
            base_cost: Base token cost for single-shot

        Returns:
            True if we can afford this technique
        """
        multiplier = self._get_multiplier(technique)
        total_cost = int(base_cost * multiplier)
        return total_cost <= self.available_for_tasks

    def route_for_budget(self, ideal: str, base_cost: int) -> str:
        """Downgrade technique if budget is tight.

        Args:
            ideal: The ideal technique to use
            base_cost: Base token cost for single-shot

        Returns:
            The technique we can actually afford (may be downgraded)
        """
        if self.can_afford(ideal, base_cost):
            return ideal

        # Downgrade path
        downgrades = {
            "vortex": "interference",
            "harmonic_5": "harmonic_3",
            "harmonic_3": "single_shot",
            "interference": "single_shot",
            "compound_eye": "lateral_only",
            "lateral_only": "single_shot",
        }

        current = ideal
        while current in downgrades:
            fallback = downgrades[current]
            if self.can_afford(fallback, base_cost):
                return fallback
            current = fallback

        return "single_shot"

    def record_spend(self, tokens: int) -> None:
        """Record tokens spent.

        Args:
            tokens: Number of tokens spent
        """
        self.spent += tokens

    def estimate_cost(self, technique: str, base_cost: int) -> int:
        """Estimate cost for a technique.

        Args:
            technique: Technique name
            base_cost: Base token cost

        Returns:
            Estimated total tokens
        """
        multiplier = self._get_multiplier(technique)
        return int(base_cost * multiplier)

    def _get_multiplier(self, technique: str) -> float:
        """Get cost multiplier for a technique.

        Uses instance-configured multipliers, falling back to defaults.
        """
        # Instance-specific overrides (configurable per-budget)
        instance_multipliers = {
            "single_shot": self.single_shot,
            "interference": self.interference,
            "harmonic_3": self.harmonic_3,
            "harmonic_5": self.harmonic_5,
            "vortex": self.vortex,
            "compound_eye": self.compound_eye,
            "resonance": self.resonance_per_loop,
        }
        return instance_multipliers.get(
            technique, DEFAULT_TECHNIQUE_MULTIPLIERS.get(technique, 1.0)
        )

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "total_budget": self.total_budget,
            "spent": self.spent,
            "remaining": self.remaining,
            "available_for_tasks": self.available_for_tasks,
            "is_low": self.is_low,
            "is_critical": self.is_critical,
        }


# =============================================================================
# Cost Estimates
# =============================================================================


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated cost for a task or operation."""

    tokens: int
    """Estimated tokens."""

    technique: str
    """Technique that will be used."""

    time_s: float
    """Estimated time in seconds."""

    confidence: float = 0.7
    """Confidence in estimate (0-1)."""


def estimate_task_cost(
    task_description: str,
    technique: str = "single_shot",
) -> CostEstimate:
    """Estimate cost for a task.

    Uses heuristics based on task description length and type.

    Args:
        task_description: Description of the task
        technique: Technique that will be used

    Returns:
        CostEstimate with token and time estimates
    """
    # Base estimate: ~2 tokens per word of description for context,
    # plus ~500 tokens for generation
    words = len(task_description.split())
    base_tokens = (words * 2) + 500

    # Use shared technique multipliers
    multiplier = DEFAULT_TECHNIQUE_MULTIPLIERS.get(technique, 1.0)

    tokens = int(base_tokens * multiplier)

    # Time estimate: ~1s per 100 tokens (rough)
    time_s = tokens / 100

    return CostEstimate(
        tokens=tokens,
        technique=technique,
        time_s=time_s,
    )


def estimate_plan_cost(
    tasks: int,
    avg_complexity: Literal["low", "medium", "high"] = "medium",
    technique: str = "single_shot",
) -> CostEstimate:
    """Estimate cost for a full plan.

    Args:
        tasks: Number of tasks in the plan
        avg_complexity: Average task complexity
        technique: Default technique for tasks

    Returns:
        CostEstimate for the full plan
    """
    # Base per-task costs
    complexity_costs = {
        "low": 300,
        "medium": 600,
        "high": 1200,
    }
    per_task = complexity_costs.get(avg_complexity, 600)

    # Signal extraction overhead
    signal_overhead = 60  # ~40 tokens per goal + per-task

    # Technique multiplier
    multipliers = {
        "single_shot": 1.0,
        "interference": 3.0,
        "vortex": 15.0,
    }
    multiplier = multipliers.get(technique, 1.0)

    # Total
    tokens = int((tasks * per_task * multiplier) + signal_overhead)
    time_s = tokens / 100  # Rough estimate

    return CostEstimate(
        tokens=tokens,
        technique=technique,
        time_s=time_s,
        confidence=0.6,  # Plans have higher variance
    )
