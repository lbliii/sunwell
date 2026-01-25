"""Integration-Aware Task Decomposition (RFC-067).

This module implements explicit wiring task generation.
Instead of hoping AI wires things up, we make wiring tasks first-class.

Key innovation: Wire tasks are explicit, not implicit.

Before (implicit wiring):
    Goal: Add user authentication
    - Create User model
    - Create JWT helpers
    - Create login route

After (explicit wiring):
    Goal: Add user authentication
    Subtasks:
      1. [Create] src/models/user.py::User
      2. [Create] src/auth/jwt.py::create_token, verify_token
      3. [Wire] auth/jwt.py imports User from models
      4. [Create] src/routes/login.py::login_handler
      5. [Wire] routes/login.py imports create_token from auth
      6. [Wire] Register /login route in app.py
      7. [Verify] Full auth flow works end-to-end
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.integration.types import (
    IntegrationCheck,
    IntegrationCheckType,
    IntegrationType,
    ProducedArtifact,
    RequiredIntegration,
    TaskType,
)

# =============================================================================
# Integration-Aware Goal
# =============================================================================


@dataclass(frozen=True, slots=True)
class IntegrationAwareGoal:
    """A goal with explicit integration contracts (RFC-067).

    This extends the base Goal concept with:
    - What artifacts this goal produces
    - How this goal integrates with its dependencies
    - Verification checks to run after completion
    - Explicit task type (create, wire, verify)

    The key insight: modeling WHAT is produced and HOW it connects
    allows us to verify completeness, not just ordering.

    Attributes:
        id: Unique goal identifier
        title: Human-readable title
        description: Detailed description
        requires: Goal IDs this depends on (ordering)
        produces: Artifacts this goal creates
        integrations: How this goal connects to dependencies
        verification_checks: Checks to run after completion
        task_type: Whether this is create, wire, or verify

    Example:
        >>> goal = IntegrationAwareGoal(
        ...     id="auth-3",
        ...     title="Wire JWT to User model",
        ...     description="Add import of User in JWT module",
        ...     requires=frozenset(["auth-1", "auth-2"]),
        ...     produces=(),  # Wire tasks don't produce new artifacts
        ...     integrations=(
        ...         RequiredIntegration(
        ...             artifact_id="UserModel",
        ...             integration_type=IntegrationType.IMPORT,
        ...             contract="User dataclass",
        ...             target_file=Path("src/auth/jwt.py"),
        ...         ),
        ...     ),
        ...     verification_checks=(
        ...         IntegrationCheck(
        ...             check_type=IntegrationCheckType.IMPORT_EXISTS,
        ...             target_file=Path("src/auth/jwt.py"),
        ...             pattern="from src.models.user import User",
        ...         ),
        ...     ),
        ...     task_type=TaskType.WIRE,
        ... )
    """

    id: str
    """Unique goal identifier."""

    title: str
    """Human-readable title."""

    description: str
    """Detailed description."""

    requires: frozenset[str] = field(default_factory=frozenset)
    """Goal IDs this depends on (ordering)."""

    produces: tuple[ProducedArtifact, ...] = ()
    """Artifacts this goal creates."""

    integrations: tuple[RequiredIntegration, ...] = ()
    """How this goal connects to dependencies."""

    verification_checks: tuple[IntegrationCheck, ...] = ()
    """Checks to run after completion."""

    task_type: TaskType = TaskType.CREATE
    """Whether this is create, wire, verify, or refactor."""

    priority: float = 0.5
    """0-1, higher = more urgent."""

    metadata: tuple[tuple[str, Any], ...] = ()
    """Additional context as immutable key-value pairs."""

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key."""
        return dict(self.metadata).get(key, default)

    def is_wire_task(self) -> bool:
        """Check if this is a wiring task."""
        return self.task_type == TaskType.WIRE

    def is_verify_task(self) -> bool:
        """Check if this is a verification task."""
        return self.task_type == TaskType.VERIFY

    def get_produced_symbols(self) -> frozenset[str]:
        """Get all symbols produced by this goal."""
        symbols: set[str] = set()
        for artifact in self.produces:
            symbols.update(artifact.exports)
            symbols.add(artifact.id)
        return frozenset(symbols)

    def get_required_artifacts(self) -> frozenset[str]:
        """Get all artifact IDs required by integrations."""
        return frozenset(i.artifact_id for i in self.integrations)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "requires": list(self.requires),
            "produces": [p.to_dict() for p in self.produces],
            "integrations": [i.to_dict() for i in self.integrations],
            "verification_checks": [c.to_dict() for c in self.verification_checks],
            "task_type": self.task_type.value,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrationAwareGoal:
        """Create from dict."""
        metadata_dict = data.get("metadata", {})
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            requires=frozenset(data.get("requires", [])),
            produces=tuple(
                ProducedArtifact.from_dict(p) for p in data.get("produces", [])
            ),
            integrations=tuple(
                RequiredIntegration.from_dict(i) for i in data.get("integrations", [])
            ),
            verification_checks=tuple(
                IntegrationCheck.from_dict(c) for c in data.get("verification_checks", [])
            ),
            task_type=TaskType(data.get("task_type", "create")),
            priority=data.get("priority", 0.5),
            metadata=tuple(metadata_dict.items()),
        )


