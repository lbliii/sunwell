"""Integration-Aware DAG Type Definitions (RFC-067).

Minimal types extracted from removed features.external.integration.types.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class IntegrationType(Enum):
    """How a component integrates with another."""

    IMPORT = "import"
    CALL = "call"
    ROUTE = "route"
    CONFIG = "config"
    INHERIT = "inherit"
    COMPOSE = "compose"


class IntegrationCheckType(Enum):
    """Types of integration checks."""

    IMPORT_EXISTS = "import_exists"
    CALL_EXISTS = "call_exists"
    ROUTE_REGISTERED = "route_registered"
    CONFIG_PRESENT = "config_present"
    TEST_EXISTS = "test_exists"
    USED_NOT_ORPHAN = "used_not_orphan"
    NO_STUBS = "no_stubs"


class TaskType(Enum):
    """Types of tasks in integration-aware planning."""

    CREATE = "create"
    WIRE = "wire"
    VERIFY = "verify"
    REFACTOR = "refactor"


@dataclass(frozen=True, slots=True)
class RequiredIntegration:
    """How a goal/task connects to its dependencies."""

    artifact_id: str
    integration_type: IntegrationType
    contract: str
    target_file: Path | None = None
    verification_pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "integration_type": self.integration_type.value,
            "contract": self.contract,
            "target_file": str(self.target_file) if self.target_file else None,
            "verification_pattern": self.verification_pattern,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequiredIntegration:
        return cls(
            artifact_id=data["artifact_id"],
            integration_type=IntegrationType(data["integration_type"]),
            contract=data["contract"],
            target_file=Path(data["target_file"]) if data.get("target_file") else None,
            verification_pattern=data.get("verification_pattern"),
        )


@dataclass(frozen=True, slots=True)
class IntegrationCheck:
    """A check to verify integration happened."""

    check_type: IntegrationCheckType
    target_file: Path
    pattern: str
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_type": self.check_type.value,
            "target_file": str(self.target_file),
            "pattern": self.pattern,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrationCheck:
        return cls(
            check_type=IntegrationCheckType(data["check_type"]),
            target_file=Path(data["target_file"]),
            pattern=data["pattern"],
            required=data.get("required", True),
            description=data.get("description", ""),
        )


@dataclass(frozen=True, slots=True)
class ProducedArtifact:
    """Artifact produced by a task (for orphan detection)."""

    id: str
    artifact_type: str
    location: str
    file_path: Path


@dataclass(frozen=True, slots=True)
class StubDetection:
    """Detection of stub/unimplemented code."""

    symbol: str
    file_path: Path
    line: int
    check_type: str


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    """Result of an integration verification check."""

    passed: bool
    message: str
    details: dict[str, Any] | None = None


class IntegrationVerifier:
    """Stub verifier - integration feature removed."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    async def detect_orphans(self, produced: list[ProducedArtifact]) -> list[StubDetection]:
        """Stub - returns empty (feature removed)."""
        return []


def decompose_with_wiring(
    tasks: list[Any],
    workspace: Path,
) -> list[Any]:
    """Stub - returns tasks unchanged (feature removed)."""
    return tasks
