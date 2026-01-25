"""Gate event schemas."""

from typing import TypedDict


class GateStartData(TypedDict, total=False):
    """Data for gate_start event."""
    gate_id: str  # Required
    gate_type: str  # Required


class GateStepData(TypedDict, total=False):
    """Data for gate_step event."""
    gate_id: str  # Required
    step: str  # Required
    passed: bool  # Required
    message: str


class GatePassData(TypedDict, total=False):
    """Data for gate_pass event."""
    gate_id: str  # Required
    gate_type: str


class GateFailData(TypedDict, total=False):
    """Data for gate_fail event."""
    gate_id: str  # Required
    gate_type: str
    failed_step: str
    errors: list[str]
