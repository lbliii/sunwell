"""Domain protocol and types for multi-purpose agents (RFC-DOMAINS).

Defines the interface that all domain modules must implement.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from sunwell.agent.learning.learning import Learning


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
    domain-specific quality criteria. For example:
    - Code domain: lint, type check, test
    - Research domain: source verification, coherence
    - Writing domain: style guide, grammar
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
        """Package path for tool auto-discovery.

        Example: 'sunwell.domains.code.tools' or 'sunwell.tools.implementations'
        """
        ...

    @property
    def validators(self) -> Sequence[DomainValidator]:
        """Validators for this domain's "done" criteria."""
        ...

    @property
    def default_validator_names(self) -> frozenset[str]:
        """Names of validators enabled by default."""
        ...

    def detect_confidence(self, goal: str) -> float:
        """Return 0-1 confidence that goal belongs to this domain.

        Used by DomainRegistry to auto-detect the best domain for a goal.

        Args:
            goal: The user's goal/task description

        Returns:
            Confidence score from 0.0 (no match) to 1.0 (perfect match)
        """
        ...

    def extract_learnings(self, artifact: Any, file_path: str | None = None) -> list[Learning]:
        """Extract domain-specific patterns from artifacts.

        Called after successful task completion to learn patterns
        that can inform future tasks.

        Args:
            artifact: The completed artifact (code, document, etc.)
            file_path: Optional path to the artifact

        Returns:
            List of extracted learnings
        """
        ...


@dataclass(slots=True)
class BaseDomain:
    """Base implementation with common domain functionality.

    Concrete domains can inherit from this for shared behavior,
    or implement Domain protocol directly.

    Keyword Tiers for Confidence Detection:
        - _high_conf_keywords: Strong indicators (0.4 each)
        - _medium_conf_keywords: Moderate indicators (0.25 each)
        - _keywords: Low-confidence indicators (0.15 each), minus high/medium
    """

    _domain_type: DomainType = field(default=DomainType.GENERAL)
    _tools_package: str = field(default="sunwell.tools.implementations")
    _validators: list[DomainValidator] = field(default_factory=list)
    _default_validator_names: frozenset[str] = field(default_factory=frozenset)
    _keywords: frozenset[str] = field(default_factory=frozenset)
    _high_conf_keywords: frozenset[str] = field(default_factory=frozenset)
    _medium_conf_keywords: frozenset[str] = field(default_factory=frozenset)

    @property
    def domain_type(self) -> DomainType:
        return self._domain_type

    @property
    def tools_package(self) -> str:
        return self._tools_package

    @property
    def validators(self) -> Sequence[DomainValidator]:
        return self._validators

    @property
    def default_validator_names(self) -> frozenset[str]:
        return self._default_validator_names

    def detect_confidence(self, goal: str) -> float:
        """Tiered keyword-based confidence scoring.

        High-confidence keywords contribute 0.4 each, medium 0.25, low 0.15.
        Returns 0.0 if no keywords are configured.
        """
        if not self._keywords and not self._high_conf_keywords and not self._medium_conf_keywords:
            return 0.0

        goal_lower = goal.lower()
        score = sum(0.4 for kw in self._high_conf_keywords if kw in goal_lower)
        score += sum(0.25 for kw in self._medium_conf_keywords if kw in goal_lower)

        low_conf = self._keywords - self._high_conf_keywords - self._medium_conf_keywords
        score += sum(0.15 for kw in low_conf if kw in goal_lower)

        return min(score, 1.0)

    def extract_learnings(self, artifact: Any, file_path: str | None = None) -> list[Learning]:
        """Default: no learnings. Override in concrete domains."""
        return []
