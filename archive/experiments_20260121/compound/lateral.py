"""Lateral inhibition pattern for compound eye architecture."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.experiments.compound.types import LateralInhibitionResult, OmmatidiumSignal

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


async def _scan_ommatidium(
    region: str,
    question: str,
    model: ModelProtocol,
    index: int,
) -> tuple[int, float, str]:
    """Fire a single ommatidium to scan one region."""
    from sunwell.models.protocol import GenerateOptions

    prompt = SIGNAL_PROMPT.format(question=question, region=region)

    try:
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=10),
        )

        text = result.text.strip()

        # Extract digit
        for char in text:
            if char in "012":
                signal = int(char) / 2.0  # Normalize to 0-1
                return index, signal, text

        # Default to middle if parsing fails
        return index, 0.5, text

    except Exception as e:
        return index, 0.5, f"ERROR: {e}"


def _apply_lateral_inhibition(
    raw_signals: list[float],
    inhibition_strength: float = 0.3,
) -> list[float]:
    """Apply lateral inhibition to enhance edges.

    Each signal is reduced by a fraction of its neighbors' signals.
    This makes high signals surrounded by low signals stand out MORE,
    and uniform regions flatten out.

    Args:
        raw_signals: Raw signal values (0-1)
        inhibition_strength: How much neighbors inhibit (0-1)

    Returns:
        Inhibited signals (can be negative, edges will be positive)
    """
    n = len(raw_signals)
    if n == 0:
        return []

    inhibited = []
    for i, signal in enumerate(raw_signals):
        # Get neighbor signals (wrap at edges)
        left = raw_signals[i - 1] if i > 0 else signal
        right = raw_signals[i + 1] if i < n - 1 else signal

        # Lateral inhibition: subtract weighted average of neighbors
        neighbor_avg = (left + right) / 2.0
        inhibited_signal = signal - (inhibition_strength * neighbor_avg)

        inhibited.append(inhibited_signal)

    return inhibited


async def lateral_inhibition_scan(
    regions: list[str],
    question: str,
    model: ModelProtocol,
    inhibition_strength: float = 0.3,
    edge_threshold: float = 0.3,
    parallel: bool = False,
) -> LateralInhibitionResult:
    """Scan regions with lateral inhibition to detect edges/anomalies.

    Like a compound eye detecting edges: areas where the signal changes
    sharply between adjacent regions are highlighted.

    Args:
        regions: List of text regions to scan (e.g., code chunks)
        question: Question to ask each ommatidium (e.g., "Rate danger 0-2")
        model: Model for scanning
        inhibition_strength: How much neighbors suppress each other (0-1)
        edge_threshold: Minimum inhibited signal to count as edge
        parallel: Run ommatidia in parallel (requires Ollama parallel support)

    Returns:
        LateralInhibitionResult with edges detected
    """
    if not regions:
        return LateralInhibitionResult(
            signals=(),
            edge_indices=(),
            edge_threshold=edge_threshold,
            total_regions=0,
            edges_found=0,
        )

    # Fire all ommatidia
    if parallel:
        tasks = [
            _scan_ommatidium(region, question, model, i)
            for i, region in enumerate(regions)
        ]
        results = await asyncio.gather(*tasks)
    else:
        results = []
        for i, region in enumerate(regions):
            r = await _scan_ommatidium(region, question, model, i)
            results.append(r)

    # Sort by index (parallel may return out of order)
    results = sorted(results, key=lambda x: x[0])

    # Extract raw signals
    raw_signals = [r[1] for r in results]
    responses = [r[2] for r in results]

    # Apply lateral inhibition
    inhibited = _apply_lateral_inhibition(raw_signals, inhibition_strength)

    # Build ommatidium signals
    signals = []
    edge_indices = []
    for i, region in enumerate(regions):
        signal = OmmatidiumSignal(
            index=i,
            region=region,
            raw_signal=raw_signals[i],
            inhibited_signal=max(0, inhibited[i]),  # Clamp to 0
            response=responses[i],
        )
        signals.append(signal)

        # Detect edges (high inhibited signal)
        if inhibited[i] >= edge_threshold:
            edge_indices.append(i)

    return LateralInhibitionResult(
        signals=tuple(signals),
        edge_indices=tuple(edge_indices),
        edge_threshold=edge_threshold,
        total_regions=len(regions),
        edges_found=len(edge_indices),
    )


