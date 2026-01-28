"""Contract verification event schemas.

Schemas for contract verification events emitted during Protocol compliance checking.
"""

from typing import TypedDict


class MethodMismatchData(TypedDict, total=False):
    """Data about a method mismatch in contract verification."""

    method_name: str
    """Name of the method with the issue."""

    issue: str
    """Description of the mismatch."""

    expected: str
    """Expected signature or value."""

    actual: str
    """Actual signature or value found."""


class TierResultData(TypedDict, total=False):
    """Data about a verification tier result."""

    tier: str
    """Which tier: 'ast', 'type_check', or 'llm'."""

    passed: bool
    """Whether this tier's check passed."""

    message: str
    """Human-readable explanation."""

    duration_ms: int
    """Time taken for this check in milliseconds."""


class ContractVerifyStartData(TypedDict, total=False):
    """Data for contract_verify_start event."""

    task_id: str
    """ID of the task being verified."""

    protocol_name: str
    """Name of the Protocol being verified against."""

    implementation_file: str
    """Path to the implementation file."""

    contract_file: str
    """Path to the contract/Protocol file."""


class ContractVerifyPassData(TypedDict, total=False):
    """Data for contract_verify_pass event."""

    task_id: str
    """ID of the task that was verified."""

    protocol_name: str
    """Name of the Protocol that was satisfied."""

    implementation_file: str
    """Path to the implementation file."""

    final_tier: str
    """Which tier produced the final verdict: 'ast', 'type_check', or 'llm'."""

    tier_results: list[TierResultData]
    """Results from each verification tier run."""

    duration_ms: int
    """Total verification time in milliseconds."""


class ContractVerifyFailData(TypedDict, total=False):
    """Data for contract_verify_fail event."""

    task_id: str
    """ID of the task that failed verification."""

    protocol_name: str
    """Name of the Protocol that was not satisfied."""

    implementation_file: str
    """Path to the implementation file."""

    final_tier: str
    """Which tier produced the final verdict: 'ast', 'type_check', or 'llm'."""

    tier_results: list[TierResultData]
    """Results from each verification tier run."""

    mismatches: list[MethodMismatchData]
    """List of method mismatches found."""

    error_message: str
    """Human-readable error summary."""

    duration_ms: int
    """Total verification time in milliseconds."""
