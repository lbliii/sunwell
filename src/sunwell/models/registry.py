"""Thread-safe model registry for instance management (RFC-137).

Provides centralized model instance management with:
- Thread-safe registration and retrieval
- Lazy instantiation from provider + model name
- Integration with existing MODEL_REGISTRY capabilities

Example:
    >>> from sunwell.models.registry import ModelRegistry, get_registry
    >>>
    >>> # Register a model instance
    >>> registry = get_registry()
    >>> registry.register("opus", opus_model)
    >>> registry.register("haiku", haiku_model)
    >>>
    >>> # Retrieve by name
    >>> smart = registry.get("opus")
    >>> cheap = registry.get("haiku")
    >>>
    >>> # Or use factory for lazy creation
    >>> registry.register_factory("gpt-4o", lambda: OpenAIModel("gpt-4o"))
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

# Default model aliases for common delegation patterns
DEFAULT_ALIASES: dict[str, str] = {
    # Anthropic smart → cheap
    "anthropic-smart": "claude-3-opus-20240229",
    "anthropic-cheap": "claude-3-haiku-20240307",
    # OpenAI smart → cheap
    "openai-smart": "gpt-4o",
    "openai-cheap": "gpt-4o-mini",
    # Ollama (local) smart → cheap
    "ollama-smart": "llama3:70b",
    "ollama-cheap": "llama3.2:3b",
}


@dataclass(slots=True)
class ModelRegistry:
    """Thread-safe registry for model instances.

    Supports three ways to get models:
    1. Direct registration: register("name", instance)
    2. Factory registration: register_factory("name", lambda: create())
    3. Auto-creation: get("name", provider="anthropic") - creates if not found

    Thread-safety is achieved via a lock around mutable state.
    """

    _instances: dict[str, ModelProtocol] = field(default_factory=dict)
    """Registered model instances."""

    _factories: dict[str, Callable[[], ModelProtocol]] = field(default_factory=dict)
    """Registered factory functions for lazy instantiation."""

    _aliases: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ALIASES))
    """Alias mappings (e.g., "anthropic-smart" → "claude-3-opus-20240229")."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    def register(self, name: str, model: ModelProtocol) -> None:
        """Register a model instance.

        Args:
            name: Unique name to register under (e.g., "opus", "haiku")
            model: The model instance
        """
        with self._lock:
            self._instances[name] = model

    def register_factory(self, name: str, factory: Callable[[], ModelProtocol]) -> None:
        """Register a factory for lazy instantiation.

        The factory is called once on first access, then cached.

        Args:
            name: Unique name to register under
            factory: Callable that creates the model instance
        """
        with self._lock:
            self._factories[name] = factory

    def register_alias(self, alias: str, target: str) -> None:
        """Register an alias that points to another name.

        Args:
            alias: The alias name (e.g., "smart")
            target: The target model name (e.g., "claude-3-opus-20240229")
        """
        with self._lock:
            self._aliases[alias] = target

    def get(
        self,
        name: str,
        *,
        provider: str | None = None,
        auto_create: bool = True,
    ) -> ModelProtocol | None:
        """Get a model instance by name.

        Resolution order:
        1. Check aliases and resolve
        2. Return cached instance if exists
        3. Call factory if registered
        4. Auto-create via provider if auto_create=True and provider given
        5. Return None

        Args:
            name: Model name or alias
            provider: Provider for auto-creation (anthropic, openai, ollama)
            auto_create: If True and provider given, create model if not found

        Returns:
            Model instance or None if not found
        """
        # Resolve alias outside lock (read-only for aliases after init)
        resolved = self._aliases.get(name, name)

        # Fast path - already cached
        if resolved in self._instances:
            return self._instances[resolved]

        with self._lock:
            # Double-check after acquiring lock
            if resolved in self._instances:
                return self._instances[resolved]

            # Try factory
            if resolved in self._factories:
                instance = self._factories[resolved]()
                self._instances[resolved] = instance
                return instance

            # Auto-create if provider specified
            if auto_create and provider:
                instance = self._create_model(provider, resolved)
                if instance:
                    self._instances[resolved] = instance
                    return instance

        return None

    def _create_model(self, provider: str, model_name: str) -> ModelProtocol | None:
        """Create a model instance from provider and name.

        Uses the same logic as cli/helpers.py:create_model but without CLI deps.
        """
        import os

        try:
            if provider == "anthropic":
                from sunwell.models.anthropic import AnthropicModel

                return AnthropicModel(
                    model=model_name,
                    api_key=os.environ.get("ANTHROPIC_API_KEY"),
                )

            elif provider == "openai":
                from sunwell.models.openai import OpenAIModel

                return OpenAIModel(
                    model=model_name,
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )

            elif provider == "ollama":
                from sunwell.models.ollama import OllamaModel

                return OllamaModel(model=model_name)

            elif provider == "mock":
                from sunwell.models.mock import MockModel

                return MockModel()

        except Exception:
            # Import or instantiation failed - return None
            pass

        return None

    def resolve(
        self,
        model_or_name: ModelProtocol | str | None,
        *,
        provider: str | None = None,
        fallback: ModelProtocol | None = None,
    ) -> ModelProtocol | None:
        """Resolve a model reference to an instance.

        Handles both model instances (pass-through) and string names (lookup).
        This is the main method Agent uses for delegation model resolution.

        Args:
            model_or_name: Either a ModelProtocol instance or a string name
            provider: Provider for auto-creation if string name
            fallback: Model to return if resolution fails

        Returns:
            Resolved model instance or fallback
        """
        if model_or_name is None:
            return fallback

        # Already a model instance - pass through
        if not isinstance(model_or_name, str):
            return model_or_name

        # String name - look up in registry
        resolved = self.get(model_or_name, provider=provider)
        return resolved if resolved is not None else fallback

    def list_registered(self) -> list[str]:
        """List all registered model names (instances + factories)."""
        with self._lock:
            return list(set(self._instances.keys()) | set(self._factories.keys()))

    def clear(self) -> None:
        """Clear all registered models (for testing)."""
        with self._lock:
            self._instances.clear()
            self._factories.clear()


# Global registry instance (thread-safe singleton via ContextVar)
_global_registry: ContextVar[ModelRegistry | None] = ContextVar(
    "_global_registry", default=None
)


def get_registry() -> ModelRegistry:
    """Get the global model registry.

    Creates the registry on first access. Thread-safe.

    Returns:
        The global ModelRegistry instance
    """
    registry = _global_registry.get()
    if registry is None:
        registry = ModelRegistry()
        _global_registry.set(registry)
    return registry


def resolve_model(
    model_or_name: ModelProtocol | str | None,
    *,
    provider: str | None = None,
    fallback: ModelProtocol | None = None,
) -> ModelProtocol | None:
    """Convenience function to resolve a model reference.

    Args:
        model_or_name: Either a ModelProtocol instance or a string name
        provider: Provider for auto-creation if string name
        fallback: Model to return if resolution fails

    Returns:
        Resolved model instance or fallback
    """
    return get_registry().resolve(model_or_name, provider=provider, fallback=fallback)
