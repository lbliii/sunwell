"""RFC-063: Weakness type definitions.

Core types for weakness detection and cascade regeneration.
These are frozen dataclasses for thread-safety in Python 3.14t.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class WeaknessType(str, Enum):
    """Categories of code weakness."""

    LOW_COVERAGE = "low_coverage"  # < 50% test coverage
    HIGH_COMPLEXITY = "high_complexity"  # Cyclomatic complexity > 10
    LINT_ERRORS = "lint_errors"  # Unresolved linter issues
    STALE_CODE = "stale_code"  # No commits in 6mo + high fan_out + low coverage
    FAILURE_PRONE = "failure_prone"  # Failed in recent executions
    MISSING_TYPES = "missing_types"  # Any in mypy output
    BROKEN_CONTRACT = "broken_contract"  # Interface doesn't match impl


# Type alias for risk levels
CascadeRisk = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True, slots=True)
class WeaknessSignal:
    """A detected weakness in the codebase."""

    artifact_id: str
    file_path: Path
    weakness_type: WeaknessType
    severity: float  # 0.0 - 1.0
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        """Severity > 0.8 is critical."""
        return self.severity > 0.8


@dataclass(frozen=True, slots=True)
class WeaknessScore:
    """Aggregated weakness score for an artifact."""

    artifact_id: str
    file_path: Path
    signals: tuple[WeaknessSignal, ...]
    fan_out: int  # How many depend on this
    depth: int  # Position in dependency chain

    @property
    def total_severity(self) -> float:
        """Weighted severity including impact multiplier."""
        if not self.signals:
            return 0.0
        base = sum(s.severity for s in self.signals) / len(self.signals)
        # Higher fan_out = more impact if weak
        impact_multiplier = 1 + (self.fan_out * 0.05)
        return min(1.0, base * impact_multiplier)

    @property
    def cascade_risk(self) -> CascadeRisk:
        """Risk level based on weakness + fan_out."""
        score = self.total_severity * (1 + self.fan_out / 10)
        if score > 2.0:
            return "critical"
        if score > 1.0:
            return "high"
        if score > 0.5:
            return "medium"
        return "low"


@dataclass(frozen=True, slots=True)
class ExtractedContract:
    """Interface contract extracted from code before regeneration.

    Captures the public API so regeneration can verify compatibility.
    """

    artifact_id: str
    file_path: Path

    # Public interface elements
    functions: tuple[str, ...]  # Function signatures
    classes: tuple[str, ...]  # Class definitions with public methods
    exports: tuple[str, ...]  # __all__ or equivalent
    type_signatures: tuple[str, ...]  # Key type annotations

    # Checksum for quick equality check
    interface_hash: str

    def is_compatible_with(self, other: "ExtractedContract") -> bool:
        """Check if another contract is backward-compatible.

        All functions in self must exist in other (additions OK).
        Signatures can be more permissive but not more restrictive.
        """
        return set(self.functions) <= set(other.functions)


@dataclass(frozen=True, slots=True)
class WaveConfidence:
    """Confidence score for a completed wave."""

    wave_num: int
    artifacts_completed: tuple[str, ...]

    # Scoring components
    tests_passed: bool
    types_clean: bool
    lint_clean: bool
    contracts_preserved: bool

    # Aggregate score 0.0-1.0
    confidence: float

    # Reasons for any deductions
    deductions: tuple[str, ...] = ()

    @classmethod
    def compute(
        cls,
        wave_num: int,
        artifacts: tuple[str, ...],
        test_result: bool,
        type_result: bool,
        lint_result: bool,
        contract_result: bool,
    ) -> "WaveConfidence":
        """Compute confidence from verification results."""
        deductions: list[str] = []
        score = 1.0

        if not test_result:
            score -= 0.4
            deductions.append("Tests failed")
        if not type_result:
            score -= 0.2
            deductions.append("Type errors introduced")
        if not lint_result:
            score -= 0.1
            deductions.append("Lint errors introduced")
        if not contract_result:
            score -= 0.3
            deductions.append("Contract compatibility broken")

        return cls(
            wave_num=wave_num,
            artifacts_completed=artifacts,
            tests_passed=test_result,
            types_clean=type_result,
            lint_clean=lint_result,
            contracts_preserved=contract_result,
            confidence=max(0.0, score),
            deductions=tuple(deductions),
        )

    @property
    def should_continue(self) -> bool:
        """Whether cascade should proceed to next wave."""
        return self.confidence >= 0.7  # Configurable threshold


@dataclass(frozen=True, slots=True)
class DeltaPreview:
    """Preview of changes the agent would make to a file."""

    artifact_id: str
    file_path: Path

    # Diff information
    additions: int
    deletions: int
    hunks: tuple[str, ...]  # Summary of each change hunk

    # Full unified diff (can be large)
    unified_diff: str | None = None
