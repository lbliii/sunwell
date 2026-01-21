"""Integration-Aware DAG (RFC-067).

This module implements explicit artifact tracking and integration verification
to solve the "building without wiring" problem common in AI code generation.

Key innovations:
1. Explicit artifacts with contracts (ProducedArtifact)
2. Required integrations as first-class (RequiredIntegration)
3. Wire tasks as explicit DAG nodes
4. Integration verification layer

Example:
    >>> from sunwell.integration import IntegrationVerifier, ProducedArtifact
    >>>
    >>> artifact = ProducedArtifact(
    ...     id="UserModel",
    ...     artifact_type="class",
    ...     location="src/models/user.py:User",
    ...     contract="User dataclass with id, email, password_hash",
    ...     exports=frozenset(["User"]),
    ... )
    >>>
    >>> verifier = IntegrationVerifier(project_root)
    >>> result = await verifier.verify_artifact_connected(artifact)
    >>> if not result.connected:
    ...     print(f"Orphan detected: {artifact.id}")
"""

from sunwell.integration.decomposer import (
    ArtifactDefinition,
    IntegrationAwareGoal,
    IntegrationDefinition,
    create_frontend_api_wire_task,
    create_route_registration_task,
    create_verify_task,
    create_wire_task,
    decompose_with_wiring,
)
from sunwell.integration.types import (
    IntegrationCheck,
    IntegrationCheckType,
    IntegrationResult,
    IntegrationType,
    IntegrationVerificationSummary,
    OrphanDetection,
    ProducedArtifact,
    RequiredIntegration,
    StubDetection,
    TaskType,
)
from sunwell.integration.verifier import IntegrationVerifier

__all__ = [
    # Core Types
    "ProducedArtifact",
    "RequiredIntegration",
    "IntegrationCheck",
    "IntegrationResult",
    "StubDetection",
    "OrphanDetection",
    "IntegrationVerificationSummary",
    # Enums
    "IntegrationType",
    "IntegrationCheckType",
    "TaskType",
    # Integration-Aware Goal
    "IntegrationAwareGoal",
    "ArtifactDefinition",
    "IntegrationDefinition",
    # Verifier
    "IntegrationVerifier",
    # Decomposition Functions
    "decompose_with_wiring",
    "create_wire_task",
    "create_verify_task",
    "create_route_registration_task",
    "create_frontend_api_wire_task",
]
