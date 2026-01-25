"""Vortex — Multi-model coordination through primitive composition.

The vortex combines:
- Locality (islands) for cultural diversity
- Verbosity scaling (token funnel) for efficiency
- Temporal primitives (interference, dialectic, resonance) for refinement

The architecture follows a funnel pattern:
1. DISCOVERY: Cheap, diverse exploration with compressed signals
2. SELECTION: Brief reasoning to pick winners
3. SYNTHESIS: Full expansion of the winning approach
"""


import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

from sunwell.models import GenerateOptions
from sunwell.features.vortex.config import VortexConfig
from sunwell.features.vortex.locality import (
    LocalityResult,
    evolve_islands,
    select_best_signal_per_island,
)
from sunwell.features.vortex.primitives import (
    DialecticResult,
    InterferenceResult,
    dialectic,
    interference,
)
from sunwell.features.vortex.signals import (
    SELECTION_PROMPT,
    SYNTHESIS_PROMPT,
    Signal,
    parse_selection,
)

# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class VortexResult:
    """Complete result from vortex execution."""

    task: str
    """Original task."""

    # Phase outputs
    locality: LocalityResult
    """Island evolution result."""

    winner: Signal
    """Winning signal from selection."""

    selection_reason: str
    """Why winner was selected."""

    synthesis: str
    """Final expanded answer."""

    # Optional primitive results (if triggered)
    interference_result: InterferenceResult | None
    """Interference result if low agreement triggered it."""

    dialectic_result: DialecticResult | None
    """Dialectic result if very low agreement triggered it."""

    # Metrics
    distinct_cultures: int
    """Number of distinct island cultures."""

    migrations: int
    """Cross-island signal migrations."""

    total_signals: int
    """Total signals generated."""

    # Token accounting
    discovery_tokens: int
    """Tokens spent on discovery."""

    selection_tokens: int
    """Tokens spent on selection."""

    synthesis_tokens: int
    """Tokens spent on synthesis."""

    # Timing
    discovery_time_s: float
    selection_time_s: float
    synthesis_time_s: float
    total_time_s: float


# =============================================================================
# Vortex
# =============================================================================


class Vortex:
    """Multi-model coordination through primitive composition.

    Example:
        >>> from sunwell.vortex import Vortex, VortexConfig
        >>> from sunwell.models import OllamaModel
        >>>
        >>> model = OllamaModel("gemma3:1b")
        >>> vortex = Vortex(model)
        >>>
        >>> result = await vortex.solve("Design a rate limiter for an API")
        >>> print(result.synthesis)
    """

    def __init__(
        self,
        model: ModelProtocol,
        config: VortexConfig | None = None,
    ):
        """Initialize vortex.

        Args:
            model: Model for generation (1B-3B recommended for speed)
            config: Vortex configuration (uses defaults if None)
        """
        self.model = model
        self.config = config or VortexConfig()

    async def solve(self, task: str) -> VortexResult:
        """Run the full vortex pipeline.

        Args:
            task: The problem to solve

        Returns:
            VortexResult with full analysis and synthesized answer
        """
        total_start = time.perf_counter()

        # Phase 1: DISCOVERY (locality + compressed signals)
        discovery_start = time.perf_counter()
        locality_result = await self._discover(task)
        discovery_time = time.perf_counter() - discovery_start

        # Phase 2: SELECTION (pick winner with brief reasoning)
        selection_start = time.perf_counter()
        winner, reason, interference_result, dialectic_result = await self._select(
            task, locality_result
        )
        selection_time = time.perf_counter() - selection_start

        # Phase 3: SYNTHESIS (full expansion)
        synthesis_start = time.perf_counter()
        synthesis = await self._synthesize(task, winner, reason)
        synthesis_time = time.perf_counter() - synthesis_start

        # Token accounting
        c = self.config
        total_signals = sum(len(isl.signals) for isl in locality_result.islands)
        discovery_tokens = total_signals * c.discovery_tokens
        selection_tokens = c.selection_tokens
        synthesis_tokens = c.synthesis_tokens

        if interference_result:
            selection_tokens += c.selection_tokens * len(interference_result.perspectives)
        if dialectic_result:
            selection_tokens += c.selection_tokens * 3  # thesis + antithesis + synthesis

        return VortexResult(
            task=task,
            locality=locality_result,
            winner=winner,
            selection_reason=reason,
            synthesis=synthesis,
            interference_result=interference_result,
            dialectic_result=dialectic_result,
            distinct_cultures=locality_result.distinct_cultures,
            migrations=locality_result.migrations,
            total_signals=total_signals,
            discovery_tokens=discovery_tokens,
            selection_tokens=selection_tokens,
            synthesis_tokens=synthesis_tokens,
            discovery_time_s=discovery_time,
            selection_time_s=selection_time,
            synthesis_time_s=synthesis_time,
            total_time_s=time.perf_counter() - total_start,
        )

    async def _discover(self, task: str) -> LocalityResult:
        """Discovery phase — evolve signals in isolated islands."""
        c = self.config

        options = GenerateOptions(
            temperature=c.discovery_temp,
            max_tokens=c.discovery_tokens,
        )

        return await evolve_islands(
            task=task,
            model=self.model,
            options=options,
            n_islands=c.n_islands,
            agents_per_island=c.agents_per_island,
            generations=c.island_generations,
            migration_rate=c.migration_rate,
            migration_threshold=c.migration_threshold,
        )

    async def _select(
        self,
        task: str,
        locality: LocalityResult,
    ) -> tuple[Signal, str, InterferenceResult | None, DialecticResult | None]:
        """Selection phase — pick winner from island signals."""
        c = self.config

        options = GenerateOptions(
            temperature=c.selection_temp,
            max_tokens=c.selection_tokens,
        )

        # Get best signals from each island
        candidates = select_best_signal_per_island(locality.islands)

        if not candidates:
            # Fallback: no signals (shouldn't happen)
            return Signal(
                claim="Unable to generate signals",
                confidence=0.0,
                tags=(),
            ), "No candidates available", None, None

        # Format candidates for selection
        candidates_str = "\n".join(
            f"{i+1}. [{s.confidence:.1f}] {s.claim} (culture: {', '.join(locality.islands[i].culture[:2])})"
            for i, s in enumerate(candidates)
        )

        result = await self.model.generate(
            SELECTION_PROMPT.format(task=task, candidates=candidates_str),
            options=options,
        )

        pick_idx, reason = parse_selection(result.text)
        pick_idx = min(pick_idx, len(candidates) - 1)
        pick_idx = max(0, pick_idx)

        winner = candidates[pick_idx]

        # Check if we need interference (multiple perspectives on winner)
        interference_result = None
        dialectic_result = None

        if winner.confidence < c.dialectic_threshold:
            # Low confidence — run interference
            interference_result = await interference(
                f"{task}\n\nProposed approach: {winner.claim}",
                self.model,
                options,
                n_perspectives=c.interference_perspectives,
            )

            # If interference shows disagreement, run dialectic
            if (c.dialectic_enabled
                and interference_result.agreement < c.dialectic_threshold):
                dialectic_result = await dialectic(
                    f"{task}\n\nContext: {winner.claim}",
                    self.model,
                    options,
                )
                # Update reason with dialectic insight
                reason = f"{reason} Dialectic synthesis: {dialectic_result.synthesis[:100]}"

        return winner, reason, interference_result, dialectic_result

    async def _synthesize(self, task: str, winner: Signal, reason: str) -> str:
        """Synthesis phase — full expansion of winning approach."""
        c = self.config

        options = GenerateOptions(
            temperature=c.synthesis_temp,
            max_tokens=c.synthesis_tokens,
        )

        result = await self.model.generate(
            SYNTHESIS_PROMPT.format(task=task, winner=winner.claim, reason=reason),
            options=options,
        )

        return result.text.strip()


