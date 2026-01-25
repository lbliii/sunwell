"""Type definitions for Deep Verification (RFC-047).

Core types for semantic verification of generated code.
Distinct from:
- sunwell.planning.naaru.artifacts.VerificationResult (artifact contract verification)
- sunwell.routing.tiered_attunement.VerificationResult (routing self-verification)

This module focuses on behavioral/semantic correctness verification.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

# =============================================================================
# Specification Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class InputSpec:
    """Specification for an input parameter."""

    name: str
    type_hint: str
    constraints: tuple[str, ...] = ()
    """Constraints like "positive", "non-empty", "valid email"."""

    examples: tuple[str, ...] = ()
    """Example values for this input."""


@dataclass(frozen=True, slots=True)
class OutputSpec:
    """Specification for an output value."""

    type_hint: str
    constraints: tuple[str, ...] = ()
    """Constraints like "sorted", "unique", "non-empty"."""

    examples: tuple[str, ...] = ()
    """Example values for this output."""


@dataclass(frozen=True, slots=True)
class Specification:
    """Extracted specification for verification.

    Combines specs from multiple sources with confidence weighting.
    """

    description: str
    """Natural language description of expected behavior."""

    inputs: tuple[InputSpec, ...]
    """Expected input types and constraints."""

    outputs: tuple[OutputSpec, ...]
    """Expected output types and constraints."""

    preconditions: tuple[str, ...]
    """Conditions that must be true before execution."""

    postconditions: tuple[str, ...]
    """Conditions that must be true after execution."""

    invariants: tuple[str, ...]
    """Properties that must always hold."""

    edge_cases: tuple[str, ...]
    """Known edge cases to test."""

    source: Literal["contract", "docstring", "signature", "existing_tests", "inferred"]
    """Where this spec primarily came from."""

    confidence: float
    """0-1, how confident we are in this spec."""


# =============================================================================
# Test Generation Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class GeneratedTest:
    """A generated test case."""

    id: str
    name: str
    description: str

    category: Literal[
        "happy_path",  # Normal expected usage
        "edge_case",  # Boundary conditions
        "error_case",  # Expected failures
        "property",  # Invariant checking
        "integration",  # Works with dependencies
        "regression",  # Doesn't break existing behavior
    ]

    code: str
    """Executable test code."""

    expected_outcome: Literal["pass", "fail", "error"]
    """What should happen when this test runs."""

    spec_coverage: tuple[str, ...]
    """Which spec elements this test covers."""

    priority: float
    """0-1, higher = more important to run."""


# =============================================================================
# Execution Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class TestExecutionResult:
    """Result of executing a single test."""

    test_id: str
    passed: bool

    actual_output: str | None = None
    expected_output: str | None = None

    error_message: str | None = None
    error_traceback: str | None = None

    duration_ms: int = 0

    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class BehavioralExecutionResult:
    """Result of executing all behavioral tests."""

    total_tests: int
    passed: int
    failed: int
    errors: int

    test_results: tuple[TestExecutionResult, ...]

    duration_ms: int

    @property
    def pass_rate(self) -> float:
        """Percentage of tests that passed."""
        if self.total_tests == 0:
            return 1.0
        return self.passed / self.total_tests


# =============================================================================
# Analysis Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class PerspectiveResult:
    """Result from a single verification perspective."""

    perspective: str
    """Name of the perspective (correctness_reviewer, edge_case_hunter, etc.)."""

    verdict: Literal["correct", "suspicious", "incorrect"]
    confidence: float
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticIssue:
    """A semantic issue found during verification."""

    severity: Literal["critical", "high", "medium", "low"]

    category: Literal[
        "wrong_output",  # Produces incorrect results
        "missing_edge_case",  # Doesn't handle edge case
        "logic_error",  # Algorithm bug
        "contract_violation",  # Doesn't satisfy spec
        "integration_issue",  # Doesn't work with dependencies
        "regression",  # Breaks existing behavior
    ]

    description: str

    evidence: str
    """Code snippet or test result showing the issue."""

    suggested_fix: str | None = None


# =============================================================================
# Final Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class DeepVerificationResult:
    """Final deep verification result with confidence.

    Note: Named DeepVerificationResult to distinguish from:
    - sunwell.planning.naaru.artifacts.VerificationResult (artifact contract verification)
    - sunwell.routing.tiered_attunement.VerificationResult (self-verification)

    This class focuses on semantic correctness of generated code.
    """

    passed: bool
    """Did verification pass overall?"""

    confidence: float
    """0-1, how confident we are in correctness."""

    issues: tuple[SemanticIssue, ...]
    """Issues found during verification."""

    generated_tests: tuple[GeneratedTest, ...]
    """Tests that were generated (can be kept)."""

    test_results: BehavioralExecutionResult | None
    """Results from test execution."""

    perspective_results: tuple[PerspectiveResult, ...]
    """Results from each verification perspective."""

    recommendations: tuple[str, ...]
    """Actionable recommendations."""

    duration_ms: int
    """Total verification time."""

    @property
    def confidence_level(self) -> Literal["high", "moderate", "low", "uncertain"]:
        """Map confidence score to level."""
        if self.confidence >= 0.9:
            return "high"
        elif self.confidence >= 0.7:
            return "moderate"
        elif self.confidence >= 0.5:
            return "low"
        else:
            return "uncertain"


# =============================================================================
# Event Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class VerificationEvent:
    """Event emitted during verification for progress tracking."""

    stage: Literal[
        "start",
        "spec_extraction",
        "spec_extracted",
        "test_generation",
        "tests_generated",
        "test_execution",
        "tests_executed",
        "analysis",
        "analyzed",
        "triangulation",
        "complete",
    ]

    message: str = ""
    data: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


# =============================================================================
# Configuration Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class DeepVerificationConfig:
    """Configuration for deep verification."""

    max_tests: int = 10
    """Maximum tests to generate."""

    test_timeout_s: int = 10
    """Timeout per test in seconds."""

    total_timeout_s: int = 120
    """Total verification timeout."""

    min_confidence: float = 0.7
    """Minimum confidence to pass."""

    min_test_pass_rate: float = 0.8
    """Minimum test pass rate to pass."""

    perspectives: tuple[str, ...] = (
        "correctness_reviewer",
        "edge_case_hunter",
        "integration_analyst",
    )
    """Which perspectives to run."""

    level: Literal["quick", "standard", "thorough"] = "standard"
    """Verification level."""


# Preset configurations for different levels
QUICK_CONFIG = DeepVerificationConfig(
    max_tests=0,  # No test generation
    perspectives=("correctness_reviewer",),
    level="quick",
)

STANDARD_CONFIG = DeepVerificationConfig(
    max_tests=5,
    perspectives=("correctness_reviewer", "edge_case_hunter"),
    level="standard",
)

THOROUGH_CONFIG = DeepVerificationConfig(
    max_tests=10,
    perspectives=(
        "correctness_reviewer",
        "edge_case_hunter",
        "integration_analyst",
        "regression_detective",
    ),
    level="thorough",
)
