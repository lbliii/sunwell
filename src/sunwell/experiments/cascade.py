"""Gradient Cascade — Stack of progressively smarter gates.

The hypothesis: Most queries can be handled by tiny models. Stack gates of
increasing capability, where each gate can either handle the request or
pass it to the next level.

```
Input → 0.5B → 1B → 3B → 8B → 70B
         │      │     │     │
        60%    25%   10%    4%   → 1% needs big model
       (exit) (exit)(exit)(exit)
```

Each gate is slightly smarter. The harder the problem, the further it
penetrates. 99% of work is done by tiny models.

Example:
    >>> from sunwell.experiments import GradientCascade
    >>>
    >>> cascade = GradientCascade(
    ...     tiers=[
    ...         ("gemma3:1b", 0.8),   # 80% confidence threshold
    ...         ("gemma3:4b", 0.7),   # 70% confidence threshold
    ...         ("gemma3:8b", 0.6),   # 60% confidence threshold
    ...     ],
    ...     fallback_model="llama3.1:70b",
    ... )
    >>>
    >>> result = await cascade.route("Fix typo in README")
    >>> print(f"Handled by tier {result.tier}: {result.model}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


@dataclass(frozen=True, slots=True)
class CascadeResult:
    """Result from gradient cascade routing."""

    tier: int
    """Which tier handled the request (0-indexed, -1 for fallback)."""

    model: str
    """Model name that handled the request."""

    confidence: float
    """Confidence of the handling tier."""

    classification: Any
    """The classification/decision made."""

    tiers_tried: int
    """How many tiers were attempted before success."""

    total_latency_ms: float
    """Total time across all tier attempts."""


@dataclass
class CascadeTier:
    """A single tier in the cascade."""

    model_name: str
    """Model name for this tier."""

    confidence_threshold: float
    """Minimum confidence to handle at this tier."""

    model: ModelProtocol | None = None
    """Loaded model instance."""


@dataclass
class GradientCascade:
    """Stack of progressively smarter gates.

    Each tier attempts to handle the request. If confidence is below
    threshold, pass to next tier. Final tier always handles.

    Usage:
        cascade = GradientCascade(
            tiers=[
                ("gemma3:1b", 0.8),   # Fast, needs high confidence
                ("gemma3:4b", 0.7),   # Medium
                ("gemma3:8b", 0.6),   # Slower, lower threshold
            ],
            fallback_model="llama3.1:70b",
        )

        result = await cascade.classify("Build a REST API")
    """

    tiers: list[tuple[str, float]]
    """List of (model_name, confidence_threshold) tuples."""

    fallback_model: str | None = None
    """Model to use if all tiers fail threshold."""

    _loaded_tiers: list[CascadeTier] = field(default_factory=list, repr=False)
    _fallback: ModelProtocol | None = field(default=None, repr=False)
    _stats: dict[str, int] = field(default_factory=lambda: {"tier_exits": {}, "fallback_exits": 0}, repr=False)

    async def _ensure_loaded(self) -> None:
        """Lazy-load models on first use."""
        if self._loaded_tiers:
            return

        from sunwell.models.ollama import OllamaModel

        for model_name, threshold in self.tiers:
            tier = CascadeTier(
                model_name=model_name,
                confidence_threshold=threshold,
                model=OllamaModel(model=model_name),
            )
            self._loaded_tiers.append(tier)

        if self.fallback_model:
            self._fallback = OllamaModel(model=self.fallback_model)

    async def classify(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> CascadeResult:
        """Classify goal using gradient cascade.

        Tries each tier in order. If confidence meets threshold, return.
        Otherwise, escalate to next tier.

        Args:
            goal: The goal to classify
            context: Optional context

        Returns:
            CascadeResult with classification and metrics
        """
        import time

        from sunwell.routing import UnifiedRouter

        await self._ensure_loaded()

        start_time = time.perf_counter()
        tiers_tried = 0

        for i, tier in enumerate(self._loaded_tiers):
            tiers_tried += 1

            router = UnifiedRouter(model=tier.model)
            decision = await router.route(goal, context)

            # Check if this tier can handle it
            if decision.confidence >= tier.confidence_threshold:
                latency = (time.perf_counter() - start_time) * 1000

                # Track stats
                self._stats["tier_exits"][i] = self._stats["tier_exits"].get(i, 0) + 1

                return CascadeResult(
                    tier=i,
                    model=tier.model_name,
                    confidence=decision.confidence,
                    classification=decision.complexity,
                    tiers_tried=tiers_tried,
                    total_latency_ms=latency,
                )

        # All tiers failed threshold — use fallback
        if self._fallback:
            tiers_tried += 1
            router = UnifiedRouter(model=self._fallback)
            decision = await router.route(goal, context)

            latency = (time.perf_counter() - start_time) * 1000
            self._stats["fallback_exits"] += 1

            return CascadeResult(
                tier=-1,  # Fallback
                model=self.fallback_model,
                confidence=decision.confidence,
                classification=decision.complexity,
                tiers_tried=tiers_tried,
                total_latency_ms=latency,
            )

        # No fallback — use last tier's result regardless of confidence
        latency = (time.perf_counter() - start_time) * 1000
        last_tier = self._loaded_tiers[-1]
        router = UnifiedRouter(model=last_tier.model)
        decision = await router.route(goal, context)

        return CascadeResult(
            tier=len(self._loaded_tiers) - 1,
            model=last_tier.model_name,
            confidence=decision.confidence,
            classification=decision.complexity,
            tiers_tried=tiers_tried,
            total_latency_ms=latency,
        )

    def stats(self) -> dict[str, Any]:
        """Return cascade statistics.

        Shows how often each tier handled requests, useful for tuning
        confidence thresholds.
        """
        total = sum(self._stats["tier_exits"].values()) + self._stats["fallback_exits"]

        if total == 0:
            return {"total_requests": 0}

        tier_rates = {}
        for i, (model_name, _) in enumerate(self.tiers):
            count = self._stats["tier_exits"].get(i, 0)
            tier_rates[f"tier_{i}_{model_name}"] = {
                "count": count,
                "rate": count / total,
            }

        return {
            "total_requests": total,
            "tier_rates": tier_rates,
            "fallback_rate": self._stats["fallback_exits"] / total,
            "early_exit_rate": self._stats["tier_exits"].get(0, 0) / total,
        }


# =============================================================================
# Pre-configured cascades
# =============================================================================


def create_standard_cascade() -> GradientCascade:
    """Create a standard 3-tier cascade.

    Tier 0 (1B): Fast, handles trivial requests (80% threshold)
    Tier 1 (4B): Medium, handles standard requests (70% threshold)
    Tier 2 (8B): Slow, handles complex requests (60% threshold)
    """
    return GradientCascade(
        tiers=[
            ("gemma3:1b", 0.8),
            ("gemma3:4b", 0.7),
            ("gemma3:8b", 0.6),
        ],
    )


def create_aggressive_cascade() -> GradientCascade:
    """Create an aggressive cascade that exits early more often.

    Lower thresholds mean more requests handled by tiny models.
    Use when speed matters more than accuracy.
    """
    return GradientCascade(
        tiers=[
            ("gemma3:1b", 0.6),   # Very aggressive
            ("gemma3:4b", 0.5),
            ("gemma3:8b", 0.4),
        ],
    )


def create_conservative_cascade() -> GradientCascade:
    """Create a conservative cascade that escalates more often.

    Higher thresholds mean more requests go to bigger models.
    Use when accuracy matters more than speed.
    """
    return GradientCascade(
        tiers=[
            ("gemma3:1b", 0.95),  # Very conservative
            ("gemma3:4b", 0.85),
            ("gemma3:8b", 0.75),
        ],
        fallback_model="llama3.1:70b",
    )
