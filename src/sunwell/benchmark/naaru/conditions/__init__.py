"""Naaru Condition Implementations (RFC-027).

This package provides modular condition implementations:
- baseline: Baseline conditions (A, B)
- harmonic: Harmonic conditions (C, D, J)
- resonance: Resonance condition (E)
- naaru_full: Full Naaru conditions (F, G)
- rotation_conditions: Rotation conditions (H, I, K)
- personas: Persona definitions and temperature strategies
- rotation: Rotation frame definitions
- utils: Utility functions
- runner: ConditionRunner class
"""

# Re-export all condition functions
from sunwell.benchmark.naaru.conditions.baseline import run_baseline, run_baseline_lens
from sunwell.benchmark.naaru.conditions.harmonic import (
    run_harmonic,
    run_harmonic_divergent,
    run_harmonic_lens,
)
from sunwell.benchmark.naaru.conditions.naaru_full import run_naaru_full, run_naaru_full_lens
from sunwell.benchmark.naaru.conditions.resonance import run_resonance
from sunwell.benchmark.naaru.conditions.rotation_conditions import run_rotation, run_rotation_lens
from sunwell.benchmark.naaru.conditions.runner import ConditionRunner

# Re-export utilities
from sunwell.benchmark.naaru.conditions.personas import (
    DIVERGENT_PERSONAS,
    HARDCODED_PERSONAS,
    TemperatureStrategy,
)
from sunwell.benchmark.naaru.conditions.rotation import (
    DIVERGENT_ROTATION_FRAMES,
    ROTATION_FRAMES,
    build_rotation_prompt,
    parse_frame_usage,
)
from sunwell.benchmark.naaru.conditions.utils import lightweight_validate

__all__ = [
    # Condition functions
    "run_baseline",
    "run_baseline_lens",
    "run_harmonic",
    "run_harmonic_lens",
    "run_harmonic_divergent",
    "run_resonance",
    "run_naaru_full",
    "run_naaru_full_lens",
    "run_rotation",
    "run_rotation_lens",
    # Runner
    "ConditionRunner",
    # Personas
    "HARDCODED_PERSONAS",
    "DIVERGENT_PERSONAS",
    "TemperatureStrategy",
    # Rotation
    "ROTATION_FRAMES",
    "DIVERGENT_ROTATION_FRAMES",
    "build_rotation_prompt",
    "parse_frame_usage",
    # Utils
    "lightweight_validate",
]
