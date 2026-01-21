"""Temporal signal stability pattern (trit-based)."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.experiments.compound.types import OmmatidiumSignal

SIGNAL_PROMPT = """You are ONE sensor in a compound eye. Your job is simple:
rate the following region on a scale of 0-2.

QUESTION: {question}

REGION:
{region}

Respond with ONLY a single digit: 0, 1, or 2
- 0 = No concern
- 1 = Minor concern
- 2 = Significant concern

Your response (just the digit):"""


@dataclass(frozen=True, slots=True)
class SignalStability:
    """Stability analysis for a single region's trit signal."""

    index: int
    """Region index."""

    region: str
    """The text region."""

    signals: tuple[int, ...]
    """Trit signals across frames (0, 1, or 2)."""

    mode_signal: int
    """Most common signal (the "vote")."""

    stability: float
    """Stability score (0-1). 1.0 = all same, 0.33 = all different."""

    is_stable: bool
    """Whether signal is stable (all frames agree)."""

    @property
    def is_unanimous(self) -> bool:
        """Whether all frames gave exactly the same signal."""
        return len(set(self.signals)) == 1

    @property
    def spread(self) -> int:
        """Signal spread (max - min). 0=stable, 2=max disagreement."""
        return max(self.signals) - min(self.signals)


@dataclass(frozen=True, slots=True)
class TemporalSignalResult:
    """Result from temporal signal stability scan."""

    regions: tuple[SignalStability, ...]
    """Per-region stability analysis."""

    n_frames: int
    """Number of frames captured."""

    stable_indices: tuple[int, ...]
    """Indices with stable signals."""

    unstable_indices: tuple[int, ...]
    """Indices with flickering signals."""

    overall_stability: float
    """Average stability across all regions."""

    @property
    def unanimous_count(self) -> int:
        """Number of regions with unanimous agreement."""
        return sum(1 for r in self.regions if r.is_unanimous)

    @property
    def high_spread_indices(self) -> tuple[int, ...]:
        """Indices where signal spread is 2 (max disagreement: 0 vs 2)."""
        return tuple(r.index for r in self.regions if r.spread == 2)


async def temporal_signal_scan(
    regions: list[str],
    question: str,
    model: ModelProtocol,
    n_frames: int = 3,
    stability_threshold: float = 0.8,
    parallel_frames: bool = False,
) -> TemporalSignalResult:
    """Measure signal stability by running trit classification multiple times.

    Much faster than full temporal differencing because:
    - Trit output is tiny (one digit)
    - Comparison is exact (no fuzzy text matching)
    - Parallel frames possible if model supports it

    Args:
        regions: Text regions to classify
        question: Question for trit classification (e.g., "Is this dangerous?")
        model: Model to use
        n_frames: Number of classification runs per region
        stability_threshold: Minimum stability to count as stable
        parallel_frames: Run frames in parallel (requires Ollama parallel support)

    Returns:
        TemporalSignalResult with per-region stability
    """
    from collections import Counter

    from sunwell.models.protocol import GenerateOptions

    async def classify_region(region: str, frame_idx: int) -> int:
        """Classify one region, return trit signal."""
        prompt = SIGNAL_PROMPT.format(question=question, region=region)

        try:
            result = await model.generate(
                prompt,
                options=GenerateOptions(temperature=0.5, max_tokens=10),
            )

            text = result.text.strip()
            for char in text:
                if char in "012":
                    return int(char)
            return 1  # Default to middle if parsing fails

        except Exception:
            return 1  # Default on error

    # Collect signals for each region across frames
    region_signals: list[list[int]] = [[] for _ in regions]

    for frame_idx in range(n_frames):
        if parallel_frames:
            # All regions in parallel for this frame
            tasks = [classify_region(r, frame_idx) for r in regions]
            frame_results = await asyncio.gather(*tasks)
            for i, signal in enumerate(frame_results):
                region_signals[i].append(signal)
        else:
            # Sequential (safe for local Ollama)
            for i, region in enumerate(regions):
                signal = await classify_region(region, frame_idx)
                region_signals[i].append(signal)

    # Analyze stability per region
    stabilities: list[SignalStability] = []
    stable_indices: list[int] = []
    unstable_indices: list[int] = []

    for i, signals in enumerate(region_signals):
        signal_tuple = tuple(signals)

        # Mode (most common signal)
        counts = Counter(signals)
        mode_signal = counts.most_common(1)[0][0]

        # Stability = fraction that match the mode
        stability = counts[mode_signal] / len(signals)

        is_stable = stability >= stability_threshold

        stabilities.append(
            SignalStability(
                index=i,
                region=regions[i][:100],  # Truncate for storage
                signals=signal_tuple,
                mode_signal=mode_signal,
                stability=stability,
                is_stable=is_stable,
            )
        )

        if is_stable:
            stable_indices.append(i)
        else:
            unstable_indices.append(i)

    overall = sum(s.stability for s in stabilities) / len(stabilities) if stabilities else 1.0

    return TemporalSignalResult(
        regions=tuple(stabilities),
        n_frames=n_frames,
        stable_indices=tuple(stable_indices),
        unstable_indices=tuple(unstable_indices),
        overall_stability=overall,
    )


