"""Tests for ModelRegistry (RFC-137).

Tests thread-safe model instance management and resolution.
"""

import threading
from unittest.mock import MagicMock

import pytest

from sunwell.models.core.protocol import ModelProtocol
from sunwell.models.registry import (
    DEFAULT_ALIASES,
    ModelRegistry,
    get_registry,
    resolve_model,
)


class TestModelRegistry:
    """Tests for ModelRegistry core functionality."""

    def test_register_and_get(self) -> None:
        """Register a model and retrieve it."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)

        registry.register("test-model", mock_model)

        assert registry.get("test-model") is mock_model

    def test_get_nonexistent_returns_none(self) -> None:
        """Getting a nonexistent model returns None."""
        registry = ModelRegistry()

        assert registry.get("nonexistent", auto_create=False) is None

    def test_register_factory_lazy_creation(self) -> None:
        """Factory is called lazily on first get."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)
        factory = MagicMock(return_value=mock_model)

        registry.register_factory("lazy-model", factory)

        # Factory not called yet
        factory.assert_not_called()

        # First get calls factory
        result = registry.get("lazy-model")
        factory.assert_called_once()
        assert result is mock_model

        # Second get uses cached instance
        result2 = registry.get("lazy-model")
        factory.assert_called_once()  # Still just once
        assert result2 is mock_model

    def test_alias_resolution(self) -> None:
        """Aliases resolve to registered models."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)

        registry.register("claude-3-opus-20240229", mock_model)
        registry.register_alias("opus", "claude-3-opus-20240229")

        result = registry.get("opus")
        assert result is mock_model

    def test_default_aliases_present(self) -> None:
        """Default aliases are available."""
        registry = ModelRegistry()

        assert "anthropic-smart" in registry._aliases
        assert "anthropic-cheap" in registry._aliases
        assert "openai-smart" in registry._aliases
        assert "openai-cheap" in registry._aliases

    def test_list_registered(self) -> None:
        """List shows all registered models."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)

        registry.register("model-a", mock_model)
        registry.register_factory("model-b", lambda: mock_model)

        registered = registry.list_registered()
        assert "model-a" in registered
        assert "model-b" in registered

    def test_clear(self) -> None:
        """Clear removes all registered models."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)

        registry.register("test", mock_model)
        registry.register_factory("test2", lambda: mock_model)

        registry.clear()

        assert registry.get("test", auto_create=False) is None
        assert registry.get("test2", auto_create=False) is None


class TestModelRegistryResolve:
    """Tests for the resolve method."""

    def test_resolve_none_returns_fallback(self) -> None:
        """Resolving None returns fallback."""
        registry = ModelRegistry()
        fallback = MagicMock(spec=ModelProtocol)

        result = registry.resolve(None, fallback=fallback)
        assert result is fallback

    def test_resolve_instance_passthrough(self) -> None:
        """Resolving a model instance passes it through."""
        registry = ModelRegistry()
        model = MagicMock(spec=ModelProtocol)

        result = registry.resolve(model)
        assert result is model

    def test_resolve_string_looks_up(self) -> None:
        """Resolving a string looks up in registry."""
        registry = ModelRegistry()
        mock_model = MagicMock(spec=ModelProtocol)

        registry.register("my-model", mock_model)

        result = registry.resolve("my-model")
        assert result is mock_model

    def test_resolve_string_not_found_returns_fallback(self) -> None:
        """Resolving unknown string returns fallback."""
        registry = ModelRegistry()
        fallback = MagicMock(spec=ModelProtocol)

        result = registry.resolve("unknown", fallback=fallback)
        assert result is fallback


class TestModelRegistryThreadSafety:
    """Tests for thread-safe access."""

    def test_concurrent_register_and_get(self) -> None:
        """Concurrent registration and retrieval is safe."""
        registry = ModelRegistry()
        errors: list[Exception] = []

        def register_models(start: int) -> None:
            try:
                for i in range(100):
                    model = MagicMock(spec=ModelProtocol)
                    registry.register(f"model-{start}-{i}", model)
            except Exception as e:
                errors.append(e)

        def get_models(start: int) -> None:
            try:
                for i in range(100):
                    registry.get(f"model-{start}-{i}", auto_create=False)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=register_models, args=(i,)))
            threads.append(threading.Thread(target=get_models, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_registry_returns_same_instance(self) -> None:
        """get_registry returns a singleton-like instance per context."""
        reg1 = get_registry()
        reg2 = get_registry()

        assert reg1 is reg2

    def test_resolve_model_convenience(self) -> None:
        """resolve_model convenience function works."""
        model = MagicMock(spec=ModelProtocol)

        # Pass-through for instances
        result = resolve_model(model)
        assert result is model

        # Fallback for None
        fallback = MagicMock(spec=ModelProtocol)
        result = resolve_model(None, fallback=fallback)
        assert result is fallback


class TestDefaultAliases:
    """Tests for default alias mappings."""

    def test_anthropic_aliases(self) -> None:
        """Anthropic aliases map to expected models."""
        assert DEFAULT_ALIASES["anthropic-smart"] == "claude-3-opus-20240229"
        assert DEFAULT_ALIASES["anthropic-cheap"] == "claude-3-haiku-20240307"

    def test_openai_aliases(self) -> None:
        """OpenAI aliases map to expected models."""
        assert DEFAULT_ALIASES["openai-smart"] == "gpt-4o"
        assert DEFAULT_ALIASES["openai-cheap"] == "gpt-4o-mini"
