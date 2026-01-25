"""Signal event schemas."""

from typing import Any, TypedDict


class SignalData(TypedDict, total=False):
    """Data for signal event."""
    status: str  # Required: "extracting" | "extracted"
    signals: dict[str, Any] | None  # Signal extraction results


class SignalRouteData(TypedDict, total=False):
    """Data for signal_route event."""
    route: str  # Required
    complexity: str
    reasoning: str
