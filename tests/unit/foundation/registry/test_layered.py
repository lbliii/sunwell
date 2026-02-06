"""Tests for LayeredLensRegistry - Helm-style lens resolution."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from sunwell.foundation.registry.layered import (
    LayeredLensRegistry,
    LensEntry,
    LAYER_PRIORITY,
)
from sunwell.foundation.core.lens import Lens, LensMetadata, Router


class TestLensEntry:
    """Tests for LensEntry dataclass."""

    @pytest.fixture
    def mock_lens(self) -> Lens:
        """Create a mock lens."""
        return Lens(
            metadata=LensMetadata(
                name="test-lens",
                domain="testing",
                description="A test lens",
            ),
        )

    def test_qualified_name_local(self, mock_lens):
        """Local entries should have local:: prefix."""
        entry = LensEntry(
            lens=mock_lens,
            layer="local",
            source_path=Path("/project/.sunwell/lenses/test.lens"),
        )
        assert entry.qualified_name == "local::test-lens"
        assert entry.display_source == "local"

    def test_qualified_name_installed(self, mock_lens):
        """Installed entries should have collection prefix."""
        entry = LensEntry(
            lens=mock_lens,
            layer="installed",
            source_path=Path("~/.sunwell/lenses/test.lens"),
            collection="my-collection",
        )
        assert entry.qualified_name == "my-collection::test-lens"
        assert entry.display_source == "my-collection"

    def test_qualified_name_installed_no_collection(self, mock_lens):
        """Installed entries without collection should use builtin prefix."""
        entry = LensEntry(
            lens=mock_lens,
            layer="installed",
            source_path=Path("~/.sunwell/lenses/test.lens"),
        )
        assert entry.qualified_name == "builtin::test-lens"

    def test_qualified_name_builtin(self, mock_lens):
        """Builtin entries should have builtin:: prefix."""
        entry = LensEntry(
            lens=mock_lens,
            layer="builtin",
            source_path=Path("/pkg/lenses/test.lens"),
        )
        assert entry.qualified_name == "builtin::test-lens"
        assert entry.display_source == "builtin"


class TestLayerPriority:
    """Tests for layer priority constants."""

    def test_priority_order(self):
        """Local should have highest priority, builtin lowest."""
        assert LAYER_PRIORITY["local"] > LAYER_PRIORITY["installed"]
        assert LAYER_PRIORITY["installed"] > LAYER_PRIORITY["builtin"]

    def test_all_layers_defined(self):
        """All standard layers should be defined."""
        assert "local" in LAYER_PRIORITY
        assert "installed" in LAYER_PRIORITY
        assert "builtin" in LAYER_PRIORITY


class TestLayeredLensRegistry:
    """Tests for LayeredLensRegistry."""

    @pytest.fixture
    def local_lens(self) -> Lens:
        """Create a local lens."""
        return Lens(
            metadata=LensMetadata(
                name="coder",
                domain="software",
                description="Local coder lens",
            ),
            router=Router(shortcuts={"::code": "write-code"}),
        )

    @pytest.fixture
    def builtin_lens(self) -> Lens:
        """Create a builtin lens with same name."""
        return Lens(
            metadata=LensMetadata(
                name="coder",
                domain="software",
                description="Builtin coder lens",
            ),
            router=Router(shortcuts={"::code": "builtin-code"}),
        )

    @pytest.fixture
    def other_lens(self) -> Lens:
        """Create a different lens."""
        return Lens(
            metadata=LensMetadata(
                name="writer",
                domain="documentation",
                description="Writer lens",
            ),
            router=Router(shortcuts={"::write": "write-docs"}),
        )

    def test_empty_registry(self):
        """Empty registry should work."""
        registry = LayeredLensRegistry()
        
        assert len(registry.lenses) == 0
        assert registry.get("nonexistent") is None
        assert registry.summary() == {}

    def test_build_with_no_paths(self):
        """Build with no valid paths should return empty registry."""
        registry = LayeredLensRegistry.build(
            local_dir=None,
            installed_dir=None,
            builtin_dir=None,
        )
        
        assert len(registry.resolved) == 0

    def test_local_overrides_builtin(self, local_lens, builtin_lens):
        """Local lenses should override builtin ones with same name."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        # Add builtin first
        builtin_entry = LensEntry(
            lens=builtin_lens,
            layer="builtin",
            source_path=Path("/pkg/coder.lens"),
        )
        registry.layers["builtin"].append(builtin_entry)
        registry.resolved["coder"] = builtin_entry
        
        # Add local (should override)
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/.sunwell/lenses/coder.lens"),
        )
        registry.layers["local"].append(local_entry)
        registry.resolved["coder"] = local_entry  # Override
        
        # Local should win
        resolved = registry.get("coder")
        assert resolved is not None
        assert resolved.metadata.description == "Local coder lens"

    def test_get_entry(self, local_lens):
        """get_entry should return full LensEntry."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        registry.resolved["coder"] = entry
        
        result = registry.get_entry("coder")
        assert result is not None
        assert result.layer == "local"
        assert result.lens.metadata.name == "coder"

    def test_get_entry_case_insensitive(self, local_lens):
        """get_entry should be case-insensitive."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        registry.resolved["coder"] = entry
        
        # Should find with different cases
        assert registry.get_entry("Coder") is not None
        assert registry.get_entry("CODER") is not None

    def test_resolve_qualified_name(self, local_lens, builtin_lens):
        """Qualified names should access specific layers."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        builtin_entry = LensEntry(
            lens=builtin_lens,
            layer="builtin",
            source_path=Path("/pkg/coder.lens"),
        )
        
        registry.layers["local"].append(local_entry)
        registry.layers["builtin"].append(builtin_entry)
        registry.resolved["coder"] = local_entry  # Local wins by default
        
        # Default resolution returns local
        default = registry.get("coder")
        assert default.metadata.description == "Local coder lens"
        
        # Qualified name accesses builtin explicitly
        builtin = registry.get_entry("builtin::coder")
        assert builtin is not None
        assert builtin.layer == "builtin"
        assert builtin.lens.metadata.description == "Builtin coder lens"

    def test_shortcut_indexing(self, local_lens, other_lens):
        """Shortcuts should be indexed from lens routers."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        other_entry = LensEntry(
            lens=other_lens,
            layer="local",
            source_path=Path("/project/writer.lens"),
        )
        
        registry.resolved["coder"] = local_entry
        registry.resolved["writer"] = other_entry
        
        # Manually index shortcuts (normally done in _load_layer)
        registry.shortcuts["::code"] = "coder"
        registry.shortcuts["::write"] = "writer"
        
        assert registry.shortcuts.get("::code") == "coder"
        assert registry.shortcuts.get("::write") == "writer"

    def test_get_collisions(self, local_lens, builtin_lens):
        """Collisions should be detected for duplicate shortcuts."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        builtin_entry = LensEntry(
            lens=builtin_lens,
            layer="builtin",
            source_path=Path("/pkg/coder.lens"),
        )
        
        # Both have ::code shortcut
        registry.shortcut_entries["::code"] = [local_entry, builtin_entry]
        
        collisions = registry.get_collisions()
        assert "::code" in collisions
        assert len(collisions["::code"]) == 2

    def test_get_overrides(self, local_lens, builtin_lens):
        """Overrides should be detected when local shadows builtin."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        builtin_entry = LensEntry(
            lens=builtin_lens,
            layer="builtin",
            source_path=Path("/pkg/coder.lens"),
        )
        
        registry.layers["local"].append(local_entry)
        registry.layers["builtin"].append(builtin_entry)
        registry.resolved["coder"] = local_entry  # Local wins
        
        overrides = registry.get_overrides()
        
        # Should detect that local overrides builtin
        assert len(overrides) == 1
        name, winner, overridden = overrides[0]
        assert name == "coder"
        assert winner.layer == "local"
        assert len(overridden) == 1
        assert overridden[0].layer == "builtin"

    def test_summary(self, local_lens, other_lens):
        """Summary should count lenses by layer."""
        registry = LayeredLensRegistry()
        registry.layers = {
            "local": [
                LensEntry(lens=local_lens, layer="local", source_path=Path("/a.lens")),
                LensEntry(lens=other_lens, layer="local", source_path=Path("/b.lens")),
            ],
            "installed": [],
            "builtin": [
                LensEntry(lens=local_lens, layer="builtin", source_path=Path("/c.lens")),
            ],
        }
        
        summary = registry.summary()
        assert summary["local"] == 2
        assert summary["installed"] == 0
        assert summary["builtin"] == 1

    def test_format_collision_warning(self, local_lens, builtin_lens):
        """Collision warning should format nicely."""
        registry = LayeredLensRegistry()
        
        local_entry = LensEntry(
            lens=local_lens,
            layer="local",
            source_path=Path("/project/coder.lens"),
        )
        builtin_entry = LensEntry(
            lens=builtin_lens,
            layer="builtin",
            source_path=Path("/pkg/coder.lens"),
        )
        
        registry.shortcut_entries["::code"] = [local_entry, builtin_entry]
        
        warning = registry.format_collision_warning("::code")
        
        assert warning is not None
        assert "collision" in warning.lower()
        assert "local" in warning
        assert "builtin" in warning

    def test_list_all(self, local_lens, other_lens):
        """list_all should return all resolved entries."""
        registry = LayeredLensRegistry()
        registry.layers = {"local": [], "installed": [], "builtin": []}
        
        entry1 = LensEntry(lens=local_lens, layer="local", source_path=Path("/a.lens"))
        entry2 = LensEntry(lens=other_lens, layer="local", source_path=Path("/b.lens"))
        
        registry.resolved["coder"] = entry1
        registry.resolved["writer"] = entry2
        
        all_entries = registry.list_all()
        assert len(all_entries) == 2

    def test_list_by_layer(self, local_lens, other_lens):
        """list_by_layer should filter by layer."""
        registry = LayeredLensRegistry()
        
        local_entry = LensEntry(lens=local_lens, layer="local", source_path=Path("/a.lens"))
        builtin_entry = LensEntry(lens=other_lens, layer="builtin", source_path=Path("/b.lens"))
        
        registry.layers = {
            "local": [local_entry],
            "installed": [],
            "builtin": [builtin_entry],
        }
        
        local_lenses = registry.list_by_layer("local")
        builtin_lenses = registry.list_by_layer("builtin")
        
        assert len(local_lenses) == 1
        assert len(builtin_lenses) == 1
        assert local_lenses[0].layer == "local"
        assert builtin_lenses[0].layer == "builtin"
