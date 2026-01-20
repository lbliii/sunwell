"""Fast Bootstrap — Day-1 Intelligence from Git History (RFC-050).

Provides immediate intelligence by mining existing project artifacts:
- Git history (commits, blame, authors)
- Code patterns (naming, types, docstrings)
- Documentation (README, architecture sections)
- Configuration (pyproject.toml, CI configs)

Usage:
    from sunwell.bootstrap import BootstrapOrchestrator, BootstrapResult

    orchestrator = BootstrapOrchestrator(project_root, context)
    result = await orchestrator.bootstrap()
"""

from sunwell.bootstrap.orchestrator import BootstrapOrchestrator
from sunwell.bootstrap.ownership import OwnershipDomain, OwnershipMap
from sunwell.bootstrap.types import (
    BootstrapDecision,
    BootstrapPatterns,
    BootstrapResult,
    BootstrapStatus,
    CodeEvidence,
    ConfigEvidence,
    DocEvidence,
    GitEvidence,
)

__all__ = [
    # Orchestrator
    "BootstrapOrchestrator",
    # Result types
    "BootstrapResult",
    "BootstrapStatus",
    # Evidence types
    "GitEvidence",
    "CodeEvidence",
    "DocEvidence",
    "ConfigEvidence",
    # Inference types
    "BootstrapDecision",
    "BootstrapPatterns",
    # Ownership
    "OwnershipMap",
    "OwnershipDomain",
]