# =============================================================================
# Decomposition Helpers
# =============================================================================


@dataclass(slots=True)
class ArtifactDefinition:
    """Intermediate representation of an artifact during planning."""

    id: str
    description: str
    artifact_type: str
    file_path: str
    exports: list[str]
    depends_on: list[str]

    def to_produced_artifact(self) -> ProducedArtifact:
        """Convert to ProducedArtifact."""
        return ProducedArtifact(
            id=self.id,
            artifact_type=self.artifact_type,  # type: ignore[arg-type]
            location=f"{self.file_path}:{self.exports[0]}" if self.exports else self.file_path,
            contract=self.description,
            exports=frozenset(self.exports),
        )


@dataclass(slots=True)
class IntegrationDefinition:
    """Intermediate representation of an integration during planning."""

    source_artifact: str
    target_artifact: str
    integration_type: IntegrationType
    target_file: str
    verification_pattern: str | None = None

    def to_required_integration(self) -> RequiredIntegration:
        """Convert to RequiredIntegration."""
        return RequiredIntegration(
            artifact_id=self.target_artifact,
            integration_type=self.integration_type,
            contract=f"Integration of {self.target_artifact}",
            target_file=Path(self.target_file) if self.target_file else None,
            verification_pattern=self.verification_pattern,
        )


# =============================================================================
# Decomposition Functions
# =============================================================================


def create_wire_task(
    wire_id: str,
    source_artifact: ArtifactDefinition,
    target_artifact: ArtifactDefinition,
    integration_type: IntegrationType = IntegrationType.IMPORT,
) -> IntegrationAwareGoal:
    """Create an explicit wire task between two artifacts.

    Args:
        wire_id: Unique ID for this wire task
        source_artifact: Artifact that needs the integration
        target_artifact: Artifact being integrated
        integration_type: How to integrate (import, call, etc.)

    Returns:
        IntegrationAwareGoal for the wire task
    """
    # Determine verification pattern based on integration type
    target_symbol = (
        target_artifact.exports[0] if target_artifact.exports else target_artifact.id
    )
    if integration_type == IntegrationType.IMPORT:
        module_path = target_artifact.file_path.replace("/", ".")
        pattern = f"from.*{module_path}.*import.*{target_symbol}"
    elif integration_type == IntegrationType.CALL:
        pattern = f"{target_symbol}\\("
    else:
        pattern = target_artifact.id

    check_type = (
        IntegrationCheckType.IMPORT_EXISTS
        if integration_type == IntegrationType.IMPORT
        else IntegrationCheckType.CALL_EXISTS
    )
    check = IntegrationCheck(
        check_type=check_type,
        target_file=Path(source_artifact.file_path),
        pattern=pattern,
        required=True,
        description=f"Verify {source_artifact.id} {integration_type.value}s {target_artifact.id}",
    )

    integration = RequiredIntegration(
        artifact_id=target_artifact.id,
        integration_type=integration_type,
        contract=target_artifact.description,
        target_file=Path(source_artifact.file_path),
        verification_pattern=pattern,
    )

    return IntegrationAwareGoal(
        id=wire_id,
        title=f"Wire: {source_artifact.id} ← {target_artifact.id}",
        description=(
            f"Add {integration_type.value} of {target_artifact.id} "
            f"in {source_artifact.file_path}"
        ),
        requires=frozenset([source_artifact.id, target_artifact.id]),
        produces=(),  # Wire tasks don't create new artifacts
        integrations=(integration,),
        verification_checks=(check,),
        task_type=TaskType.WIRE,
        priority=0.7,  # Wire tasks are important
    )


