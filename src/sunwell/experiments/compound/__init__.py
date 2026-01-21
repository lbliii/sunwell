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

from sunwell.experiments.compound.attention import (
    AttentionFoldResult,
    FoldStrategy,
    FoldedRegion,
    attention_fold,
)
from sunwell.experiments.compound.compound_eye import compound_eye_scan
from sunwell.experiments.compound.lateral import lateral_inhibition_scan
from sunwell.experiments.compound.render import (
    render_attention_fold_map,
    render_compound_map,
    render_lateral_map,
    render_signal_stability_map,
    render_temporal_map,
)
from sunwell.experiments.compound.signal import (
    SignalStability,
    TemporalSignalResult,
    temporal_signal_scan,
)
from sunwell.experiments.compound.temporal import temporal_diff_scan
from sunwell.experiments.compound.types import (
    CompoundEyeResult,
    LateralInhibitionResult,
    OmmatidiumSignal,
    RegionStability,
    TemporalDiffResult,
    TemporalFrame,
)
from sunwell.experiments.compound.utils import chunk_by_lines, chunk_code_by_function

__all__ = [
    # Main scan functions
    "lateral_inhibition_scan",
    "temporal_diff_scan",
    "compound_eye_scan",
    "temporal_signal_scan",
    "attention_fold",
    # Types
    "OmmatidiumSignal",
    "LateralInhibitionResult",
    "TemporalFrame",
    "RegionStability",
    "TemporalDiffResult",
    "CompoundEyeResult",
    "SignalStability",
    "TemporalSignalResult",
    "FoldStrategy",
    "FoldedRegion",
    "AttentionFoldResult",
    # Rendering
    "render_lateral_map",
    "render_temporal_map",
    "render_compound_map",
    "render_signal_stability_map",
    "render_attention_fold_map",
    # Utilities
    "chunk_code_by_function",
    "chunk_by_lines",
]
