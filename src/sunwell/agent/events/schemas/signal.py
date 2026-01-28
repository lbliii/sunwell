"""Signal event schemas."""

from typing import Any, TypedDict


class SignalData(TypedDict, total=False):
    """Data for signal event."""
    status: str  # Required: "extracting" | "extracted"
    signals: dict[str, Any] | None  # Signal extraction results


class SignalRouteData(TypedDict, total=False):
    """Data for signal_route event.

    Captures routing decisions for adaptive threshold learning.
    """

    route: str  # Required (legacy field, same as strategy)
    complexity: str
    reasoning: str
    # Adaptive routing fields
    confidence: float  # Confidence score used for routing (0.0-1.0)
    strategy: str  # Selected strategy: "vortex" | "interference" | "single_shot"
    threshold_vortex: float  # Threshold for Vortex routing
    threshold_interference: float  # Threshold for Interference routing
    thresholds_adaptive: bool  # True if using learned thresholds