def create_verify_task(
    verify_id: str,
    goal_description: str,
    artifacts: list[ArtifactDefinition],
    depends_on: list[str],
) -> IntegrationAwareGoal:
    """Create a final verification task for a goal.

    Args:
        verify_id: Unique ID for this verify task
        goal_description: What we're verifying
        artifacts: All artifacts that should exist
        depends_on: All task IDs that must complete first

    Returns:
        IntegrationAwareGoal for the verify task
    """
    checks: list[IntegrationCheck] = []

    for artifact in artifacts:
        # Add no-stubs check
        if artifact.file_path.endswith(".py"):
            checks.append(IntegrationCheck(
                check_type=IntegrationCheckType.NO_STUBS,
                target_file=Path(artifact.file_path),
                pattern=artifact.exports[0] if artifact.exports else artifact.id,
                required=True,
                description=f"Verify {artifact.id} has no stub implementations",
            ))

        # Add orphan check
        checks.append(IntegrationCheck(
            check_type=IntegrationCheckType.USED_NOT_ORPHAN,
            target_file=Path(artifact.file_path),
            pattern=artifact.exports[0] if artifact.exports else artifact.id,
            required=False,  # Warning only for orphans at verify stage
            description=f"Verify {artifact.id} is not orphaned",
        ))

    return IntegrationAwareGoal(
        id=verify_id,
        title=f"Verify: {goal_description}",
        description=f"Verify all integrations for: {goal_description}",
        requires=frozenset(depends_on),
        produces=(),
        integrations=(),
        verification_checks=tuple(checks),
        task_type=TaskType.VERIFY,
        priority=0.5,
    )


def decompose_with_wiring(
    goal_id: str,
    goal_description: str,
    artifacts: list[ArtifactDefinition],
) -> list[IntegrationAwareGoal]:
    """Decompose a goal into create + wire + verify tasks.

    This is the core function that makes wiring explicit.

    Args:
        goal_id: Base ID for the goal
        goal_description: What we're building
        artifacts: Artifacts to create (with their dependencies)

    Returns:
        List of IntegrationAwareGoal with explicit wire tasks

    Example:
        >>> artifacts = [
        ...     ArtifactDefinition(
        ...         id="UserModel",
        ...         description="User dataclass",
        ...         artifact_type="class",
        ...         file_path="src/models/user.py",
        ...         exports=["User"],
        ...         depends_on=[],
        ...     ),
        ...     ArtifactDefinition(
        ...         id="JWTHelpers",
        ...         description="JWT token helpers",
        ...         artifact_type="module",
        ...         file_path="src/auth/jwt.py",
        ...         exports=["create_token", "verify_token"],
        ...         depends_on=["UserModel"],  # Needs to import User
        ...     ),
        ... ]
        >>> tasks = decompose_with_wiring("auth", "Add authentication", artifacts)
        >>> for task in tasks:
        ...     print(f"[{task.task_type.value}] {task.title}")
        [create] Create UserModel
        [create] Create JWTHelpers
        [wire] Wire: JWTHelpers ← UserModel
        [verify] Verify: Add authentication
    """
    tasks: list[IntegrationAwareGoal] = []
    artifact_map = {a.id: a for a in artifacts}
    task_counter = 1

    # 1. Generate CREATE tasks for each artifact
    for artifact in artifacts:
        create_task = IntegrationAwareGoal(
            id=f"{goal_id}-{task_counter}",
            title=f"Create {artifact.id}",
            description=f"Create {artifact.description}",
            requires=frozenset(),  # Dependencies handled by wire tasks
            produces=(artifact.to_produced_artifact(),),
            integrations=(),
            verification_checks=(
                IntegrationCheck(
                    check_type=IntegrationCheckType.NO_STUBS,
                    target_file=Path(artifact.file_path),
                    pattern=artifact.exports[0] if artifact.exports else artifact.id,
                    required=True,
                    description=f"Ensure {artifact.id} is fully implemented",
                ),
            ),
            task_type=TaskType.CREATE,
            priority=0.8,
        )
        tasks.append(create_task)
        task_counter += 1

    # 2. Generate WIRE tasks for each dependency relationship
    wire_task_ids: list[str] = []
    for artifact in artifacts:
        for dep_id in artifact.depends_on:
            if dep_id in artifact_map:
                dep_artifact = artifact_map[dep_id]
                wire_task = create_wire_task(
                    wire_id=f"{goal_id}-{task_counter}",
                    source_artifact=artifact,
                    target_artifact=dep_artifact,
                    integration_type=IntegrationType.IMPORT,
                )
                tasks.append(wire_task)
                wire_task_ids.append(wire_task.id)
                task_counter += 1

    # 3. Generate final VERIFY task
    all_task_ids = [t.id for t in tasks]
    verify_task = create_verify_task(
        verify_id=f"{goal_id}-verify",
        goal_description=goal_description,
        artifacts=artifacts,
        depends_on=all_task_ids,
    )
    tasks.append(verify_task)

    return tasks


