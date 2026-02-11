"""Schema loading and validation for lens definitions."""

# NOTE: LensLoader is NOT imported at package level to avoid circular
# imports with foundation.core.lens (which imports schema.models types).
# Import LensLoader directly: from sunwell.foundation.schema.loader import LensLoader

__all__ = ["LensLoader"]


def __getattr__(name: str):
    """Lazy import to avoid circular dependency."""
    if name == "LensLoader":
        from sunwell.foundation.schema.loader import LensLoader
        return LensLoader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
