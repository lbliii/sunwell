"""Plan scoring and metrics calculation (RFC-116)."""

import statistics
from typing import TYPE_CHECKING

from sunwell.naaru.artifacts import ArtifactGraph
from sunwell.naaru.planners.metrics import PlanMetrics, PlanMetricsV2

if TYPE_CHECKING:
    from sunwell.naaru.planners.harmonic.utils import extract_keywords

# Import here to avoid circular dependency
from sunwell.naaru.planners.harmonic.utils import extract_keywords as _extract_keywords


def compute_metrics_v1(graph: ArtifactGraph) -> PlanMetrics:
    """Compute V1 metrics for a plan."""
    depth = graph.max_depth()
    leaves = graph.leaves()
    artifacts = list(graph.artifacts.values())
    waves = graph.execution_waves()

    # Compute width (max artifacts in any wave)
    width = max(len(w) for w in waves) if waves else 1

    # Count file conflicts
    file_artifacts: dict[str, list[str]] = {}
    for a in artifacts:
        if a.produces_file:
            file_artifacts.setdefault(a.produces_file, []).append(a.id)
    conflicts = sum(
        len(ids) * (len(ids) - 1) // 2  # Combinations
        for ids in file_artifacts.values()
        if len(ids) > 1
    )

    artifact_count = len(artifacts)

    return PlanMetrics(
        depth=depth,
        width=width,
        leaf_count=len(leaves),
        artifact_count=artifact_count,
        parallelism_factor=len(leaves) / max(artifact_count, 1),
        balance_factor=width / max(depth, 1),
        file_conflicts=conflicts,
        estimated_waves=len(waves),
    )


def compute_metrics_v2(graph: ArtifactGraph, goal: str) -> PlanMetricsV2:
    """Compute V2 metrics for a plan (RFC-116).

    V2 adds:
    - Wave analysis (avg_wave_width, parallel_work_ratio, wave_variance)
    - Semantic signals (keyword_coverage, has_convergence)
    - Depth utilization (using depth productively)
    """
    # Base metrics (same as V1)
    depth = graph.max_depth()
    leaves = graph.leaves()
    artifacts = list(graph.artifacts.values())
    waves = graph.execution_waves()

    # Compute width (max artifacts in any wave)
    width = max(len(w) for w in waves) if waves else 1

    # Count file conflicts
    file_artifacts: dict[str, list[str]] = {}
    for a in artifacts:
        if a.produces_file:
            file_artifacts.setdefault(a.produces_file, []).append(a.id)
    conflicts = sum(
        len(ids) * (len(ids) - 1) // 2  # Combinations
        for ids in file_artifacts.values()
        if len(ids) > 1
    )

    artifact_count = len(artifacts)
    num_waves = len(waves)

    # V2: Wave analysis
    wave_sizes = tuple(len(w) for w in waves)
    avg_wave_width = artifact_count / max(num_waves, 1)
    parallel_work_ratio = (artifact_count - 1) / max(num_waves - 1, 1)
    wave_variance = statistics.stdev(wave_sizes) if len(wave_sizes) > 1 else 0.0

    # V2: Depth utilization — high value = doing parallel work relative to depth
    depth_utilization = avg_wave_width / max(depth, 1)

    # V2: Lightweight semantic check — keyword coverage
    goal_keywords = set(_extract_keywords(goal))
    artifact_keywords: set[str] = set()
    for artifact in artifacts:
        artifact_keywords.update(_extract_keywords(artifact.description))
        artifact_keywords.update(_extract_keywords(artifact.id))

    if goal_keywords:
        keyword_coverage = len(goal_keywords & artifact_keywords) / len(goal_keywords)
    else:
        keyword_coverage = 1.0  # No keywords = assume full coverage

    # V2: Convergence check — single root is proper DAG structure
    roots = graph.roots()
    has_convergence = len(roots) == 1

    return PlanMetricsV2(
        # Base metrics (V1)
        depth=depth,
        width=width,
        leaf_count=len(leaves),
        artifact_count=artifact_count,
        parallelism_factor=len(leaves) / max(artifact_count, 1),
        balance_factor=width / max(depth, 1),
        file_conflicts=conflicts,
        estimated_waves=num_waves,
        # V2 extensions
        wave_sizes=wave_sizes,
        avg_wave_width=avg_wave_width,
        parallel_work_ratio=parallel_work_ratio,
        wave_variance=wave_variance,
        keyword_coverage=keyword_coverage,
        has_convergence=has_convergence,
        depth_utilization=depth_utilization,
    )
