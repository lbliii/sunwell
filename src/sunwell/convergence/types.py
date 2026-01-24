"""Type definitions for Convergence Loops (RFC-123).

Immutable data structures for convergence loop state and configuration.
All types are frozen dataclasses with slots for performance.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sunwell.agent.gates import GateType


class ConvergenceStatus(Enum):
    """Status of convergence loop."""

    RUNNING = "running"
    """Loop is actively iterating."""

    STABLE = "stable"
    """All gates pass — code is stable."""

    ESCALATED = "escalated"
    """Max iterations reached or stuck — needs human intervention."""

    TIMEOUT = "timeout"
    """Time limit exceeded."""

    CANCELLED = "cancelled"
    """User cancelled the loop."""


@dataclass(frozen=True, slots=True)
class GateCheckResult:
    """Result of a single gate check.

    Example:
        >>> result = GateCheckResult(
        ...     gate=GateType.LINT,
        ...     passed=False,
        ...     errors=("E501 line too long",),
        ...     duration_ms=150,
        ... )
        >>> result.error_count
        1
    """

    gate: GateType
    """Which gate was checked."""

    passed: bool
    """Whether the gate passed."""

    errors: tuple[str, ...] = ()
    """Error messages if failed."""

    duration_ms: int = 0
    """Time taken in milliseconds."""

    @property
    def error_count(self) -> int:
        """Number of errors."""
        return len(self.errors)


@dataclass(frozen=True, slots=True)
class ConvergenceIteration:
    """One iteration of the convergence loop.

    Example:
        >>> iteration = ConvergenceIteration(
        ...     iteration=1,
        ...     gate_results=(lint_result, type_result),
        ...     files_changed=(Path("api.py"),),
        ...     duration_ms=500,
        ... )
        >>> iteration.all_passed
        False
    """

    iteration: int
    """Iteration number (1-based)."""

    gate_results: tuple[GateCheckResult, ...]
    """Results from each gate check."""

    files_changed: tuple[Path, ...]
    """Files that were modified in this iteration."""

    duration_ms: int
    """Total duration of this iteration."""

    @property
    def all_passed(self) -> bool:
        """True if all gates passed."""
        return all(r.passed for r in self.gate_results)

    @property
    def total_errors(self) -> int:
        """Total error count across all gates."""
        return sum(r.error_count for r in self.gate_results)


@dataclass
class ConvergenceResult:
    """Final result of convergence loop.

    Mutable because we build it incrementally during execution.

    Example:
        >>> result = ConvergenceResult(status=ConvergenceStatus.STABLE)
        >>> result.stable
        True
    """

    status: ConvergenceStatus
    """Final status."""

    iterations: list[ConvergenceIteration] = field(default_factory=list)
    """All iterations executed."""

    total_duration_ms: int = 0
    """Total time spent."""

    tokens_used: int = 0
    """Total tokens consumed by fix attempts."""

    @property
    def stable(self) -> bool:
        """True if convergence succeeded."""
        return self.status == ConvergenceStatus.STABLE

    @property
    def iteration_count(self) -> int:
        """Number of iterations executed."""
        return len(self.iterations)


@dataclass
class ConvergenceConfig:
    """Configuration for convergence behavior.

    Example:
        >>> config = ConvergenceConfig(
        ...     max_iterations=10,
        ...     enabled_gates=frozenset({GateType.LINT, GateType.TYPE}),
        ... )
    """

    # Limits
    max_iterations: int = 5
    """Maximum convergence iterations before escalating."""

    max_tokens: int = 50_000
    """Maximum token budget for fix attempts."""

    timeout_seconds: int = 300
    """Total time limit (5 minutes default)."""

    # Gate configuration
    enabled_gates: frozenset[GateType] = field(
        default_factory=lambda: frozenset({GateType.LINT, GateType.TYPE})
    )
    """Gates to run (default: lint + type)."""

    advisory_gates: frozenset[GateType] = field(default_factory=frozenset)
    """Optional gates — run but don't block on failure."""

    # Behavior
    debounce_ms: int = 200
    """Wait for writes to settle before checking."""

    escalate_after_same_error: int = 2
    """Escalate if same error repeats N times."""
