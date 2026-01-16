"""Validator data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sunwell.core.types import Severity, ValidationMethod


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

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        parts = [self.name]
        if self.description:
            parts.append(self.description)
        return " ".join(parts)


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

    def to_embedding_text(self) -> str:
        """Convert to text for embedding/retrieval."""
        parts = [self.name, self.check]
        if self.description:
            parts.append(self.description)
        return " ".join(parts)


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
