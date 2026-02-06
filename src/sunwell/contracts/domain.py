"""Domain protocol and types for multi-purpose agents.

Extracted from sunwell.domains.protocol per the Contracts Layer plan.
This module imports ONLY from stdlib.

Note: ``Domain.extract_learnings`` returns ``list[Any]`` instead of
``list[Learning]`` to avoid importing agent types. Concrete domain
implementations use the proper Learning type.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class DomainType(Enum):
    """Extended domain types beyond code.

    Each domain type has distinct:
    - Tools (what actions are available)
    - Validators (what "done" means)
    - Patterns (what to learn from artifacts)
    """

    CODE = "code"
    """Software development: file ops, git, lint, type, test."""

    RESEARCH = "research"
    """Knowledge work: web search, summarize, cite, fact-check."""

    WRITING = "writing"
    """Content creation: outline, draft, revise, style check."""

    DATA = "data"
    """Data analysis: query, transform, visualize, validate schema."""

    PERSONAL = "personal"
    """Personal assistant: calendar, contacts, email, reminders."""

    GENERAL = "general"
    """Fallback for unclassified goals."""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of domain-specific validation.

    Attributes:
        passed: Whether validation passed
        validator_name: Name of the validator that ran
        message: Human-readable result message
        errors: Detailed error information if failed
        duration_ms: How long validation took
        auto_fixed: Whether issues were auto-corrected
    """

    passed: bool
    """Whether validation passed."""

    validator_name: str
    """Name of the validator that ran."""

    message: str = ""
    """Human-readable result message."""

    errors: tuple[dict[str, Any], ...] = ()
    """Detailed error information if failed."""

    duration_ms: int = 0
    """How long validation took in milliseconds."""

    auto_fixed: bool = False
    """Whether issues were auto-corrected."""


class DomainValidator(Protocol):
    """Protocol for domain-specific validation.

    Each domain defines validators that check if artifacts meet
    domain-specific quality criteria.
    """

    @property
    def name(self) -> str:
        """Unique validator name (e.g., 'lint', 'sources', 'grammar')."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what this validator checks."""
        ...

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Validate artifact meets domain criteria.

        Args:
            artifact: The artifact to validate (file content, document, etc.)
            context: Additional context (toolchain, workspace, etc.)

        Returns:
            ValidationResult with pass/fail and details
        """
        ...


class Domain(Protocol):
    """Protocol for domain-specific behavior.

    Each domain module (code, research, writing, etc.) implements this
    protocol to define domain-specific tools, validators, and patterns.
    """

    @property
    def domain_type(self) -> DomainType:
        """The type of this domain."""
        ...

    @property
    def tools_package(self) -> str:
        """Package path for tool auto-discovery."""
        ...

    @property
    def validators(self) -> Sequence[DomainValidator]:
        """Validators for this domain's 'done' criteria."""
        ...

    @property
    def default_validator_names(self) -> frozenset[str]:
        """Names of validators enabled by default."""
        ...

    def detect_confidence(self, goal: str) -> float:
        """Return 0-1 confidence that goal belongs to this domain."""
        ...

    def extract_learnings(self, artifact: Any, file_path: str | None = None) -> list[Any]:
        """Extract domain-specific patterns from artifacts.

        Returns list of Learning objects (typed as Any to avoid
        importing agent types into contracts).
        """
        ...
