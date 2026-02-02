"""Domain abstraction for multi-purpose agents (RFC-DOMAINS).

Sunwell's core pipeline is domain-agnostic. This module provides:
- DomainType enum for classification
- Domain protocol for domain-specific behavior
- DomainRegistry for domain detection and lookup
- Domain implementations (code, research, writing, data, personal)

Each domain defines:
- Tools relevant to that domain
- Validators for "done" criteria
- Pattern extraction for learnings
- Detection confidence for goal classification
"""

from sunwell.domains.protocol import (
    Domain,
    DomainType,
    DomainValidator,
    ValidationResult,
)
from sunwell.domains.registry import DomainRegistry

__all__ = [
    "Domain",
    "DomainRegistry",
    "DomainType",
    "DomainValidator",
    "ValidationResult",
]
