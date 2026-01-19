"""Global state management for CLI.

Manages singleton instances like SimulacrumManager that are shared
across CLI commands.

Thread Safety:
    Uses threading.Lock for singleton initialization to prevent
    race conditions in free-threaded Python (3.14t).
"""

from __future__ import annotations

import threading
from pathlib import Path

# Global headspace manager instance (lazy-loaded)
_simulacrum_manager = None
_simulacrum_lock = threading.Lock()


def get_simulacrum_manager():
    """Get or create the global SimulacrumManager instance.
    
    Uses lazy loading with thread-safe double-check locking to avoid
    import overhead when not needed. Safe for free-threaded Python.
    
    The manager handles auto-spawn of headspaces based on query patterns.
    Configuration loaded from .sunwell/config.yaml if present.
    """
    global _simulacrum_manager
    
    # Fast path: already initialized
    if _simulacrum_manager is not None:
        return _simulacrum_manager
    
    # Slow path: acquire lock and double-check
    with _simulacrum_lock:
        # Double-check after acquiring lock
        if _simulacrum_manager is not None:
            return _simulacrum_manager
        from sunwell.simulacrum.manager import SimulacrumManager, SpawnPolicy, LifecyclePolicy
        from sunwell.embedding import create_embedder
        from sunwell.config import get_config
        
        config = get_config()
        
        # Build policies from config
        spawn_policy = SpawnPolicy(
            enabled=config.headspace.spawn.enabled,
            novelty_threshold=config.headspace.spawn.novelty_threshold,
            min_queries_before_spawn=config.headspace.spawn.min_queries_before_spawn,
            domain_coherence_threshold=config.headspace.spawn.domain_coherence_threshold,
            max_headspaces=config.headspace.spawn.max_headspaces,
            auto_name=config.headspace.spawn.auto_name,
        )
        
        lifecycle_policy = LifecyclePolicy(
            stale_days=config.headspace.lifecycle.stale_days,
            archive_days=config.headspace.lifecycle.archive_days,
            min_useful_nodes=config.headspace.lifecycle.min_useful_nodes,
            min_useful_learnings=config.headspace.lifecycle.min_useful_learnings,
            auto_archive=config.headspace.lifecycle.auto_archive,
            auto_merge_empty=config.headspace.lifecycle.auto_merge_empty,
            protect_recently_spawned_days=config.headspace.lifecycle.protect_recently_spawned_days,
        )
        
        manager_path = Path(config.headspace.base_path)
        _simulacrum_manager = SimulacrumManager(
            base_path=manager_path,
            spawn_policy=spawn_policy,
            lifecycle_policy=lifecycle_policy,
        )
        
        # Set embedder for semantic operations
        embedder = create_embedder()
        _simulacrum_manager.set_embedder(embedder)
        
    return _simulacrum_manager
