"""Data structures for compound eye patterns."""

from __future__ import annotations

from dataclasses import dataclass


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
        if self.total_regions == 0:
            return 0.0
        return self.edges_found / self.total_regions

    def get_edge_regions(self) -> list[str]:
        """Get the text regions where edges were detected."""
        return [self.signals[i].region for i in self.edge_indices]


@dataclass(frozen=True, slots=True)
class TemporalFrame:
    """One "frame" from temporal differencing."""

    frame_id: int
    """Frame number (0-indexed)."""

    content_hash: str
    """Hash of the generated content."""

    content: str
    """Full generated content."""


@dataclass(frozen=True, slots=True)
class RegionStability:
    """Stability analysis for one region across frames."""

    index: int
    """Region index."""

    region_text: str
    """The text region."""

    frame_hashes: tuple[str, ...]
    """Content hashes for this region across frames."""

    stability_score: float
    """Stability score (0-1). 1.0 = identical across all frames."""

    is_stable: bool
    """Whether region is stable (above threshold)."""


@dataclass(frozen=True, slots=True)
class TemporalDiffResult:
    """Result from temporal differencing scan."""

    frames: tuple[TemporalFrame, ...]
    """All captured frames."""

    regions: tuple[RegionStability, ...]
    """Stability analysis for each region."""

    unstable_regions: tuple[int, ...]
    """Indices of unstable (flickering) regions."""

    overall_stability: float
    """Overall stability score (0-1)."""

    n_frames: int
    """Number of frames captured."""

    stability_threshold: float
    """Threshold used for stability detection."""


@dataclass(frozen=True, slots=True)
class CompoundEyeResult:
    """Combined result from full compound eye scan."""

    lateral: LateralInhibitionResult
    """Lateral inhibition results."""

    temporal: TemporalDiffResult
    """Temporal differencing results."""

    hotspots: tuple[int, ...]
    """Indices that are BOTH edges AND unstable (highest priority)."""
