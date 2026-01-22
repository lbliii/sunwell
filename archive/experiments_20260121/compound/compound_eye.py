"""Combined compound eye scan pattern."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.experiments.compound.lateral import lateral_inhibition_scan
from sunwell.experiments.compound.temporal import temporal_diff_scan
from sunwell.experiments.compound.types import CompoundEyeResult


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


