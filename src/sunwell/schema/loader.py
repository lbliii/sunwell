"""Load lens definitions from YAML/JSON files.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from `sunwell.schema.loader` (the package) instead.

This module re-exports LensLoader from the modular loader package.
The actual implementations are in:
- `sunwell.schema.loader.loader` - Main LensLoader class
- `sunwell.schema.loader.presets` - Preset handling
- `sunwell.schema.loader.parsers` - Parser modules (metadata, heuristics, validators, etc.)

Migration guide:
    # Old (still works)
    from sunwell.schema.loader import LensLoader

    # New (same import, but now from package)
    from sunwell.schema.loader import LensLoader
"""

# Re-export LensLoader for backward compatibility
from sunwell.schema.loader import LensLoader

__all__ = ["LensLoader"]