# =============================================================================
# Convenience Functions
# =============================================================================


async def solve(
    task: str,
    model: ModelProtocol,
    config: VortexConfig | None = None,
) -> VortexResult:
    """Convenience function to run vortex without instantiating class.

    Example:
        >>> from sunwell.vortex import solve
        >>> result = await solve("Design a cache", model)
    """
    vortex = Vortex(model, config)
    return await vortex.solve(task)


def format_result(result: VortexResult) -> str:
    """Format vortex result as human-readable report."""
    lines = [
        "=== VORTEX RESULT ===",
        f"Task: {result.task[:60]}...",
        "",
        "=== DISCOVERY ===",
        f"  Islands: {len(result.locality.islands)}",
        f"  Distinct cultures: {result.distinct_cultures}",
        f"  Migrations: {result.migrations}",
        f"  Total signals: {result.total_signals}",
        f"  Time: {result.discovery_time_s:.1f}s",
        "",
        "  Cultures:",
    ]

    for isl in result.locality.islands:
        culture = ", ".join(isl.culture[:3]) if isl.culture else "none"
        lines.append(f"    Island {isl.island_id}: [{culture}]")

    lines.extend([
        "",
        "=== SELECTION ===",
        f"  Winner: {result.winner.claim[:60]}...",
        f"  Confidence: {result.winner.confidence:.1f}",
        f"  Reason: {result.selection_reason[:80]}...",
        f"  Time: {result.selection_time_s:.1f}s",
    ])

    if result.interference_result:
        lines.append(f"  Interference: {result.interference_result.pattern} ({result.interference_result.agreement:.2%} agreement)")

    if result.dialectic_result:
        lines.append("  Dialectic: thesis → antithesis → synthesis")

    lines.extend([
        "",
        "=== SYNTHESIS ===",
        f"  Time: {result.synthesis_time_s:.1f}s",
        "",
        f"{result.synthesis[:500]}...",
        "",
        "=== METRICS ===",
        f"  Discovery tokens: {result.discovery_tokens}",
        f"  Selection tokens: {result.selection_tokens}",
        f"  Synthesis tokens: {result.synthesis_tokens}",
        f"  Total time: {result.total_time_s:.1f}s",
    ])

    return "\n".join(lines)
