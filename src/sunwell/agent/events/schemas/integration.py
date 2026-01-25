"""Integration verification event schemas (RFC-067)."""

from typing import TypedDict


class IntegrationCheckStartData(TypedDict, total=False):
    """Data for integration_check_start event."""
    edge_id: str  # Required
    check_type: str  # Required
    source_artifact: str  # Required
    target_artifact: str  # Required


class IntegrationCheckPassData(TypedDict, total=False):
    """Data for integration_check_pass event."""
    edge_id: str  # Required
    check_type: str  # Required
    verification_method: str  # "ast", "regex", "exists"


class IntegrationCheckFailData(TypedDict, total=False):
    """Data for integration_check_fail event."""
    edge_id: str  # Required
    check_type: str  # Required
    expected: str  # Required
    actual: str  # Required
    suggested_fix: str | None


class StubDetectedData(TypedDict, total=False):
    """Data for stub_detected event."""
    artifact_id: str  # Required
    file_path: str  # Required
    stub_type: str  # Required: "pass", "todo", "not_implemented", "ellipsis"
    location: str  # Required: line:col or function name


class OrphanDetectedData(TypedDict, total=False):
    """Data for orphan_detected event."""
    artifact_id: str  # Required
    file_path: str  # Required


class WireTaskGeneratedData(TypedDict, total=False):
    """Data for wire_task_generated event."""
    task_id: str  # Required
    source_artifact: str  # Required
    target_artifact: str  # Required
    integration_type: str  # Required: "import", "call", "route", etc.
