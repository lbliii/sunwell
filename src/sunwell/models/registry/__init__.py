"""Model registry for instance management.

Thread-safe registry for model instances with lazy instantiation
and delegation pattern support.
"""

from sunwell.models.registry.registry import (
    DEFAULT_ALIASES,
    ModelRegistry,
    get_registry,
    resolve_model,
)

__all__ = [
    "ModelRegistry",
    "get_registry",
    "resolve_model",
    "DEFAULT_ALIASES",
]
