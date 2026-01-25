"""Vortex — Multi-model coordination through primitive composition.

The vortex architecture combines:
- **Locality**: Islands prevent premature convergence, enabling cultural diversity
- **Verbosity scaling**: Token funnel (cheap discovery → expensive synthesis)
- **Temporal primitives**: Interference, dialectic, resonance for refinement

Example:
    >>> from sunwell.vortex import Vortex
    >>> from sunwell.models import OllamaModel
    >>>
    >>> model = OllamaModel("gemma3:1b")
    >>> vortex = Vortex(model)
    >>>
    >>> result = await vortex.solve("Design a rate limiter for an API")
    >>> print(result.synthesis)

Or use the convenience function:
    >>> from sunwell.vortex import solve
    >>> result = await solve("Design a rate limiter", model)

Configuration:
    >>> from sunwell.vortex import Vortex, VortexConfig, FAST_CONFIG
    >>>
    >>> # Custom config
    >>> config = VortexConfig(n_islands=4, synthesis_tokens=500)
    >>> vortex = Vortex(model, config)
    >>>
    >>> # Or use presets
    >>> fast_vortex = Vortex(model, FAST_CONFIG)
"""

from sunwell.features.vortex.config import (
    FAST_CONFIG,
    QUALITY_CONFIG,
    VortexConfig,
)
from sunwell.features.vortex.core import (
    Vortex,
    VortexResult,
    format_result,
    solve,
)
from sunwell.features.vortex.locality import (
    Island,
    LocalityResult,
    evolve_islands,
)
from sunwell.features.vortex.primitives import (
    DialecticResult,
    GradientResult,
    InterferenceResult,
    ResonanceResult,
    Subtask,
    dialectic,
    gradient,
    interference,
    resonance,
)
from sunwell.features.vortex.signals import (
    Signal,
    format_signal,
)

__all__ = [
    # Core
    "Vortex",
    "VortexResult",
    "solve",
    "format_result",
    # Config
    "VortexConfig",
    "FAST_CONFIG",
    "QUALITY_CONFIG",
    # Signals
    "Signal",
    "format_signal",
    # Locality
    "Island",
    "LocalityResult",
    "evolve_islands",
    # Primitives
    "InterferenceResult",
    "DialecticResult",
    "ResonanceResult",
    "GradientResult",
    "Subtask",
    "interference",
    "dialectic",
    "resonance",
    "gradient",
]
