"""Integration-Aware DAG Type Definitions (RFC-067).

This module defines the core types for integration tracking and verification.

Key insight: Current DAGs model ORDERING (what order to work), but not CONNECTION
(did we actually wire things together). These types model both.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

# =============================================================================
# Enums
# =============================================================================


class IntegrationType(Enum):
    """How a component integrates with another.

    These represent the different ways code components connect.
    """

    IMPORT = "import"
    """Python import: from x import y."""

    CALL = "call"
    """Function/method call: obj.method() or func()."""

    ROUTE = "route"
    """Route registration: @app.route('/path')."""

    CONFIG = "config"
    """Configuration entry: KEY=value in settings."""

    INHERIT = "inherit"
    """Class inheritance: class Foo(Bar)."""

    COMPOSE = "compose"
    """Composition: self.component = Component()."""


class IntegrationCheckType(Enum):
    """Types of integration checks."""

    IMPORT_EXISTS = "import_exists"
    """Does file A import symbol X from file B?"""

    CALL_EXISTS = "call_exists"
    """Does function A call function B?"""

    ROUTE_REGISTERED = "route_registered"
    """Is route /foo registered in app?"""

    CONFIG_PRESENT = "config_present"
    """Is key X in config file?"""

    TEST_EXISTS = "test_exists"
    """Is there a test for function X?"""

    USED_NOT_ORPHAN = "used_not_orphan"
    """Is artifact X imported/used anywhere?"""

    NO_STUBS = "no_stubs"
    """Does the implementation contain stubs (pass, TODO, etc.)?"""


class TaskType(Enum):
    """Types of tasks in integration-aware planning.

    The key innovation: Wire tasks are first-class, not implicit.
    """

    CREATE = "create"
    """Create a new artifact (file, class, function)."""

    WIRE = "wire"
    """Connect artifacts together (import, register, call)."""

    VERIFY = "verify"
    """Verify integrations work end-to-end."""

    REFACTOR = "refactor"
    """Restructure without changing behavior."""


# =============================================================================
# Artifact Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProducedArtifact:
    """What a goal/task creates.

    An artifact has identity, location, and a contract defining what it provides.
    Think of it as a Protocol/Interface: the spec is the CONTRACT, the artifact
    is the IMPLEMENTATION.

    Attributes:
        id: Unique identifier (e.g., "UserModel", "login_route")
        artifact_type: What kind of thing: class, function, file, route, config, test
        location: Where it lives: src/models/user.py:User or /api/login
        contract: What this artifact provides (interface/signature)
        exports: Symbols this artifact exports (for import verification)

    Example:
        >>> artifact = ProducedArtifact(
        ...     id="UserModel",
        ...     artifact_type="class",
        ...     location="src/models/user.py:User",
        ...     contract="Dataclass with id: UUID, email: str, password_hash: str",
        ...     exports=frozenset(["User", "UserCreate"]),
        ... )
    """

    id: str
    """Unique artifact ID."""

    artifact_type: Literal["class", "function", "file", "route", "config", "test", "module"]
    """What kind of thing this is."""

    location: str
    """Where it lives: file:symbol or /route/path."""

    contract: str
    """What this artifact provides (interface/signature)."""

    exports: frozenset[str] = field(default_factory=frozenset)
    """Symbols this artifact exports (for import verification)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional context."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "artifact_type": self.artifact_type,
            "location": self.location,
            "contract": self.contract,
            "exports": list(self.exports),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProducedArtifact:
        """Create from dict."""
        return cls(
            id=data["id"],
            artifact_type=data["artifact_type"],
            location=data["location"],
            contract=data["contract"],
            exports=frozenset(data.get("exports", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class RequiredIntegration:
    """How a goal/task connects to its dependencies.

    This makes wiring explicit. Instead of hoping the AI connects things,
    we specify exactly what integration must happen.

    Attributes:
        artifact_id: Which artifact we need
        integration_type: How we connect (import, call, route, config, inherit)
        contract: What we expect from it (e.g., 'function with signature (user_id: str) -> User')
        target_file: File where integration should happen
        verification_pattern: Regex or AST pattern to verify integration exists

    Example:
        >>> integration = RequiredIntegration(
        ...     artifact_id="UserModel",
        ...     integration_type=IntegrationType.IMPORT,
        ...     contract="User dataclass",
        ...     target_file=Path("src/auth/service.py"),
        ...     verification_pattern="from src.models.user import User",
        ... )
    """

    artifact_id: str
    """Which artifact we need."""

    integration_type: IntegrationType
    """How we connect to it."""

    contract: str
    """What we expect from it."""

    target_file: Path | None = None
    """File where integration should happen."""

    verification_pattern: str | None = None
    """Regex or pattern to verify integration exists."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "integration_type": self.integration_type.value,
            "contract": self.contract,
            "target_file": str(self.target_file) if self.target_file else None,
            "verification_pattern": self.verification_pattern,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequiredIntegration:
        """Create from dict."""
        return cls(
            artifact_id=data["artifact_id"],
            integration_type=IntegrationType(data["integration_type"]),
            contract=data["contract"],
            target_file=Path(data["target_file"]) if data.get("target_file") else None,
            verification_pattern=data.get("verification_pattern"),
        )


# =============================================================================
# Verification Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class IntegrationCheck:
    """A check to verify integration happened.

    These checks are run after task completion to verify that artifacts
    are actually wired together, not just created.

    Attributes:
        check_type: What kind of check (import_exists, call_exists, etc.)
        target_file: File to check
        pattern: What to look for (import name, function call, etc.)
        required: If False, warning only. If True, task fails.
        description: Human-readable description of what we're checking

    Example:
        >>> check = IntegrationCheck(
        ...     check_type=IntegrationCheckType.IMPORT_EXISTS,
        ...     target_file=Path("src/auth/service.py"),
        ...     pattern="from src.models.user import User",
        ...     required=True,
        ...     description="Auth service must import User model",
        ... )
    """

    check_type: IntegrationCheckType
    """What kind of check."""

    target_file: Path
    """File to check."""

    pattern: str
    """What to look for (import name, function call, regex)."""

    required: bool = True
    """If False, warning only. If True, task fails."""

    description: str = ""
    """Human-readable description."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "check_type": self.check_type.value,
            "target_file": str(self.target_file),
            "pattern": self.pattern,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrationCheck:
        """Create from dict."""
        return cls(
            check_type=IntegrationCheckType(data["check_type"]),
            target_file=Path(data["target_file"]),
            pattern=data["pattern"],
            required=data.get("required", True),
            description=data.get("description", ""),
        )


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    """Result of verifying an integration.

    Attributes:
        check: The check that was run
        passed: Whether the check passed
        found: What was actually found (if anything)
        message: Human-readable result message
        suggestions: Suggested fixes if failed
    """

    check: IntegrationCheck
    """The check that was run."""

    passed: bool
    """Whether the check passed."""

    found: str | None = None
    """What was actually found."""

    message: str = ""
    """Human-readable result message."""

    suggestions: tuple[str, ...] = ()
    """Suggested fixes if failed."""


@dataclass(frozen=True, slots=True)
class StubDetection:
    """A detected stub/incomplete implementation.

    Stubs are a common AI failure mode: generating function signatures
    but leaving the body as `pass`, `TODO`, or `raise NotImplementedError`.

    Attributes:
        file: File containing the stub
        line: Line number
        symbol: Function/class name
        stub_type: What kind of stub (pass, todo, not_implemented, ellipsis, empty)
        context: Surrounding code for context
    """

    file: Path
    """File containing the stub."""

    line: int
    """Line number."""

    symbol: str
    """Function/class name."""

    stub_type: Literal["pass", "todo", "fixme", "not_implemented", "ellipsis", "empty"]
    """What kind of stub."""

    context: str = ""
    """Surrounding code for context."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "file": str(self.file),
            "line": self.line,
            "symbol": self.symbol,
            "stub_type": self.stub_type,
            "context": self.context,
        }


# =============================================================================
# Orphan Detection Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class OrphanDetection:
    """A detected orphaned artifact.

    Orphans are artifacts that exist but aren't imported or used anywhere.
    This is a common AI failure mode: creating files but never wiring them.

    Attributes:
        artifact: The orphaned artifact
        file: File containing the orphan
        symbol: Class/function name
        suggestion: Suggested fix
    """

    artifact: ProducedArtifact
    """The orphaned artifact."""

    file: Path
    """File containing the orphan."""

    symbol: str
    """Class/function name."""

    suggestion: str = ""
    """Suggested fix."""


# =============================================================================
# Verification Summary
# =============================================================================


@dataclass(frozen=True, slots=True)
class IntegrationVerificationSummary:
    """Summary of all integration verifications for a goal.

    Attributes:
        goal_id: The goal that was verified
        total_checks: Number of checks run
        passed_checks: Number of checks that passed
        failed_required: Number of required checks that failed
        failed_optional: Number of optional checks that failed
        stubs_detected: Stub implementations found
        orphans_detected: Orphaned artifacts found
        results: Individual check results
        overall_passed: Whether the goal passes integration verification
    """

    goal_id: str
    """The goal that was verified."""

    total_checks: int
    """Number of checks run."""

    passed_checks: int
    """Number of checks that passed."""

    failed_required: int
    """Number of required checks that failed."""

    failed_optional: int
    """Number of optional checks that failed."""

    stubs_detected: tuple[StubDetection, ...]
    """Stub implementations found."""

    orphans_detected: tuple[OrphanDetection, ...]
    """Orphaned artifacts found."""

    results: tuple[IntegrationResult, ...]
    """Individual check results."""

    @property
    def overall_passed(self) -> bool:
        """Whether the goal passes integration verification."""
        return self.failed_required == 0 and len(self.stubs_detected) == 0

    @property
    def pass_rate(self) -> float:
        """Percentage of checks that passed."""
        if self.total_checks == 0:
            return 1.0
        return self.passed_checks / self.total_checks

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "goal_id": self.goal_id,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_required": self.failed_required,
            "failed_optional": self.failed_optional,
            "stubs_detected": [s.to_dict() for s in self.stubs_detected],
            "orphans_detected": [
                {
                    "artifact": o.artifact.to_dict(),
                    "file": str(o.file),
                    "symbol": o.symbol,
                    "suggestion": o.suggestion,
                }
                for o in self.orphans_detected
            ],
            "overall_passed": self.overall_passed,
            "pass_rate": self.pass_rate,
        }
