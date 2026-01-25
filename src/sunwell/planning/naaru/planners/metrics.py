"""Plan quality metrics for Harmonic Planning (RFC-038, RFC-116)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.planning.naaru.artifacts import ArtifactGraph


@dataclass(frozen=True, slots=True)
class PlanMetrics:
    """Quantitative measures of plan quality (V1 formula).

    These metrics enable comparison and selection of plan candidates.
    Higher composite score = better plan for parallel execution.

    Attributes:
        depth: Critical path length (longest dependency chain)
        width: Maximum parallel artifacts at any level
        leaf_count: Artifacts with no dependencies (can start immediately)
        artifact_count: Total artifacts in the graph
        parallelism_factor: leaf_count / artifact_count (higher = more parallel)
        balance_factor: width / depth (higher = more balanced tree)
        file_conflicts: Pairs of artifacts that modify the same file
        estimated_waves: Minimum execution waves (topological levels)
    """

    depth: int
    """Critical path length (longest dependency chain)."""

    width: int
    """Maximum parallel artifacts at any level."""

    leaf_count: int
    """Artifacts with no dependencies (can start immediately)."""

    artifact_count: int
    """Total artifacts in the graph."""

    parallelism_factor: float
    """leaf_count / artifact_count — higher is more parallel."""

    balance_factor: float
    """width / depth — higher means more balanced tree."""

    file_conflicts: int
    """Pairs of artifacts that modify the same file."""

    estimated_waves: int
    """Minimum execution waves (topological levels)."""

    @property
    def score(self) -> float:
        """V1 composite score (higher is better).

        Formula balances parallelism against complexity:
        - Reward: high parallelism_factor, high balance_factor
        - Penalize: deep graphs, many file conflicts
        """
        return (
            self.parallelism_factor * 40
            + self.balance_factor * 30
            + (1 / max(self.depth, 1)) * 20
            + (1 / (1 + self.file_conflicts)) * 10
        )


@dataclass(frozen=True, slots=True)
class PlanMetricsV2(PlanMetrics):
    """Extended metrics for Harmonic Scoring v2 (RFC-116).

    Adds domain-aware metrics that recognize:
    - Irreducible depth (some goals legitimately require sequential phases)
    - Mid-graph parallelism (fat waves in the middle matter, not just leaves)
    - Semantic coherence (plans should actually cover the goal)

    New Attributes:
        wave_sizes: Size of each execution wave
        avg_wave_width: artifact_count / estimated_waves
        parallel_work_ratio: Work per wave transition
        wave_variance: Standard deviation of wave sizes
        keyword_coverage: Fraction of goal keywords in artifact descriptions
        has_convergence: True if graph has a single root
        depth_utilization: avg_wave_width / depth
    """

    # Wave analysis (new in V2)
    wave_sizes: tuple[int, ...]
    """Size of each execution wave, e.g., (5, 4, 3, 2, 1)."""

    avg_wave_width: float
    """artifact_count / estimated_waves — measures "fatness" of waves."""

    parallel_work_ratio: float
    """(artifacts - 1) / max(estimated_waves - 1, 1) — work per transition."""

    wave_variance: float
    """Standard deviation of wave sizes — lower = more balanced."""

    # Semantic signals (new in V2)
    keyword_coverage: float
    """Fraction of goal keywords found in artifact descriptions (0.0-1.0)."""

    has_convergence: bool
    """True if graph has a single root (proper convergence point)."""

    # Depth context (new in V2)
    depth_utilization: float
    """avg_wave_width / depth — how well we use the depth we have."""

    @property
    def score_v2(self) -> float:
        """RFC-116 v2 composite score — rewards appropriate structure.

        Philosophy:
        - Don't penalize depth; penalize UNUSED depth
        - Reward parallel work at ALL levels, not just leaves
        - Add lightweight semantic sanity check

        Weight allocation:
        - Parallelism (reworked): 35%
        - Structure quality: 30%
        - Semantic coherence: 20%
        - Conflict avoidance: 15%
        """
        return (
            # Parallelism (reworked) — 35%
            self.parallel_work_ratio * 20        # Work per wave transition
            + self.avg_wave_width * 15           # Fat waves = good

            # Structure quality — 30%
            + self.depth_utilization * 20        # Using depth well
            + (1 / (1 + self.wave_variance)) * 10  # Balanced waves

            # Semantic coherence — 20%
            + self.keyword_coverage * 15         # Covers the goal
            + (5 if self.has_convergence else 0)  # Proper DAG structure

            # Conflict avoidance — 15%
            + (1 / (1 + self.file_conflicts)) * 15
        )


@dataclass(frozen=True, slots=True)
class CandidateResult:
    """A plan candidate with stable ID for tracking through transformations.

    Using explicit IDs instead of array indices prevents alignment bugs
    between frontend and backend when candidates are filtered or reordered.
    """

    id: str
    """Stable identifier (e.g., 'candidate-0', 'candidate-1')."""

    graph: "ArtifactGraph"
    """The artifact graph for this candidate."""

    variance_config: dict[str, str | int | float | bool]
    """Configuration used to generate this candidate."""

    score: PlanMetrics | PlanMetricsV2 | None = None
    """Computed metrics (added after scoring)."""
