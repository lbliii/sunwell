"""Domain protocol and types for multi-purpose agents (RFC-DOMAINS).

Defines the interface that all domain modules must implement.

Type definitions moved to sunwell.contracts.domain; re-exported here
for backward compatibility. BaseDomain stays here as it contains
business logic (keyword-based confidence scoring).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# Re-export all protocol types from contracts
from sunwell.contracts.domain import (
    Domain,
    DomainType,
    DomainValidator,
    ValidationResult,
)

if TYPE_CHECKING:
    from sunwell.agent.learning.learning import Learning


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

    def extract_learnings(self, artifact: Any, file_path: str | None = None) -> list["Learning"]:
        """Default: no learnings. Override in concrete domains."""
        return []
