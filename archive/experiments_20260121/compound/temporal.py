"""Temporal differencing pattern for compound eye architecture."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from difflib import SequenceMatcher

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.experiments.compound.types import (
    RegionStability,
    TemporalDiffResult,
    TemporalFrame,
)


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
            frame_id=i,
            content_hash=_hash_content(result.text),
            content=result.text.strip(),
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

        # Compute hashes for each variant
        frame_hashes = tuple(_hash_content(v) for v in variants)

        region_stability.append(
            RegionStability(
                index=region_idx,
                region_text=rep_text[:100],  # Truncate for storage
                frame_hashes=frame_hashes,
                stability_score=stability,
                is_stable=stability >= stability_threshold,
            )
        )

    # Classify regions
    stable_indices = tuple(r.index for r in region_stability if r.is_stable)
    unstable_indices = tuple(r.index for r in region_stability if not r.is_stable)

    # Overall stability
    overall = (
        sum(r.stability_score for r in region_stability) / len(region_stability)
        if region_stability
        else 1.0
    )

    return TemporalDiffResult(
        frames=tuple(frames),
        regions=tuple(region_stability),
        unstable_regions=unstable_indices,
        overall_stability=overall,
        n_frames=n_frames,
        stability_threshold=stability_threshold,
    )


