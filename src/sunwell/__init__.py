"""Sunwell - RAG for Judgment.

Dynamic expertise retrieval for LLMs.

The Naaru architecture (RFC-019) provides coordinated intelligence for local models.
"""

from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.heuristic import Heuristic, AntiHeuristic
from sunwell.core.persona import Persona
from sunwell.core.validator import (
    DeterministicValidator,
    HeuristicValidator,
    ValidationResult,
)
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.types import Severity, Tier, Confidence
from sunwell.core.errors import SunwellError, ErrorCode

# Naaru Architecture (RFC-019)
from sunwell.naaru import (
    Naaru,
    NaaruConfig as NaaruRuntimeConfig,  # Avoid conflict with config.NaaruConfig
    Convergence,
    Shard,
    ShardPool,
    Resonance,
    Discernment,
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
