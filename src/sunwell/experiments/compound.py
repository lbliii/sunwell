"""Compound Eye Architecture — Bio-inspired multi-model patterns.

Inspired by how insect compound eyes work:
- Ommatidia: Many tiny independent units, each a complete sensor
- Lateral Inhibition: Adjacent units suppress each other, enhancing edges
- Temporal Differencing: Comparing sequential "frames" detects motion/change

Key insight: Compound eyes excel at detecting CHANGE and BOUNDARIES,
not high-resolution static images. Same principle for LLMs:
- Don't ask "is this good?" — ask "where does the signal CHANGE?"
- Don't trust one run — compare multiple runs to find UNCERTAINTY.

Patterns:
1. Lateral Inhibition: Adjacent model calls inhibit each other.
   High signal where neighbors differ = edge/anomaly worth investigating.

2. Temporal Differencing: Same prompt, multiple runs.
   Regions that change between runs = model uncertainty.

Example:
    >>> from sunwell.experiments.compound import (
    ...     lateral_inhibition_scan,
    ...     temporal_diff_scan,
    ...     compound_eye_scan,
    ... )
    >>>
    >>> # Find edges/anomalies in code
    >>> edges = await lateral_inhibition_scan(
    ...     code_chunks,
    ...     question="Rate danger 0-2",
    ...     model=OllamaModel("gemma3:1b"),
    ... )
    >>> print(f"Edges at: {edges.edge_indices}")
    >>>
    >>> # Find uncertain regions
    >>> motion = await temporal_diff_scan(
    ...     prompt="Explain this code",
    ...     model=OllamaModel("gemma3:1b"),
    ...     n_frames=3,
    ... )
    >>> print(f"Flickering regions: {motion.unstable_regions}")
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:

    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class OmmatidiumSignal:
    """Signal from a single ommatidium (one model call on one region)."""

    index: int
    """Position in the sequence."""

    region: str
    """The text/code region this ommatidium observed."""

    raw_signal: float
    """Raw signal strength (0.0-1.0)."""

    inhibited_signal: float
    """Signal after lateral inhibition (can be negative, clamped to 0)."""

    response: str
    """Full model response."""


@dataclass(frozen=True, slots=True)
class LateralInhibitionResult:
    """Result from lateral inhibition scan."""

    signals: tuple[OmmatidiumSignal, ...]
    """All ommatidium signals."""

    edge_indices: tuple[int, ...]
    """Indices where edges were detected (high inhibited signal)."""

    edge_threshold: float
    """Threshold used for edge detection."""

    total_regions: int
    """Total number of regions scanned."""

    edges_found: int
    """Number of edges detected."""

    @property
    def edge_ratio(self) -> float:
        """Ratio of edges to total regions."""
        return self.edges_found / self.total_regions if self.total_regions > 0 else 0.0

    def get_edge_regions(self) -> list[str]:
        """Get the text of edge regions."""
        return [self.signals[i].region for i in self.edge_indices]


@dataclass(frozen=True, slots=True)
class TemporalFrame:
    """A single frame (one run of the model)."""

    frame_index: int
    """Which frame this is (0, 1, 2, ...)."""

    content: str
    """The model's output for this frame."""

    content_hash: str
    """Hash of content for quick comparison."""


@dataclass(frozen=True, slots=True)
class RegionStability:
    """Stability analysis for a region of text."""

    region_index: int
    """Index of this region."""

    region_text: str
    """Representative text (from first frame)."""

    stability_score: float
    """How stable this region is across frames (0=flickering, 1=stable)."""

    variants: tuple[str, ...]
    """Different versions seen across frames."""

    is_stable: bool
    """Whether this region is considered stable."""


@dataclass(frozen=True, slots=True)
class TemporalDiffResult:
    """Result from temporal differencing scan."""

    frames: tuple[TemporalFrame, ...]
    """All frames captured."""

    regions: tuple[RegionStability, ...]
    """Stability analysis per region."""

    stable_regions: tuple[int, ...]
    """Indices of stable regions."""

    unstable_regions: tuple[int, ...]
    """Indices of unstable (flickering) regions."""

    overall_stability: float
    """Overall stability score (0-1)."""

    n_frames: int
    """Number of frames captured."""

    @property
    def flicker_ratio(self) -> float:
        """Ratio of unstable to total regions."""
        total = len(self.regions)
        return len(self.unstable_regions) / total if total > 0 else 0.0

    def get_unstable_text(self) -> list[str]:
        """Get representative text of unstable regions."""
        return [self.regions[i].region_text for i in self.unstable_regions]


