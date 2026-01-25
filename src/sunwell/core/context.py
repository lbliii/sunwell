"""Application context with dependency injection.

RFC-025: Protocol Layer - Dependency injection pattern for testability.

AppContext holds all dependencies needed by CLI commands and core logic,
enabling easy swapping for testing or alternative implementations.
"""


from dataclasses import dataclass, field
from pathlib import Path

from sunwell.config import SunwellConfig, get_config
from sunwell.embedding import create_embedder
from sunwell.embedding.protocol import EmbeddingProtocol
from sunwell.models.protocol import ModelProtocol
from sunwell.simulacrum.manager import SimulacrumManager
from sunwell.types.protocol import (
    ConsoleProtocol,
    MemoryStoreProtocol,
)


@dataclass(slots=True)
class AppContext:
    """Application context with all dependencies.

    RFC-025: Dependency injection pattern for testability.

    Holds all major dependencies needed by CLI commands and core logic.
    Can be swapped for test doubles or alternative implementations.

    Usage:
        # Production
        ctx = AppContext.from_config()

        # Testing
        ctx = AppContext.for_testing()

        # Custom
        ctx = AppContext(
            config=my_config,
            memory=my_memory_store,
            embedder=my_embedder,
            console=my_console,
        )
    """

    config: SunwellConfig
    """Root configuration."""

    memory: MemoryStoreProtocol
    """Memory store (SimulacrumManager or test double)."""

    embedder: EmbeddingProtocol
    """Embedding provider."""

    console: ConsoleProtocol = field(default=None)
    """Console for I/O (defaults to Rich Console)."""

    def __post_init__(self):
        """Initialize defaults after construction."""
        if self.console is None:
            from rich.console import Console
            self.console = Console()

    @classmethod
    def from_config(cls, config: SunwellConfig | None = None) -> AppContext:
        """Factory for production use.

        Creates AppContext with real implementations from config.

        Args:
            config: Configuration to use (defaults to get_config())

        Returns:
            AppContext with production dependencies
        """
        if config is None:
            config = get_config()

        # Create embedder
        embedder = create_embedder()

        # Create SimulacrumManager
        from sunwell.simulacrum.manager import LifecyclePolicy, SpawnPolicy

        spawn_policy = SpawnPolicy(
            enabled=config.simulacrum.spawn.enabled,
            novelty_threshold=config.simulacrum.spawn.novelty_threshold,
            min_queries_before_spawn=config.simulacrum.spawn.min_queries_before_spawn,
            domain_coherence_threshold=config.simulacrum.spawn.domain_coherence_threshold,
            max_simulacrums=config.simulacrum.spawn.max_simulacrums,
            auto_name=config.simulacrum.spawn.auto_name,
        )

        lifecycle_policy = LifecyclePolicy(
            stale_days=config.simulacrum.lifecycle.stale_days,
            archive_days=config.simulacrum.lifecycle.archive_days,
            min_useful_nodes=config.simulacrum.lifecycle.min_useful_nodes,
            min_useful_learnings=config.simulacrum.lifecycle.min_useful_learnings,
            auto_archive=config.simulacrum.lifecycle.auto_archive,
            auto_merge_empty=config.simulacrum.lifecycle.auto_merge_empty,
            protect_recently_spawned_days=config.simulacrum.lifecycle.protect_recently_spawned_days,
        )

        manager_path = Path(config.simulacrum.base_path)
        memory = SimulacrumManager(
            base_path=manager_path,
            spawn_policy=spawn_policy,
            lifecycle_policy=lifecycle_policy,
        )

        # Set embedder for semantic operations
        memory.set_embedder(embedder)

        return cls(
            config=config,
            memory=memory,
            embedder=embedder,
        )

    @classmethod
    def for_testing(cls) -> AppContext:
        """Factory for test use.

        Creates AppContext with test doubles (in-memory, no I/O).

        Returns:
            AppContext with test dependencies
        """
        from sunwell.config import SunwellConfig

        # Minimal config for testing
        config = SunwellConfig()

        # In-memory embedder (hash-based, no API calls)
        from sunwell.embedding.hash import HashEmbedder
        embedder = HashEmbedder()

        # In-memory memory store (no disk I/O)
        import tempfile

        from sunwell.simulacrum.manager import SimulacrumManager

        # Use a persistent temp directory (not cleaned up immediately)
        tmpdir = tempfile.mkdtemp(prefix="sunwell_test_")
        memory = SimulacrumManager(base_path=Path(tmpdir))
        memory.set_embedder(embedder)

        # Null console (no output)
        class NullConsole:
            def print(self, *args: any, **kwargs: any) -> None:
                pass

            def input(self, prompt: str = "") -> str:
                return ""

        return cls(
            config=config,
            memory=memory,
            embedder=embedder,
            console=NullConsole(),
        )

    def create_model(self, provider: str, model: str | None = None) -> ModelProtocol:
        """Create a model instance.

        Args:
            provider: Model provider (openai, anthropic, ollama, etc.)
            model: Model name (optional, uses provider default)

        Returns:
            ModelProtocol instance
        """
        from sunwell.cli.helpers import create_model
        return create_model(provider, model)