# =============================================================================
# Route Registration Detection
# =============================================================================


def create_route_registration_task(
    task_id: str,
    route_artifact: ArtifactDefinition,
    app_file: str,
    route_path: str,
) -> IntegrationAwareGoal:
    """Create a task to register a route in the app.

    This is a common wiring task that's often forgotten.

    Args:
        task_id: Unique ID
        route_artifact: The route handler artifact
        app_file: Main app file (e.g., app.py, main.py)
        route_path: The URL path (e.g., /api/login)

    Returns:
        IntegrationAwareGoal for route registration
    """
    return IntegrationAwareGoal(
        id=task_id,
        title=f"Wire: Register {route_path} route",
        description=f"Register {route_artifact.id} at {route_path} in {app_file}",
        requires=frozenset([route_artifact.id]),
        produces=(),
        integrations=(
            RequiredIntegration(
                artifact_id=route_artifact.id,
                integration_type=IntegrationType.ROUTE,
                contract=f"Route at {route_path}",
                target_file=Path(app_file),
                verification_pattern=route_path,
            ),
        ),
        verification_checks=(
            IntegrationCheck(
                check_type=IntegrationCheckType.ROUTE_REGISTERED,
                target_file=Path(app_file),
                pattern=route_path,
                required=True,
                description=f"Verify {route_path} is registered",
            ),
            IntegrationCheck(
                check_type=IntegrationCheckType.IMPORT_EXISTS,
                target_file=Path(app_file),
                pattern=route_artifact.exports[0] if route_artifact.exports else route_artifact.id,
                required=True,
                description=f"Verify {route_artifact.id} is imported in {app_file}",
            ),
        ),
        task_type=TaskType.WIRE,
        priority=0.75,
    )


# =============================================================================
# Frontend-Backend Integration
# =============================================================================


def create_frontend_api_wire_task(
    task_id: str,
    frontend_file: str,
    api_endpoint: str,
    backend_artifact_id: str,
) -> IntegrationAwareGoal:
    """Create a task to wire frontend to backend API.

    This catches the common failure of creating API but not calling it.

    Args:
        task_id: Unique ID
        frontend_file: Frontend component file
        api_endpoint: The API endpoint to call
        backend_artifact_id: The backend route artifact

    Returns:
        IntegrationAwareGoal for frontend-backend wiring
    """
    return IntegrationAwareGoal(
        id=task_id,
        title=f"Wire: Frontend calls {api_endpoint}",
        description=f"Add fetch/axios call to {api_endpoint} in {frontend_file}",
        requires=frozenset([backend_artifact_id]),
        produces=(),
        integrations=(
            RequiredIntegration(
                artifact_id=backend_artifact_id,
                integration_type=IntegrationType.CALL,
                contract=f"API call to {api_endpoint}",
                target_file=Path(frontend_file),
                verification_pattern=f"fetch.*{api_endpoint}|axios.*{api_endpoint}",
            ),
        ),
        verification_checks=(
            IntegrationCheck(
                check_type=IntegrationCheckType.CALL_EXISTS,
                target_file=Path(frontend_file),
                pattern=api_endpoint,
                required=True,
                description=f"Verify frontend calls {api_endpoint}",
            ),
        ),
        task_type=TaskType.WIRE,
        priority=0.7,
    )
