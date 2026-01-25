"""Naaru Condition Implementations (RFC-027).

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.benchmark.naaru.conditions` (the package) instead.

This module re-exports everything from the modular conditions package.
The actual implementations are in:
- `sunwell.benchmark.naaru.conditions.baseline` - Baseline conditions (A, B)
- `sunwell.benchmark.naaru.conditions.harmonic` - Harmonic conditions (C, D, J)
- `sunwell.benchmark.naaru.conditions.resonance` - Resonance condition (E)
- `sunwell.benchmark.naaru.conditions.naaru_full` - Full Naaru conditions (F, G)
- `sunwell.benchmark.naaru.conditions.rotation_conditions` - Rotation conditions (H, I, K)
- `sunwell.benchmark.naaru.conditions.personas` - Persona definitions
- `sunwell.benchmark.naaru.conditions.rotation` - Rotation frame definitions
- `sunwell.benchmark.naaru.conditions.utils` - Utility functions
- `sunwell.benchmark.naaru.conditions.runner` - ConditionRunner class

Migration guide:
    # Old (still works)
    from sunwell.benchmark.naaru.conditions import ConditionRunner

    # New (same import, but now from package)
    from sunwell.benchmark.naaru.conditions import ConditionRunner
"""

# Re-export everything from the modular conditions package for backward compatibility
from sunwell.benchmark.naaru.conditions import (
    ConditionRunner,
    DIVERGENT_PERSONAS,
    DIVERGENT_ROTATION_FRAMES,
    HARDCODED_PERSONAS,
    ROTATION_FRAMES,
    TemperatureStrategy,
    build_rotation_prompt,
    lightweight_validate,
    parse_frame_usage,
    run_baseline,
    run_baseline_lens,
    run_harmonic,
    run_harmonic_divergent,
    run_harmonic_lens,
    run_naaru_full,
    run_naaru_full_lens,
    run_resonance,
    run_rotation,
    run_rotation_lens,
)

__all__ = [
    "ConditionRunner",
    "DIVERGENT_PERSONAS",
    "DIVERGENT_ROTATION_FRAMES",
    "HARDCODED_PERSONAS",
    "ROTATION_FRAMES",
    "TemperatureStrategy",
    "build_rotation_prompt",
    "lightweight_validate",
    "parse_frame_usage",
    "run_baseline",
    "run_baseline_lens",
    "run_harmonic",
    "run_harmonic_divergent",
    "run_harmonic_lens",
    "run_naaru_full",
    "run_naaru_full_lens",
    "run_resonance",
    "run_rotation",
    "run_rotation_lens",
]
