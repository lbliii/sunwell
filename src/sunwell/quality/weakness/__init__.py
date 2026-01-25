"""RFC-063: Weakness Cascade - DAG-powered technical debt liquidation.
RFC-069: Cascade Agent Integration - wiring weakness fix to artifact execution.

This module provides:
- Automated weakness detection (coverage, complexity, lint, types, staleness)
- Cascade preview showing full impact before changes
- Contract extraction for compatibility verification
- Wave-by-wave execution with confidence scoring
- CascadeExecutor for agent-driven code regeneration (RFC-069)
"""

from sunwell.weakness.analyzer import SmartWeaknessAnalyzer, WeaknessAnalyzer
from sunwell.weakness.cascade import CascadeEngine, CascadeExecution, CascadePreview
from sunwell.weakness.executor import (
    CascadeArtifactBuilder,
    CascadeExecutor,
    WaveResult,
    create_cascade_executor,
)
from sunwell.weakness.types import (
    CascadeRisk,
    DeltaPreview,
    ExtractedContract,
    WaveConfidence,
    WeaknessScore,
    WeaknessSignal,
    WeaknessType,
)
from sunwell.weakness.verification import run_mypy, run_pytest, run_ruff

__all__ = [
    # Types
    "WeaknessType",
    "WeaknessSignal",
    "WeaknessScore",
    "ExtractedContract",
    "WaveConfidence",
    "DeltaPreview",
    "CascadeRisk",
    "WaveResult",
    # Classes
    "WeaknessAnalyzer",
    "SmartWeaknessAnalyzer",  # RFC-077: LLM prioritization
    "CascadeEngine",
    "CascadeExecution",
    "CascadePreview",
    # RFC-069: Executor classes
    "CascadeArtifactBuilder",
    "CascadeExecutor",
    # Factory functions
    "create_cascade_executor",
    # Verification utilities
    "run_pytest",
    "run_mypy",
    "run_ruff",
]
