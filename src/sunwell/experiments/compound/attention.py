"""Attention fold pattern for resolving flickering regions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.experiments.compound.signal import SignalStability, TemporalSignalResult


class FoldStrategy(Enum):
    """Strategies for resolving flickering regions."""

    VOTE = "vote"
    """More samples, majority wins."""

    ESCALATE = "escalate"
    """Send to bigger model."""

    TRIANGULATE = "triangulate"
    """Ask from multiple angles."""

    DECOMPOSE = "decompose"
    """Break into smaller pieces."""

    ENSEMBLE = "ensemble"
    """Combine multiple strategies."""


@dataclass(frozen=True, slots=True)
class FoldedRegion:
    """Result of folding attention onto a flickering region."""

    index: int
    """Original region index."""

    region: str
    """The text region."""

    original_signals: tuple[int, ...]
    """Signals before folding."""

    resolved_signal: int
    """Final signal after folding."""

    confidence: float
    """Confidence in resolved signal (0-1)."""

    strategy_used: FoldStrategy
    """Which strategy resolved it."""

    details: dict[str, Any]
    """Strategy-specific details."""


@dataclass(frozen=True, slots=True)
class AttentionFoldResult:
    """Result from attention folding."""

    stable_regions: tuple[SignalStability, ...]
    """Regions that were already stable (passed through)."""

    folded_regions: tuple[FoldedRegion, ...]
    """Regions that needed folding."""

    final_signals: tuple[int, ...]
    """Final signals for all regions (stable + resolved)."""

    total_regions: int
    """Total number of regions."""

    folded_count: int
    """Number of regions that needed folding."""

    avg_confidence: float
    """Average confidence across folded regions."""


async def _fold_vote(
    region: str,
    question: str,
    model: ModelProtocol,
    original_signals: tuple[int, ...],
    extra_samples: int = 5,
) -> FoldedRegion:
    """Resolve by getting more samples and voting."""
    from collections import Counter

    from sunwell.models.protocol import GenerateOptions

    # Get more samples
    all_signals = list(original_signals)

    for _ in range(extra_samples):
        prompt = SIGNAL_PROMPT.format(question=question, region=region)
        try:
            result = await model.generate(
                prompt,
                options=GenerateOptions(temperature=0.5, max_tokens=10),
            )
            for char in result.text.strip():
                if char in "012":
                    all_signals.append(int(char))
                    break
            else:
                all_signals.append(1)
        except Exception:
            all_signals.append(1)

    # Vote
    counts = Counter(all_signals)
    winner, count = counts.most_common(1)[0]
    confidence = count / len(all_signals)

    return FoldedRegion(
        index=-1,  # Set by caller
        region=region[:100],
        original_signals=original_signals,
        resolved_signal=winner,
        confidence=confidence,
        strategy_used=FoldStrategy.VOTE,
        details={"all_signals": all_signals, "vote_counts": dict(counts)},
    )


async def _fold_escalate(
    region: str,
    question: str,
    big_model: ModelProtocol,
    original_signals: tuple[int, ...],
) -> FoldedRegion:
    """Resolve by asking a bigger model."""
    from sunwell.models.protocol import GenerateOptions

    prompt = f"""You are a senior reviewer. A smaller model was UNCERTAIN about this code.

QUESTION: {question}

CODE:
{region}

The smaller model gave inconsistent signals: {original_signals}

Your job: Give a DEFINITIVE rating.
Respond with ONLY: 0 (safe), 1 (minor concern), or 2 (significant risk)