@dataclass(frozen=True, slots=True)
class CompoundEyeResult:
    """Combined result from full compound eye scan."""

    lateral: LateralInhibitionResult
    """Lateral inhibition results (spatial edges)."""

    temporal: TemporalDiffResult
    """Temporal differencing results (uncertainty)."""

    hotspots: tuple[int, ...]
    """Indices that are BOTH edges AND unstable (highest priority)."""

    @property
    def has_hotspots(self) -> bool:
        """Whether any hotspots were detected."""
        return len(self.hotspots) > 0


# =============================================================================
# Lateral Inhibition
# =============================================================================


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


# =============================================================================
# Temporal Differencing
# =============================================================================


def _hash_content(content: str) -> str:
    """Create a hash of content for quick comparison."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _split_into_regions(text: str, method: str = "sentence") -> list[str]:
    """Split text into regions for stability analysis.

    Args:
        text: Text to split
        method: "sentence", "paragraph", or "line"

    Returns:
        List of text regions
    """
    if method == "paragraph":
        regions = [p.strip() for p in text.split("\n\n") if p.strip()]
    elif method == "line":
        regions = [line.strip() for line in text.split("\n") if line.strip()]
    else:  # sentence
        # Simple sentence splitting (handles ., !, ?)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        regions = [s.strip() for s in sentences if s.strip()]

    return regions if regions else [text]


def _compute_region_similarity(regions_a: list[str], regions_b: list[str]) -> list[float]:
    """Compute similarity between corresponding regions of two frames.

    Uses SequenceMatcher for fuzzy matching.
    """
    similarities = []
    max_len = max(len(regions_a), len(regions_b))

    for i in range(max_len):
        a = regions_a[i] if i < len(regions_a) else ""
        b = regions_b[i] if i < len(regions_b) else ""

        if not a and not b:
            similarities.append(1.0)  # Both empty = stable
        elif not a or not b:
            similarities.append(0.0)  # One missing = unstable
        else:
            ratio = SequenceMatcher(None, a, b).ratio()
            similarities.append(ratio)

    return similarities


async def temporal_diff_scan(
    prompt: str,
    model: ModelProtocol,
    n_frames: int = 3,
    region_method: str = "sentence",
    stability_threshold: float = 0.85,
    temperature: float = 0.7,
) -> TemporalDiffResult:
    """Detect uncertainty by comparing multiple runs.

    Like a compound eye detecting motion: regions that change between
    frames indicate uncertainty/instability.

    Args:
        prompt: The prompt to run multiple times
        model: Model to use
        n_frames: Number of frames (runs) to capture
        region_method: How to split output ("sentence", "paragraph", "line")
        stability_threshold: Minimum similarity to count as stable (0-1)
        temperature: Temperature for generation (higher = more variance)

    Returns:
        TemporalDiffResult with stability analysis
    """
    from sunwell.models.protocol import GenerateOptions

    # Capture frames
    frames: list[TemporalFrame] = []
    for i in range(n_frames):
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=temperature, max_tokens=1000),
        )

        frame = TemporalFrame(
            frame_index=i,
            content=result.text.strip(),
            content_hash=_hash_content(result.text),
        )
        frames.append(frame)

    # Split each frame into regions
    frame_regions = [_split_into_regions(f.content, region_method) for f in frames]

    # Find the maximum number of regions across all frames
    max_regions = max(len(r) for r in frame_regions) if frame_regions else 0

    # Analyze stability per region
    region_stability: list[RegionStability] = []

    for region_idx in range(max_regions):
        # Collect variants of this region across frames
        variants = []
        for frame_reg in frame_regions:
            if region_idx < len(frame_reg):
                variants.append(frame_reg[region_idx])
            else:
                variants.append("")  # Missing in this frame

        # Compute pairwise similarities
        similarities = []
        for i in range(len(variants)):
            for j in range(i + 1, len(variants)):
                if variants[i] and variants[j]:
                    sim = SequenceMatcher(None, variants[i], variants[j]).ratio()
                    similarities.append(sim)
                elif not variants[i] and not variants[j]:
                    similarities.append(1.0)
                else:
                    similarities.append(0.0)

        # Average similarity = stability
        stability = sum(similarities) / len(similarities) if similarities else 1.0

        # Get representative text (first non-empty variant)
        rep_text = next((v for v in variants if v), "")

        # Dedupe variants for storage
        unique_variants = tuple(dict.fromkeys(variants))

        region_stability.append(
            RegionStability(
                region_index=region_idx,
                region_text=rep_text[:100],  # Truncate for storage
                stability_score=stability,
                variants=unique_variants,
                is_stable=stability >= stability_threshold,
            )
        )

    # Classify regions
    stable_indices = tuple(r.region_index for r in region_stability if r.is_stable)
    unstable_indices = tuple(r.region_index for r in region_stability if not r.is_stable)

    # Overall stability
    overall = (
        sum(r.stability_score for r in region_stability) / len(region_stability)
        if region_stability
        else 1.0
    )

    return TemporalDiffResult(
        frames=tuple(frames),
        regions=tuple(region_stability),
        stable_regions=stable_indices,
        unstable_regions=unstable_indices,
        overall_stability=overall,
        n_frames=n_frames,
    )


# =============================================================================
# Combined Compound Eye Scan
# =============================================================================


async def compound_eye_scan(
    regions: list[str],
    question: str,
    prompt_template: str,
    model: ModelProtocol,
    n_temporal_frames: int = 3,
    inhibition_strength: float = 0.3,
    edge_threshold: float = 0.3,
    stability_threshold: float = 0.85,
) -> CompoundEyeResult:
    """Full compound eye scan: lateral inhibition + temporal differencing.

    Detects BOTH:
    - Spatial edges (where signals change between adjacent regions)
    - Temporal uncertainty (where model output changes between runs)

    Regions that are BOTH edges AND unstable are "hotspots" —
    highest priority for human review.

    Args:
        regions: List of text regions to scan
        question: Question for lateral inhibition (e.g., "Rate danger 0-2")
        prompt_template: Template for temporal diff, with {region} placeholder
        model: Model to use
        n_temporal_frames: Frames for temporal differencing
        inhibition_strength: Lateral inhibition strength
        edge_threshold: Threshold for edge detection
        stability_threshold: Threshold for stability

    Returns:
        CompoundEyeResult with hotspots identified
    """
    # Run lateral inhibition scan
    lateral = await lateral_inhibition_scan(
        regions=regions,
        question=question,
        model=model,
        inhibition_strength=inhibition_strength,
        edge_threshold=edge_threshold,
    )

    # Run temporal diff on edge regions only (for efficiency)
    # This focuses deep analysis on areas lateral inhibition flagged
    temporal_results: list[RegionStability] = []
    frames_collected: list[TemporalFrame] = []

    for edge_idx in lateral.edge_indices:
        region = regions[edge_idx]
        prompt = prompt_template.format(region=region)

        temp_result = await temporal_diff_scan(
            prompt=prompt,
            model=model,
            n_frames=n_temporal_frames,
            stability_threshold=stability_threshold,
        )

        # Track frames from first edge region
        if not frames_collected:
            frames_collected = list(temp_result.frames)

        # Aggregate region stability (use overall stability for the edge region)
        temporal_results.append(
            RegionStability(
                region_index=edge_idx,
                region_text=region[:100],
                stability_score=temp_result.overall_stability,
                variants=(),  # Don't store all variants for efficiency
                is_stable=temp_result.overall_stability >= stability_threshold,
            )
        )

    # Build temporal result
    stable_indices = tuple(r.region_index for r in temporal_results if r.is_stable)
    unstable_indices = tuple(r.region_index for r in temporal_results if not r.is_stable)

    overall_stability = (
        sum(r.stability_score for r in temporal_results) / len(temporal_results)
        if temporal_results
        else 1.0
    )

    temporal = TemporalDiffResult(
        frames=tuple(frames_collected),
        regions=tuple(temporal_results),
        stable_regions=stable_indices,
        unstable_regions=unstable_indices,
        overall_stability=overall_stability,
        n_frames=n_temporal_frames,
    )

    # Find hotspots: edges that are ALSO unstable
    edge_set = set(lateral.edge_indices)
    unstable_set = set(unstable_indices)
    hotspots = tuple(sorted(edge_set & unstable_set))

    return CompoundEyeResult(
        lateral=lateral,
        temporal=temporal,
        hotspots=hotspots,
    )


# =============================================================================
# Temporal Signal Stability (Trit-based)
# =============================================================================


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


def render_signal_stability_map(result: TemporalSignalResult) -> str:
    """Render temporal signal stability as ASCII visualization."""
    lines = [
        "Temporal Signal Stability Map",
        "=" * 60,
        "",
        f"Frames: {result.n_frames} | Threshold: unanimous or majority",
        "Legend: 🟢=Stable 🔴=Flickering | Signals shown as [0,1,2...]",
        "",
    ]

    for region in result.regions:
        # Stability indicator
        if region.is_unanimous:
            indicator = "🟢"
        elif region.is_stable:
            indicator = "🟡"
        else:
            indicator = "🔴"

        # Signal string
        sig_str = ",".join(str(s) for s in region.signals)

        # Spread indicator
        spread_mark = " ⚠️" if region.spread == 2 else ""

        # Truncate region text
        region_text = region.region[:35].replace("\n", " ").ljust(35)

        lines.append(f"{indicator} [{sig_str}] {region_text}{spread_mark}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(
        f"Stability: {result.overall_stability:.0%} | "
        f"Unanimous: {result.unanimous_count}/{len(result.regions)} | "
        f"Flickering: {len(result.unstable_indices)}"
    )

    if result.high_spread_indices:
        lines.append(f"⚠️  High spread (0↔2): regions {list(result.high_spread_indices)}")

    return "\n".join(lines)


# =============================================================================
# Attention Folding (Focus on Uncertainty)
# =============================================================================


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


def render_attention_fold_map(result: AttentionFoldResult) -> str:
    """Render attention folding result."""
    lines = [
        "Attention Fold Results",
        "=" * 60,
        "",
        f"Total: {result.total_regions} | Stable: {len(result.stable_regions)} | Folded: {result.folded_count}",
        f"Average confidence on folded: {result.avg_confidence:.0%}",
        "",
        "Final Signals:",
    ]

    # Show final signals with indicators
    for i, signal in enumerate(result.final_signals):
        # Check if this was folded
        folded = next((f for f in result.folded_regions if f.index == i), None)

        if folded:
            # Was flickering, now resolved
            orig = ",".join(str(s) for s in folded.original_signals)
            indicator = "🔧"  # Fixed
            conf = f"{folded.confidence:.0%}"
            strategy = folded.strategy_used.value[:4]
            lines.append(
                f"  {indicator} [{i}] [{orig}] → {signal} (conf:{conf}, {strategy})"
            )
        else:
            # Was stable
            indicator = "✅"
            lines.append(f"  {indicator} [{i}] {signal} (stable)")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# =============================================================================
# Utility Functions
# =============================================================================


def chunk_code_by_function(code: str) -> list[str]:
    """Split code into function-level chunks.

    Simple heuristic: split on 'def ' or 'class '.
    """
    # Split on function/class definitions
    pattern = r"(?=\n(?:def |class |async def ))"
    chunks = re.split(pattern, code)

    # Clean up
    chunks = [c.strip() for c in chunks if c.strip()]

    return chunks if chunks else [code]


def chunk_by_lines(text: str, chunk_size: int = 10) -> list[str]:
    """Split text into chunks of N lines."""
    lines = text.split("\n")
    chunks = []

    for i in range(0, len(lines), chunk_size):
        chunk = "\n".join(lines[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks if chunks else [text]


def render_lateral_map(result: LateralInhibitionResult) -> str:
    """Render lateral inhibition result as ASCII visualization."""
    lines = [
        "Lateral Inhibition Map",
        "=" * 60,
        "",
        "Legend: ⚪=0 🟡=1 🔴=2  |  [E]=Edge detected",
        "",
    ]

    for sig in result.signals:
        # Signal indicator
        if sig.raw_signal >= 0.66:
            indicator = "🔴"
        elif sig.raw_signal >= 0.33:
            indicator = "🟡"
        else:
            indicator = "⚪"

        # Edge marker
        edge_mark = " [E]" if sig.index in result.edge_indices else "    "

        # Truncate region text
        region_text = sig.region[:40].replace("\n", " ").ljust(40)

        # Inhibited signal bar
        bar_len = int(sig.inhibited_signal * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)

        lines.append(f"{indicator} [{bar}] {region_text}{edge_mark}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(f"Edges: {result.edges_found}/{result.total_regions} ({result.edge_ratio:.0%})")

    return "\n".join(lines)


def render_temporal_map(result: TemporalDiffResult) -> str:
    """Render temporal differencing result as ASCII visualization."""
    lines = [
        "Temporal Stability Map",
        "=" * 60,
        "",
        f"Frames captured: {result.n_frames}",
        "Legend: 🟢=Stable 🔴=Flickering",
        "",
    ]

    for region in result.regions:
        # Stability indicator
        indicator = "\U0001f7e2" if region.is_stable else "🔴"

        # Stability bar
        bar_len = int(region.stability_score * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)

        # Truncate region text
        region_text = region.region_text[:40].replace("\n", " ").ljust(40)

        lines.append(f"{indicator} [{bar}] {region_text}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(
        f"Stability: {result.overall_stability:.0%} | "
        f"Flickering: {len(result.unstable_regions)}/{len(result.regions)}"
    )

    return "\n".join(lines)


def render_compound_map(result: CompoundEyeResult) -> str:
    """Render full compound eye result."""
    lines = [
        "🪰 Compound Eye Scan Results",
        "=" * 60,
        "",
    ]

    # Lateral summary
    lines.append(f"Lateral Inhibition: {result.lateral.edges_found} edges detected")

    # Temporal summary
    lines.append(
        f"Temporal Stability: {result.temporal.overall_stability:.0%} "
        f"({len(result.temporal.unstable_regions)} flickering)"
    )

    # Hotspots
    if result.hotspots:
        lines.append("")
        lines.append("⚠️  HOTSPOTS (edges + flickering):")
        for idx in result.hotspots:
            region = result.lateral.signals[idx].region[:50].replace("\n", " ")
            lines.append(f"   [{idx}] {region}...")
    else:
        lines.append("")
        lines.append("✅ No hotspots detected")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
