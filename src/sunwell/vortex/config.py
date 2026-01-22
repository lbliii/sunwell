"""Vortex configuration."""


from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VortexConfig:
    """Vortex behavior configuration.

    Controls verbosity scaling, temperature funnel, and locality.
    Defaults are tuned for small models (1B-3B parameters).
    """

    # =========================================================================
    # Verbosity Scaling (Token Funnel)
    # =========================================================================

    discovery_tokens: int = 40
    """Max tokens for discovery phase. Cheap exploration."""

    selection_tokens: int = 80
    """Max tokens for selection phase. Brief reasoning."""

    synthesis_tokens: int = 300
    """Max tokens for synthesis phase. Full expansion."""

    # =========================================================================
    # Temperature Funnel
    # =========================================================================

    discovery_temp: float = 0.9
    """Temperature for discovery. High diversity."""

    selection_temp: float = 0.6
    """Temperature for selection. Moderate focus."""

    synthesis_temp: float = 0.3
    """Temperature for synthesis. Tight convergence."""

    # =========================================================================
    # Locality (Islands)
    # =========================================================================

    n_islands: int = 3
    """Number of isolated neighborhoods for cultural diversity."""

    agents_per_island: int = 3
    """Agents per island during discovery."""

    island_generations: int = 3
    """Evolution rounds per island."""

    migration_rate: float = 0.2
    """Probability of strong signals crossing island boundaries."""

    migration_threshold: float = 0.75
    """Minimum confidence for signal migration."""

    # =========================================================================
    # Discovery
    # =========================================================================

    discovery_signals: int = 6
    """Total signals to generate in discovery phase."""

    reaction_rounds: int = 2
    """Rounds of signal reactions (agreement measurement)."""

    # =========================================================================
    # Primitives
    # =========================================================================

    interference_perspectives: int = 3
    """Perspectives for interference primitive."""

    resonance_iterations: int = 2
    """Refinement iterations for resonance primitive."""

    dialectic_enabled: bool = True
    """Whether to use dialectic for low-agreement cases."""

    dialectic_threshold: float = 0.6
    """Agreement threshold below which to trigger dialectic."""


# Preset configurations
FAST_CONFIG = VortexConfig(
    discovery_tokens=30,
    selection_tokens=60,
    synthesis_tokens=200,
    n_islands=2,
    agents_per_island=2,
    island_generations=2,
    discovery_signals=4,
    reaction_rounds=1,
    interference_perspectives=2,
    resonance_iterations=1,
)
"""Fast configuration for quick iteration. Lower quality ceiling."""


QUALITY_CONFIG = VortexConfig(
    discovery_tokens=50,
    selection_tokens=100,
    synthesis_tokens=500,
    n_islands=4,
    agents_per_island=4,
    island_generations=4,
    discovery_signals=8,
    reaction_rounds=3,
    interference_perspectives=5,
    resonance_iterations=3,
)
"""Quality configuration for best results. Slower."""
