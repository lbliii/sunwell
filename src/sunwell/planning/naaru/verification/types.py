"""Contract verification types.

Dataclasses for representing Protocol method signatures and verification results.
"""

from dataclasses import dataclass, field
from enum import Enum


class VerificationTier(Enum):
    """Which verification tier produced the result."""

    AST = "ast"
    """AST-based structural check."""

    TYPE_CHECK = "type_check"
    """Static type checker (mypy)."""

    LLM = "llm"
    """LLM-based semantic verification."""


class VerificationStatus(Enum):
    """Overall verification status."""

    PASSED = "passed"
    """Implementation satisfies the contract."""

    FAILED = "failed"
    """Implementation does not satisfy the contract."""

    SKIPPED = "skipped"
    """Verification was skipped (no contract, missing file, etc.)."""

    ERROR = "error"
    """Verification encountered an error."""


@dataclass(frozen=True, slots=True)
class MethodSignature:
    """Represents a method signature extracted from a Protocol.

    Used to compare expected methods against implementation.
    """

    name: str
    """Method name."""

    parameters: tuple[str, ...]
    """Parameter names (excluding self)."""

    parameter_types: tuple[str, ...]
    """Parameter type annotations (as strings)."""

    return_type: str | None
    """Return type annotation (as string), or None if not annotated."""

    is_async: bool = False
    """Whether the method is async."""

    is_property: bool = False
    """Whether the method is a property."""

    @property
    def signature_str(self) -> str:
        """Human-readable signature string."""
        params = []
        for name, type_ann in zip(self.parameters, self.parameter_types, strict=False):
            if type_ann:
                params.append(f"{name}: {type_ann}")
            else:
                params.append(name)

        params_str = ", ".join(params)
        ret = f" -> {self.return_type}" if self.return_type else ""
        prefix = "async " if self.is_async else ""
        decorator = "@property\n    " if self.is_property else ""

        return f"{decorator}{prefix}def {self.name}({params_str}){ret}"


@dataclass(frozen=True, slots=True)
class MethodMismatch:
    """Describes a mismatch between expected and actual method."""

    method_name: str
    """Name of the method with the issue."""

    issue: str
    """Description of the mismatch."""

    expected: str | None = None
    """Expected signature or value."""

    actual: str | None = None
    """Actual signature or value found."""


@dataclass(frozen=True, slots=True)
class TierResult:
    """Result from a single verification tier."""

    tier: VerificationTier
    """Which tier produced this result."""

    passed: bool
    """Whether this tier's check passed."""

    message: str
    """Human-readable explanation."""

    mismatches: tuple[MethodMismatch, ...] = ()
    """Specific mismatches found (if any)."""

    duration_ms: int = 0
    """Time taken for this check in milliseconds."""


@dataclass(frozen=True, slots=True)
class ContractVerificationResult:
    """Complete result of contract verification.

    Contains results from all verification tiers that were run.
    """

    status: VerificationStatus
    """Overall verification status."""

    protocol_name: str
    """Name of the Protocol being verified against."""

    implementation_file: str
    """Path to the implementation file."""

    contract_file: str
    """Path to the contract/Protocol file."""

    tier_results: tuple[TierResult, ...] = ()
    """Results from each verification tier run."""

    final_tier: VerificationTier | None = None
    """The tier that produced the final verdict."""

    error_message: str | None = None
    """Error message if status is ERROR."""

    @property
    def passed(self) -> bool:
        """Convenience property for checking if verification passed."""
        return self.status == VerificationStatus.PASSED

    @property
    def all_mismatches(self) -> list[MethodMismatch]:
        """Collect all mismatches from all tiers."""
        mismatches = []
        for tier_result in self.tier_results:
            mismatches.extend(tier_result.mismatches)
        return mismatches

    @property
    def summary(self) -> str:
        """Human-readable summary of the verification."""
        if self.status == VerificationStatus.PASSED:
            return f"{self.protocol_name}: PASSED (via {self.final_tier.value if self.final_tier else 'unknown'})"
        elif self.status == VerificationStatus.FAILED:
            mismatch_count = len(self.all_mismatches)
            return f"{self.protocol_name}: FAILED ({mismatch_count} issue(s))"
        elif self.status == VerificationStatus.ERROR:
            return f"{self.protocol_name}: ERROR - {self.error_message}"
        else:
            return f"{self.protocol_name}: SKIPPED"


@dataclass(frozen=True, slots=True)
class TypeCheckResult:
    """Result from running mypy type checker."""

    passed: bool
    """Whether type checking passed."""

    errors: tuple[str, ...] = ()
    """List of error messages from mypy."""

    warnings: tuple[str, ...] = ()
    """List of warning messages from mypy."""

    exit_code: int = 0
    """Exit code from mypy process."""

    duration_ms: int = 0
    """Time taken for type checking in milliseconds."""


@dataclass(slots=True)
class ProtocolInfo:
    """Information about a Protocol extracted from source."""

    name: str
    """Protocol class name."""

    methods: list[MethodSignature] = field(default_factory=list)
    """Methods defined in the Protocol."""

    bases: list[str] = field(default_factory=list)
    """Base classes (other Protocols this extends)."""

    source_file: str | None = None
    """Source file path where Protocol is defined."""

    docstring: str | None = None
    """Protocol docstring if present."""
