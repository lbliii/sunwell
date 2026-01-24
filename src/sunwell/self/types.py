"""Type definitions for Self-Knowledge Architecture.

RFC-085: Shared types used across source, analysis, and proposal modules.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# === Source Knowledge Types ===


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Location in Sunwell's source code."""

    module: str
    line: int
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Information about a code symbol (class, function, constant)."""

    name: str
    type: str  # "class", "function", "constant"
    module: str
    source: str
    start_line: int
    end_line: int | None
    docstring: str | None
    methods: tuple[str, ...] = ()  # For classes
    is_async: bool = False  # For functions


@dataclass(frozen=True, slots=True)
class ModuleStructure:
    """Structure of a Python module."""

    module: str
    classes: tuple[dict[str, Any], ...]
    functions: tuple[dict[str, Any], ...]
    imports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result from semantic search across Sunwell's codebase."""

    module: str
    symbol: str | None
    snippet: str
    score: float
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Citation:
    """Citation to source code in an explanation."""

    module: str
    line: int
    end_line: int | None = None
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class Explanation:
    """Generated explanation of a Sunwell concept."""

    topic: str
    summary: str
    details: str
    citations: tuple[Citation, ...]
    related_modules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureDiagram:
    """Architecture diagram generated from source analysis."""

    mermaid: str  # Mermaid diagram syntax
    modules: tuple[str, ...]
    dependencies: tuple[tuple[str, str], ...]  # (from_module, to_module)


# === Analysis Knowledge Types ===


class FailureSeverity(Enum):
    """Severity level of a failure."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class FailureReport:
    """Report of a failure with root cause analysis."""

    error: str
    error_type: str
    root_cause: str | None
    source_location: SourceLocation | None
    timestamp: datetime
    severity: FailureSeverity
    suggestion: str | None = None


@dataclass(slots=True)
class ExecutionEvent:
    """An execution event to record for analysis."""

    tool_name: str
    success: bool
    latency_ms: int
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    model: str | None = None
    user_edited: bool = False


@dataclass(frozen=True, slots=True)
class Hotspot:
    """Error hotspot in the codebase."""

    module: str
    method: str | None
    errors: int
    last_error: datetime


@dataclass(slots=True)
class PatternReport:
    """Report of behavioral patterns."""

    most_used_tools: list[tuple[str, int]]
    error_hotspots: list[Hotspot]
    common_sequences: list[tuple[str, str, int]]  # (tool1, tool2, count)
    total_executions: int
    success_rate: float
    avg_latency_ms: float


@dataclass(slots=True)
class ModelReport:
    """Report comparing model performance."""

    models_tracked: list[str]
    categories_tracked: list[str]
    best_per_category: dict[str, str | None]
    total_entries: int


@dataclass(slots=True)
class Diagnosis:
    """Diagnosis of an error with suggested fixes."""

    error: str
    root_cause: str
    source_location: SourceLocation | None
    similar_past_errors: list[FailureReport]
    suggested_fixes: list[str]
    confidence: float


# === Proposal Types ===


class ProposalStatus(Enum):
    """Status of an improvement proposal."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class ProposalType(Enum):
    """Type of improvement proposal."""

    HEURISTIC = "heuristic"
    VALIDATOR = "validator"
    WORKFLOW = "workflow"
    CONFIG = "config"
    TOOL = "tool"
    CODE = "code"


@dataclass(slots=True)
class FileChange:
    """A change to a source file."""

    path: str  # Relative to source root
    diff: str
    original_content: str | None = None


@dataclass(slots=True)
class ProposalTestSpec:
    """A test specification to verify a proposal.

    Note: Named ProposalTestSpec (not TestCase or ProposalTest) to avoid pytest
    collection warnings since classes starting/ending with 'Test' are collected.
    """

    name: str
    code: str
    expected_outcome: str = "pass"


# Alias for backwards compatibility
ProposalTestCase = ProposalTestSpec  # Alias for backward compatibility


@dataclass(slots=True)
class TestResult:
    """Result of testing a proposal."""

    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    failures: list[str]
    output: str
    duration_ms: int


@dataclass(slots=True)
class ApplyResult:
    """Result of applying a proposal."""

    success: bool
    commit_hash: str | None
    rollback_data: str | None
    message: str


@dataclass(slots=True)
class PullRequest:
    """A GitHub pull request for human review."""

    url: str
    number: int
    title: str
    description: str
    branch: str


# === Blocked Files for Self-Modification ===

# Files that cannot be modified by the proposal system (meta-circular protection)
BLOCKED_PATHS: frozenset[str] = frozenset({
    "sunwell/self/",
    "sunwell/tools/types.py",
    "sunwell/mirror/safety.py",
})


def is_path_blocked(path: str | Path) -> bool:
    """Check if a path is blocked from self-modification."""
    path_str = str(path)
    return any(blocked in path_str for blocked in BLOCKED_PATHS)
