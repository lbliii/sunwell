"""Delegation event schemas (RFC-137)."""

from typing import TypedDict


class DelegationStartedData(TypedDict, total=False):
    """Data for delegation_started event."""

    task_description: str
    smart_model: str
    delegation_model: str
    reason: str
    estimated_tokens: int


class EphemeralLensCreatedData(TypedDict, total=False):
    """Data for ephemeral_lens_created event."""

    task_scope: str
    heuristics_count: int
    patterns_count: int
    generated_by: str
    anti_patterns_count: int
    constraints_count: int
