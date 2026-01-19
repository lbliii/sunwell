"""Locality-constrained signal evolution.

Islands prevent premature convergence by isolating signal populations.
Strong signals can migrate across boundaries, enabling cross-pollination
without homogenization.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import GenerateOptions, ModelProtocol

from sunwell.vortex.signals import Signal, generate_reaction, generate_signal


@dataclass(frozen=True, slots=True)
class Island:
    """An isolated signal population."""

    island_id: int
    """Island identifier."""

    signals: tuple[Signal, ...]
    """Signals in this island."""

    culture: tuple[str, ...]
    """Dominant tags (the island's "culture")."""


@dataclass(frozen=True, slots=True)
class LocalityResult:
    """Result from locality-constrained evolution."""

    islands: tuple[Island, ...]
    """Final island states."""

    migrations: int
    """Cross-island signal transfers."""

    generations: int
    """Evolution rounds completed."""

    distinct_cultures: int
    """Number of islands with unique cultures."""


async def evolve_islands(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
    n_islands: int = 3,
    agents_per_island: int = 3,
    generations: int = 3,
    migration_rate: float = 0.2,
    migration_threshold: float = 0.75,
) -> LocalityResult:
    """Evolve signals in isolated islands with selective migration.

    Each island develops its own "culture" (dominant tags/perspectives).
    Strong signals can migrate to adjacent islands, enabling cross-pollination.

    Args:
        task: The problem to solve
        model: Model for signal generation
        options: Generation options (should use discovery_tokens)
        n_islands: Number of isolated populations
        agents_per_island: Agents per island per generation
        generations: Evolution rounds
        migration_rate: Probability of migration per eligible signal
        migration_threshold: Minimum confidence for migration eligibility

    Returns:
        LocalityResult with final island states
    """
    # Initialize empty signal pools per island
    island_signals: list[list[Signal]] = [[] for _ in range(n_islands)]
    total_migrations = 0

    for gen in range(generations):
        # Each island evolves independently
        for island_id in range(n_islands):
            local_signals = island_signals[island_id]

            for agent_id in range(agents_per_island):
                if local_signals:
                    # React to local signals only
                    visible = sorted(
                        local_signals,
                        key=lambda s: s.confidence,
                        reverse=True,
                    )[:5]
                    signal = await generate_reaction(
                        task, visible, model, options,
                        island=island_id, agent=agent_id, generation=gen,
                    )
                else:
                    # No local signals yet — generate fresh
                    signal = await generate_signal(
                        task, model, options,
                        island=island_id, agent=agent_id, generation=gen,
                    )

                island_signals[island_id].append(signal)

        # Migration phase (not on last generation)
        if gen < generations - 1:
            for island_id in range(n_islands):
                for signal in island_signals[island_id]:
                    if (signal.confidence >= migration_threshold
                        and random.random() < migration_rate):
                        # Migrate to adjacent island
                        target = (island_id + 1) % n_islands
                        island_signals[target].append(signal)
                        total_migrations += 1

        # Prune old/weak signals (keep top signals per island)
        max_signals = agents_per_island * 3
        for island_id in range(n_islands):
            island_signals[island_id] = sorted(
                island_signals[island_id],
                key=lambda s: s.confidence + (0.1 if s.generation == gen else 0),
                reverse=True,
            )[:max_signals]

    # Build final island states with culture analysis
    islands = []
    for island_id, signals in enumerate(island_signals):
        # Determine culture from dominant tags
        all_tags = [tag for s in signals for tag in s.tags]
        tag_counts = Counter(all_tags)
        culture = tuple(t for t, _ in tag_counts.most_common(3))

        islands.append(Island(
            island_id=island_id,
            signals=tuple(signals),
            culture=culture,
        ))

    # Count distinct cultures
    culture_sets = [frozenset(isl.culture) for isl in islands]
    distinct = len(set(culture_sets))

    return LocalityResult(
        islands=tuple(islands),
        migrations=total_migrations,
        generations=generations,
        distinct_cultures=distinct,
    )


def select_best_signal_per_island(islands: tuple[Island, ...]) -> list[Signal]:
    """Get the highest-confidence signal from each island."""
    best = []
    for island in islands:
        if island.signals:
            top = max(island.signals, key=lambda s: s.confidence)
            best.append(top)
    return best


def merge_island_signals(
    islands: tuple[Island, ...],
    top_n: int = 2,
) -> list[Signal]:
    """Merge top signals from all islands."""
    merged = []
    for island in islands:
        sorted_signals = sorted(
            island.signals,
            key=lambda s: s.confidence,
            reverse=True,
        )
        merged.extend(sorted_signals[:top_n])
    return merged
