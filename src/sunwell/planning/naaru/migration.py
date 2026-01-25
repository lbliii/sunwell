"""Migration helpers from RFC-019 to RFC-033 unified architecture."""


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.foundation.types.config import NaaruConfig


def migrate_rfc019_to_rfc033(old_config: NaaruConfig) -> NaaruConfig:
    """Migrate RFC-019 NaaruConfig to RFC-033 unified architecture.

    Converts old flags (harmonic_synthesis, resonance, discernment) to
    new unified layer configuration (diversity, selection, refinement).

    Args:
        old_config: NaaruConfig with RFC-019 fields

    Returns:
        New NaaruConfig with RFC-033 fields set appropriately

    Example:
        >>> # Old (RFC-019)
        >>> config = NaaruConfig(
        ...     harmonic_synthesis=True,
        ...     resonance=2,
        ...     discernment=True,
        ... )
        >>>
        >>> # New (RFC-033)
        >>> new_config = migrate_rfc019_to_rfc033(config)
        >>> # Equivalent to:
        >>> # NaaruConfig(
        >>> #     diversity="harmonic",
        >>> #     selection="voting",
        >>> #     refinement="tiered",
        >>> #     refinement_max_attempts=2,
        >>> # )
    """
    from sunwell.foundation.types.config import NaaruConfig

    # Map old flags to new strategies
    if old_config.harmonic_synthesis:
        diversity = "harmonic"
        selection = "voting"
    else:
        diversity = "none"
        selection = "passthrough"

    # Map resonance to refinement
    if old_config.resonance > 0:
        refinement = "tiered" if old_config.discernment else "full"
    else:
        refinement = "none"

    # Create new config with migrated values
    return NaaruConfig(
        # Preserve all existing fields
        name=old_config.name,
        title=old_config.title,
        titles=old_config.titles,
        alternate_titles=old_config.alternate_titles,
        use_native_ollama_api=old_config.use_native_ollama_api,
        voice=old_config.voice,
        voice_models=old_config.voice_models,
        voice_temperature=old_config.voice_temperature,
        wisdom=old_config.wisdom,
        wisdom_models=old_config.wisdom_models,
        purity_threshold=old_config.purity_threshold,
        convergence=old_config.convergence,
        router=old_config.router,
        router_temperature=old_config.router_temperature,
        router_cache_size=old_config.router_cache_size,
        num_analysis_shards=old_config.num_analysis_shards,
        num_synthesis_shards=old_config.num_synthesis_shards,
        # New RFC-033 fields
        diversity=diversity,
        selection=selection,
        refinement=refinement,
        refinement_max_attempts=old_config.resonance if old_config.resonance > 0 else 2,
        cost_budget="normal",
        task_type="auto",
    )


def create_rfc019_equivalent_config() -> NaaruConfig:
    """Create a config equivalent to RFC-019 default behavior.

    Returns:
        NaaruConfig that matches RFC-019 defaults:
        - harmonic_synthesis=True
        - resonance=2
        - discernment=True
    """
    from sunwell.foundation.types.config import NaaruConfig

    return NaaruConfig(
        diversity="harmonic",
        selection="voting",
        refinement="tiered",
        refinement_max_attempts=2,
        cost_budget="normal",
    )


def create_rfc028_equivalent_config() -> NaaruConfig:
    """Create a minimal config (RFC-028 rotation was removed).

    Note: Cognitive frame rotation was removed after benchmarking showed
    no quality improvement for 20B+ models. This now creates a minimal config.

    Returns:
        NaaruConfig with minimal settings (no diversity, no refinement)
    """
    from sunwell.foundation.types.config import NaaruConfig

    return NaaruConfig(
        diversity="none",
        selection="passthrough",
        refinement="none",
        cost_budget="minimal",
    )
