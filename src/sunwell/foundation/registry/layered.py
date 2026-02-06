"""LayeredLensRegistry - Helm-style cascade/override lens registry.

Provides lens resolution with priority order:
1. Local (.sunwell/lenses/) - highest priority
2. Installed (~/.sunwell/lenses/) - medium priority
3. Built-in (bundled with Sunwell) - lowest priority

Lenses from higher layers override lower layers. All sources are tracked
for collision detection and qualified access (e.g., builtin::coder).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens

# Layer priority (higher number = higher priority)
LAYER_PRIORITY = {
    "builtin": 1,
    "installed": 2,
    "local": 3,
}


@dataclass
class LensEntry:
    """Tracks where a lens came from."""

    lens: Lens
    layer: str  # "local", "installed", "builtin"
    source_path: Path  # Path to the lens file
    collection: str | None = None  # Collection name for installed lenses

    @property
    def qualified_name(self) -> str:
        """Get fully qualified name for this lens entry."""
        if self.layer == "local":
            return f"local::{self.lens.metadata.name}"
        elif self.layer == "installed" and self.collection:
            return f"{self.collection}::{self.lens.metadata.name}"
        else:
            return f"builtin::{self.lens.metadata.name}"

    @property
    def display_source(self) -> str:
        """Get human-readable source string."""
        if self.layer == "local":
            return "local"
        elif self.layer == "installed" and self.collection:
            return self.collection
        else:
            return "builtin"


@dataclass
class LayeredLensRegistry:
    """Registry with Helm-style cascade/override semantics.

    Lenses from higher priority layers override lower ones.
    All sources are tracked for collision detection and qualified access.
    """

    # All entries by layer
    layers: dict[str, list[LensEntry]] = field(default_factory=dict)

    # Resolved lenses (winner for each lens name)
    resolved: dict[str, LensEntry] = field(default_factory=dict)

    # All entries for each shortcut (for collision detection)
    shortcut_entries: dict[str, list[LensEntry]] = field(default_factory=dict)

    # Quick lookup: shortcut -> winning lens name
    shortcuts: dict[str, str] = field(default_factory=dict)

    # Track which shortcuts have been warned about (session-level)
    _warned_shortcuts: set[str] = field(default_factory=set)

    @classmethod
    def build(
        cls,
        local_dir: Path | None = None,
        installed_dir: Path | None = None,
        builtin_dir: Path | None = None,
    ) -> LayeredLensRegistry:
        """Build a layered registry from multiple lens directories.

        Args:
            local_dir: Path to local .sunwell/lenses/ directory
            installed_dir: Path to installed ~/.sunwell/lenses/ directory
            builtin_dir: Path to built-in lenses directory

        Returns:
            LayeredLensRegistry with all lenses indexed
        """
        registry = cls()
        registry.layers = {"local": [], "installed": [], "builtin": []}

        # Load layers in priority order (lowest first, so higher can override)

        # Layer 1: Built-in (lowest priority)
        if builtin_dir and builtin_dir.exists():
            registry._load_layer(builtin_dir, "builtin", None)

        # Layer 2: Installed (medium priority)
        if installed_dir and installed_dir.exists():
            registry._load_layer(installed_dir, "installed", None)

        # Layer 3: Local (highest priority)
        if local_dir and local_dir.exists():
            registry._load_layer(local_dir, "local", None)

        return registry

    @classmethod
    def from_discovery(cls, workspace: Path | None = None) -> LayeredLensRegistry:
        """Build registry using standard discovery paths.

        Args:
            workspace: Optional workspace path for local lenses.
                      If None, uses current working directory.

        Returns:
            LayeredLensRegistry with all discovered lenses
        """
        workspace = workspace or Path.cwd()

        return cls.build(
            local_dir=workspace / ".sunwell" / "lenses",
            installed_dir=Path.home() / ".sunwell" / "lenses",
            builtin_dir=Path(__file__).parent.parent.parent / "lenses",
        )

    def _load_layer(
        self, lenses_dir: Path, layer: str, collection: str | None
    ) -> None:
        """Load lenses from a directory into a specific layer."""
        from sunwell.foundation.schema.loader import LensLoader

        loader = LensLoader()

        # Load .lens and .lens.yaml files
        for ext in ["*.lens", "*.lens.yaml"]:
            for lens_path in lenses_dir.glob(ext):
                try:
                    lens = loader.load(lens_path)
                    if not lens:
                        continue

                    entry = LensEntry(
                        lens=lens,
                        layer=layer,
                        source_path=lens_path,
                        collection=collection,
                    )

                    # Add to layer
                    self.layers[layer].append(entry)

                    # Update resolved (last one wins due to load order)
                    self.resolved[lens.metadata.name] = entry

                    # Index shortcuts from lens router
                    if lens.router and lens.router.shortcuts:
                        for shortcut, skill_name in lens.router.shortcuts.items():
                            if shortcut not in self.shortcut_entries:
                                self.shortcut_entries[shortcut] = []
                            self.shortcut_entries[shortcut].append(entry)
                            # Winner is the one from highest priority layer
                            self.shortcuts[shortcut] = lens.metadata.name

                except Exception as e:
                    print(
                        f"Warning: Failed to load lens {lens_path}: {e}",
                        file=sys.stderr,
                    )

    @property
    def lenses(self) -> dict[str, Lens]:
        """Get all resolved lenses."""
        return {name: entry.lens for name, entry in self.resolved.items()}

    def get(self, name: str) -> Lens | None:
        """Get lens by name (uses priority resolution)."""
        entry = self.get_entry(name)
        return entry.lens if entry else None

    def get_entry(self, name: str) -> LensEntry | None:
        """Get lens entry by name with full source information."""
        # Check for qualified name (layer::name)
        if "::" in name and not name.startswith("::"):
            return self._resolve_qualified(name)

        # Direct name match
        if name in self.resolved:
            return self.resolved[name]

        # Try case-insensitive match
        name_lower = name.lower()
        for lens_name, entry in self.resolved.items():
            if lens_name.lower() == name_lower:
                return entry

        return None

    def _resolve_qualified(self, qualified: str) -> LensEntry | None:
        """Resolve a qualified name (e.g., builtin::coder, local::coder)."""
        if "::" not in qualified:
            return None

        qualifier, lens_name = qualified.split("::", 1)
        qualifier_lower = qualifier.lower()

        # Find entries matching both qualifier and lens name
        for entry in self.resolved.values():
            if entry.lens.metadata.name.lower() != lens_name.lower():
                continue

            if qualifier_lower == entry.layer:
                return entry
            if entry.collection and entry.collection.lower() == qualifier_lower:
                return entry

        # Also check all layers (not just resolved winners)
        for layer_entries in self.layers.values():
            for entry in layer_entries:
                if entry.lens.metadata.name.lower() != lens_name.lower():
                    continue

                if qualifier_lower == entry.layer:
                    return entry
                if entry.collection and entry.collection.lower() == qualifier_lower:
                    return entry

        return None

    def resolve_shortcut(
        self, shortcut: str, warn_collision: bool = True
    ) -> tuple[Lens | None, str | None]:
        """Resolve a shortcut to a lens.

        Args:
            shortcut: Shortcut string (e.g., "::code", "code")
            warn_collision: If True, print warning on collision

        Returns:
            Tuple of (lens, skill_name) or (None, None) if not found
        """
        # Normalize shortcut
        if not shortcut.startswith("::"):
            shortcut = f"::{shortcut}"

        if shortcut not in self.shortcuts:
            # Try without ::
            shortcut_clean = shortcut.lstrip(":")
            if shortcut_clean in self.shortcuts:
                shortcut = shortcut_clean
            else:
                return None, None

        lens_name = self.shortcuts[shortcut]
        entry = self.resolved.get(lens_name)

        if entry and warn_collision:
            self._maybe_warn_collision(shortcut)

        # Get skill name from shortcut
        skill_name = None
        if entry and entry.lens.router and entry.lens.router.shortcuts:
            skill_name = entry.lens.router.shortcuts.get(shortcut)

        return entry.lens if entry else None, skill_name

    def _maybe_warn_collision(self, shortcut: str) -> None:
        """Print collision warning once per session."""
        if shortcut in self._warned_shortcuts:
            return

        entries = self.shortcut_entries.get(shortcut, [])
        if len(entries) <= 1:
            return

        self._warned_shortcuts.add(shortcut)
        warning = self.format_collision_warning(shortcut)
        if warning:
            print(warning, file=sys.stderr)

    def get_collisions(self) -> dict[str, list[LensEntry]]:
        """Get shortcuts with multiple sources (collisions)."""
        return {
            shortcut: entries
            for shortcut, entries in self.shortcut_entries.items()
            if len(entries) > 1
        }

    def get_overrides(self) -> list[tuple[str, LensEntry, list[LensEntry]]]:
        """Get lenses that override others.

        Returns:
            List of (lens_name, winner, overridden_entries)
        """
        overrides = []

        for name, winner in self.resolved.items():
            # Find all entries for this lens name
            all_entries = [
                entry
                for layer_entries in self.layers.values()
                for entry in layer_entries
                if entry.lens.metadata.name == name and entry != winner
            ]

            if all_entries:
                overrides.append((name, winner, all_entries))

        return overrides

    def format_collision_warning(self, shortcut: str) -> str | None:
        """Format warning message for a collision."""
        entries = self.shortcut_entries.get(shortcut, [])
        if len(entries) <= 1:
            return None

        # Sort by priority (highest first)
        sorted_entries = sorted(
            entries,
            key=lambda e: LAYER_PRIORITY.get(e.layer, 0),
            reverse=True,
        )

        winner = sorted_entries[0]
        others = sorted_entries[1:]

        # Format qualified names for others
        other_qualifiers = [e.qualified_name for e in others]

        return (
            f"Shortcut collision: {shortcut}\n"
            f"  Using: {winner.display_source}:{winner.lens.metadata.name}\n"
            f"  Also available: {', '.join(other_qualifiers)}\n"
            f"  Tip: Use qualified name (e.g., builtin::coder) to specify"
        )

    def list_all(self) -> list[LensEntry]:
        """Get all resolved lens entries."""
        return list(self.resolved.values())

    def list_by_layer(self, layer: str) -> list[LensEntry]:
        """Get all lenses from a specific layer."""
        return self.layers.get(layer, [])

    def summary(self) -> dict[str, int]:
        """Get summary of lenses by layer."""
        return {
            layer: len(entries) for layer, entries in self.layers.items()
        }
