"""Validator data models.

RFC-035 adds SchemaValidator for lens-provided schema artifact validation.
"""


from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sunwell.core.types import Severity, ValidationMethod


class SchemaValidationMethod(Enum):
    """Method for schema validator execution (RFC-035)."""

    CONSTRAINT = "constraint"  # DSL-based deterministic check
    LLM = "llm"  # LLM-based judgment


@dataclass(frozen=True, slots=True)
class DeterministicValidator:
    """Script-based, reproducible validator.

    Deterministic validators run scripts or commands that produce
    consistent, reproducible results. They're ideal for syntax checks,
    linting, link verification, etc.
    """

    name: str
    script: str  # Path or inline script
    severity: Severity = Severity.ERROR
    description: str | None = None
    timeout_seconds: float = 30.0

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts for embedding text (Embeddable protocol)."""
        return (self.name, self.description)

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        from sunwell.core.types.embeddable import to_embedding_text

        return to_embedding_text(self)


@dataclass(frozen=True, slots=True)
class HeuristicValidator:
    """AI-based validator (judgment calls).

    Heuristic validators use LLM judgment to assess quality aspects
    that can't be mechanically checked—tone, clarity, completeness, etc.
    """

    name: str
    check: str  # What to verify
    method: ValidationMethod = ValidationMethod.PATTERN_MATCH
    confidence_threshold: float = 0.8
    severity: Severity = Severity.WARNING
    description: str | None = None

    def to_prompt(self, content: str) -> str:
        """Generate validation prompt."""
        return f"""Evaluate this content against the following criterion:

**Check**: {self.check}

---
{content}
---

Respond with:
1. PASS or FAIL
2. Confidence (0.0-1.0)
3. Brief explanation (1-2 sentences)

Format: PASS|0.95|Content meets the criterion because...
"""

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts for embedding text (Embeddable protocol)."""
        return (self.name, self.check, self.description)

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        from sunwell.core.types.embeddable import to_embedding_text

        return to_embedding_text(self)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result from running a validator."""

    validator_name: str
    passed: bool
    severity: Severity
    message: str | None = None
    confidence: float | None = None  # For heuristic validators
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def status_emoji(self) -> str:
        """Get status indicator emoji."""
        if self.passed:
            return "✅"
        elif self.severity == Severity.ERROR:
            return "❌"
        elif self.severity == Severity.WARNING:
            return "⚠️"
        else:
            return "ℹ️"

    def to_display(self) -> str:
        """Format for display."""
        parts = [f"{self.status_emoji} {self.validator_name}"]
        if self.message:
            parts.append(f": {self.message}")
        if self.confidence is not None:
            parts.append(f" ({self.confidence:.0%} confidence)")
        return "".join(parts)


@dataclass(frozen=True, slots=True)
class SchemaValidator:
    """Lens-provided validator for schema artifacts (RFC-035).

    Unlike HeuristicValidator (general content checks), SchemaValidator
    targets specific artifact types defined in a project schema. These
    validators extend a project's built-in validators with lens-specific
    domain expertise.

    Example:
        A developmental editor lens might add:

        SchemaValidator(
            name="character_arc_complete",
            check="Every major character must change by the end",
            applies_to="character",
            condition="character.role == 'major'",
        )

    When combined with a fiction schema, this ensures character arcs
    are complete for major characters.
    """

    name: str
    check: str  # What to verify
    applies_to: str  # Artifact type (e.g., "character", "scene")
    condition: str | None = None  # When to apply (e.g., "character.role == 'major'")
    severity: Severity = Severity.WARNING
    method: SchemaValidationMethod = SchemaValidationMethod.LLM

    def to_prompt(self, artifact: dict[str, Any]) -> str:
        """Generate validation prompt for an artifact.

        Args:
            artifact: The artifact data to validate

        Returns:
            Prompt for LLM validation
        """
        import json

        artifact_str = json.dumps(artifact, indent=2, default=str)

        return f"""Evaluate this {self.applies_to} artifact against the following criterion:

**Check**: {self.check}

**Artifact**:
```json
{artifact_str}
```

Respond with:
1. PASS or FAIL
2. Confidence (0.0-1.0)
3. Brief explanation (1-2 sentences)

Format: PASS|0.95|The artifact meets the criterion because...
"""

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts for embedding text (Embeddable protocol)."""
        condition_part = f"when: {self.condition}" if self.condition else None
        return (self.name, self.check, f"applies to: {self.applies_to}", condition_part)

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        from sunwell.core.types.embeddable import to_embedding_text

        return to_embedding_text(self)