Your rating:"""

    try:
        result = await big_model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=10),
        )

        for char in result.text.strip():
            if char in "012":
                signal = int(char)
                return FoldedRegion(
                    index=-1,
                    region=region[:100],
                    original_signals=original_signals,
                    resolved_signal=signal,
                    confidence=0.9,  # Trust the big model
                    strategy_used=FoldStrategy.ESCALATE,
                    details={"big_model_response": result.text},
                )

        # Parsing failed
        return FoldedRegion(
            index=-1,
            region=region[:100],
            original_signals=original_signals,
            resolved_signal=1,
            confidence=0.5,
            strategy_used=FoldStrategy.ESCALATE,
            details={"error": "Could not parse big model response"},
        )

    except Exception as e:
        return FoldedRegion(
            index=-1,
            region=region[:100],
            original_signals=original_signals,
            resolved_signal=1,
            confidence=0.3,
            strategy_used=FoldStrategy.ESCALATE,
            details={"error": str(e)},
        )


async def _fold_triangulate(
    region: str,
    base_question: str,
    model: ModelProtocol,
    original_signals: tuple[int, ...],
) -> FoldedRegion:
    """Resolve by asking from multiple angles."""
    from collections import Counter

    from sunwell.models.protocol import GenerateOptions

    # Different angles on the same question
    angles = [
        f"As a SECURITY expert: {base_question}",
        f"As a CODE REVIEWER: {base_question}",
        f"Would a HACKER find this exploitable? {base_question}",
    ]

    angle_signals = []
    angle_details = {}

    for angle in angles:
        prompt = SIGNAL_PROMPT.format(question=angle, region=region)
        try:
            result = await model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=10),
            )
            for char in result.text.strip():
                if char in "012":
                    signal = int(char)
                    angle_signals.append(signal)
                    angle_details[angle[:30]] = signal
                    break
            else:
                angle_signals.append(1)
                angle_details[angle[:30]] = "parse_error"
        except Exception as e:
            angle_signals.append(1)
            angle_details[angle[:30]] = str(e)

    # Combine original + triangulated
    all_signals = list(original_signals) + angle_signals
    counts = Counter(all_signals)
    winner, count = counts.most_common(1)[0]

    # Confidence based on agreement across angles
    angle_agreement = len(set(angle_signals)) == 1
    confidence = 0.85 if angle_agreement else count / len(all_signals)

    return FoldedRegion(
        index=-1,
        region=region[:100],
        original_signals=original_signals,
        resolved_signal=winner,
        confidence=confidence,
        strategy_used=FoldStrategy.TRIANGULATE,
        details={"angle_signals": angle_details, "agreement": angle_agreement},
    )


async def _fold_decompose(
    region: str,
    question: str,
    model: ModelProtocol,
    original_signals: tuple[int, ...],
) -> FoldedRegion:
    """Resolve by breaking into smaller pieces and aggregating."""
    from sunwell.models.protocol import GenerateOptions

    # Split region into smaller chunks (by line or statement)
    lines = [line.strip() for line in region.split("\n") if line.strip()]

    if len(lines) <= 1:
        # Can't decompose further, fall back to vote
        return await _fold_vote(region, question, model, original_signals, extra_samples=3)

    # Classify each line
    line_signals = []
    for line in lines[:5]:  # Limit to 5 lines
        prompt = SIGNAL_PROMPT.format(question=question, region=line)
        try:
            result = await model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=10),
            )
            for char in result.text.strip():
                if char in "012":
                    line_signals.append(int(char))
                    break
            else:
                line_signals.append(1)
        except Exception:
            line_signals.append(1)

    # Aggregate: max signal (if any line is dangerous, whole region is)
    resolved = max(line_signals) if line_signals else 1

    # Confidence based on consistency of line signals
    unique_signals = len(set(line_signals))
    confidence = 1.0 if unique_signals == 1 else 0.7 if unique_signals == 2 else 0.5

    return FoldedRegion(
        index=-1,
        region=region[:100],
        original_signals=original_signals,
        resolved_signal=resolved,
        confidence=confidence,
        strategy_used=FoldStrategy.DECOMPOSE,
        details={"line_signals": line_signals, "lines_analyzed": len(line_signals)},
    )


async def attention_fold(
    initial_scan: TemporalSignalResult,
    regions: list[str],
    question: str,
    model: ModelProtocol,
    strategy: FoldStrategy = FoldStrategy.VOTE,
    big_model: ModelProtocol | None = None,
    stability_threshold: float = 0.8,
) -> AttentionFoldResult:
    """Fold attention onto flickering regions to resolve uncertainty.

    Process:
    1. Take initial temporal scan results
    2. Pass through stable regions unchanged
    3. Apply resolution strategy to flickering regions
    4. Return unified result with confidence scores

    Args:
        initial_scan: Result from temporal_signal_scan
        regions: Original text regions
        question: Classification question
        model: Model for folding strategies
        strategy: Which strategy to use for flickering regions
        big_model: Bigger model for ESCALATE strategy
        stability_threshold: Below this = flickering

    Returns:
        AttentionFoldResult with resolved signals
    """
    stable_regions: list[SignalStability] = []
    folded_regions: list[FoldedRegion] = []
    final_signals: list[int] = [0] * len(regions)

    for region_stability in initial_scan.regions:
        idx = region_stability.index

        if region_stability.stability >= stability_threshold:
            # Stable - pass through
            stable_regions.append(region_stability)
            final_signals[idx] = region_stability.mode_signal
        else:
            # Flickering - fold attention
            region_text = regions[idx]
            original_signals = region_stability.signals

            if strategy == FoldStrategy.VOTE:
                folded = await _fold_vote(region_text, question, model, original_signals)
            elif strategy == FoldStrategy.ESCALATE:
                if big_model is None:
                    folded = await _fold_vote(region_text, question, model, original_signals)
                else:
                    folded = await _fold_escalate(
                        region_text, question, big_model, original_signals
                    )
            elif strategy == FoldStrategy.TRIANGULATE:
                folded = await _fold_triangulate(
                    region_text, question, model, original_signals
                )
            elif strategy == FoldStrategy.DECOMPOSE:
                folded = await _fold_decompose(region_text, question, model, original_signals)
            else:
                # Default to vote
                folded = await _fold_vote(region_text, question, model, original_signals)

            # Update with correct index
            folded = FoldedRegion(
                index=idx,
                region=folded.region,
                original_signals=folded.original_signals,
                resolved_signal=folded.resolved_signal,
                confidence=folded.confidence,
                strategy_used=folded.strategy_used,
                details=folded.details,
            )

            folded_regions.append(folded)
            final_signals[idx] = folded.resolved_signal

    # Calculate average confidence for folded regions
    avg_conf = (
        sum(f.confidence for f in folded_regions) / len(folded_regions)
        if folded_regions
        else 1.0
    )

    return AttentionFoldResult(
        stable_regions=tuple(stable_regions),
        folded_regions=tuple(folded_regions),
        final_signals=tuple(final_signals),
        total_regions=len(regions),
        folded_count=len(folded_regions),
        avg_confidence=avg_conf,
    )


