"""Sunwell - RAG for Judgment.

Dynamic expertise retrieval for LLMs.

The Naaru architecture (RFC-019) provides coordinated intelligence for local models.
"""

from sunwell.foundation.errors import ErrorCode, SunwellError
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.heuristic import AntiHeuristic, Heuristic
from sunwell.foundation.core.lens import Lens, LensMetadata
from sunwell.core.persona import Persona
from sunwell.core.types import Confidence, Severity, Tier
from sunwell.core.validator import (
    DeterministicValidator,
    HeuristicValidator,
    ValidationResult,
)

# Naaru Architecture (RFC-019)
from sunwell.planning.naaru import (
    Convergence,
    Discernment,
    Naaru,
    Resonance,
    Shard,
    ShardPool,
)
from sunwell.planning.naaru import (
    NaaruConfig as NaaruRuntimeConfig,  # Avoid conflict with config.NaaruConfig
)

__version__ = "0.1.0"

__all__ = [
    # Core
    "Lens",
    "LensMetadata",
    "Heuristic",
    "AntiHeuristic",
    "Persona",
    "DeterministicValidator",
    "HeuristicValidator",
    "ValidationResult",
    "Framework",
    "FrameworkCategory",
    # Types
    "Severity",
    "Tier",
    "Confidence",
    # Errors
    "SunwellError",
    "ErrorCode",
    # Naaru Architecture
    "Naaru",
    "NaaruRuntimeConfig",
    "Convergence",
    "Shard",
    "ShardPool",
    "Resonance",
    "Discernment",
]
