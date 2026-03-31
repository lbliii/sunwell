"""Self types stub (mirror feature removed)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Minimal ExecutionEvent for tool audit recording."""

    tool_name: str
    success: bool
    latency_ms: float
    error: str | None
    timestamp: datetime


def is_path_blocked(path: str) -> bool:
    """No-op: always False."""
    return False


# Stubs for test compatibility (test file will be removed)
class FailureSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalType:
    REFACTOR = "refactor"
    FIX = "fix"


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class ProposalTestSpec:
    command: str
    timeout_seconds: int = 60
