"""Confidence scoring and aggregation module (RFC-100).

This module provides:
1. Confidence scoring for claims and model nodes
2. Provenance tracking for evidence trails
3. Calibration feedback for improving accuracy

Confidence Bands:
- 🟢 High (90-100%): "I'm sure" — no drill-down needed
- 🟡 Moderate (70-89%): "Likely right" — spot check
- 🟠 Low (50-69%): "Uncertain" — review recommended
- 🔴 Uncertain (<50%): "I don't know" — human must verify
"""

from sunwell.quality.confidence.aggregation import (
    ConfidenceLevel,
    Evidence,
    ModelNode,
    aggregate_confidence,
    score_to_band,
)
from sunwell.quality.confidence.calibration import (
    CalibrationTracker,
    ConfidenceFeedback,
)

__all__ = [
    "ConfidenceLevel",
    "Evidence",
    "ModelNode",
    "aggregate_confidence",
    "score_to_band",
    "ConfidenceFeedback",
    "CalibrationTracker",
]
