"""Tests for Binding and BindingManager (soul stone attunement).

Covers:
- Binding creation, serialization, migration
- BindingManager CRUD operations
- get_binding_or_create_temp() CLI helper
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.foundation.binding import Binding, BindingManager, get_binding_or_create_temp


class TestBinding:
    """Tests for Binding dataclass."""

    def test_binding_creation_minimal(self) -> None:
        """Create binding with minimal required fields."""
        binding = Binding(name="test", lens_uri="./test.lens")

        assert binding.name == "test"
        assert binding.lens_uri == "./test.lens"
        assert binding.provider == "ollama"  # Default changed to ollama
        assert binding.model == "llama3.1:8b"
        # simulacrum defaults to name
        assert binding.simulacrum == "test"

    def test_binding_creation_full(self) -> None:
        """Create binding with all fields."""
        binding = Binding(
            name="my-project",
            lens_uri="/path/to/lens.lens",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            simulacrum="project-memory",
            tier=2,
            stream=False,
            verbose=True,
            auto_learn=False,
            tools_enabled=True,
            trust_level="shell",
        )

        assert binding.name == "my-project"
        assert binding.provider == "anthropic"
        assert binding.model == "claude-sonnet-4-20250514"
        assert binding.simulacrum == "project-memory"
        assert binding.tier == 2
        assert binding.stream is False
        assert binding.verbose is True
        assert binding.auto_learn is False
        assert binding.tools_enabled is True
        assert binding.trust_level == "shell"

    def test_binding_touch_updates_metadata(self) -> None:
        """touch() updates last_used and increments use_count."""
        binding = Binding(name="test", lens_uri="./test.lens")
        original_last_used = binding.last_used
        original_count = binding.use_count

        binding.touch()

        assert binding.use_count == original_count + 1
        assert binding.last_used >= original_last_used

    def test_binding_save_and_load(self) -> None:
        """Save and load binding preserves all fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "binding.json"

            original = Binding(
                name="test-project",
                lens_uri="/path/to/lens.lens",
                provider="ollama",
                model="llama3.1:8b",
                simulacrum="test-memory",
                tier=2,
                stream=False,
                tools_enabled=True,
                workspace_patterns=["*.py", "*.md"],
            )
            original.save(path)

            loaded = Binding.load(path)

            assert loaded.name == original.name
            assert loaded.lens_uri == original.lens_uri
            assert loaded.provider == original.provider
            assert loaded.model == original.model
            assert loaded.simulacrum == original.simulacrum
            assert loaded.tier == original.tier
            assert loaded.stream == original.stream
            assert loaded.tools_enabled == original.tools_enabled
            assert loaded.workspace_patterns == original.workspace_patterns

    def test_binding_load_migrates_lens_path_to_lens_uri(self) -> None:
        """Loading old binding with 'lens_path' migrates to 'lens_uri'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "old_binding.json"

            # Old format with 'lens_path' instead of 'lens_uri'
            old_data = {
                "name": "legacy",
                "lens_path": "./old.lens",
                "provider": "openai",
                "model": "gpt-4",
            }
            with open(path, "w") as f:
                json.dump(old_data, f)

            loaded = Binding.load(path)

            # lens_path should be migrated to lens_uri
            assert loaded.lens_uri == "./old.lens"

    def test_binding_load_migrates_slug_to_uri(self) -> None:
        """Loading old binding with slug lens_path converts to URI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "old_binding.json"

            # Old format with slug (no path separators)
            old_data = {
                "name": "legacy",
                "lens_path": "tech-writer",  # slug, not a path
                "provider": "openai",
                "model": "gpt-4",
            }
            with open(path, "w") as f:
                json.dump(old_data, f)

            loaded = Binding.load(path)

            # Slug should be converted to URI
            assert loaded.lens_uri == "sunwell:lens/user/tech-writer"

    def test_binding_save_creates_parent_dirs(self) -> None:
        """save() creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "binding.json"

            binding = Binding(name="test", lens_uri="./test.lens")
            binding.save(path)

            assert path.exists()


class TestBindingManager:
    """Tests for BindingManager operations."""

    def test_manager_create_binding(self) -> None:
        """Create a new binding via manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            binding = manager.create(
                name="my-project",
                lens_uri="./writer.lens",
                provider="openai",
            )

            assert binding.name == "my-project"
            assert binding.lens_uri == "./writer.lens"
            # Should be persisted in the isolated bindings directory
            assert (bindings_dir / "global" / "my-project.json").exists()

    def test_manager_create_auto_selects_model(self) -> None:
        """Create binding auto-selects model based on provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            openai = manager.create("test1", lens_uri="./test.lens", provider="openai")
            anthropic = manager.create("test2", lens_uri="./test.lens", provider="anthropic")
            ollama = manager.create("test3", lens_uri="./test.lens", provider="ollama")

            assert openai.model == "gpt-4o"
            assert anthropic.model == "claude-sonnet-4-20250514"
            assert ollama.model == "llama3.1:8b"

    def test_manager_create_normalizes_slug_to_uri(self) -> None:
        """Create binding converts slug to URI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            binding = manager.create(
                name="my-project",
                lens_uri="tech-writer",  # slug, not a path
                provider="openai",
            )

            # Should be converted to URI
            assert binding.lens_uri == "sunwell:lens/user/tech-writer"

    def test_manager_get_binding(self) -> None:
        """Get existing binding by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("test", lens_uri="./test.lens")

            binding = manager.get("test")

            assert binding is not None
            assert binding.name == "test"

    def test_manager_get_nonexistent_returns_none(self) -> None:
        """Get nonexistent binding returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            binding = manager.get("does-not-exist")

            assert binding is None

    def test_manager_set_and_get_default(self) -> None:
        """Set and get default binding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("primary", lens_uri="./primary.lens")
            manager.create("secondary", lens_uri="./secondary.lens")

            success = manager.set_default("primary")
            default = manager.get_default()

            assert success is True
            assert default is not None
            assert default.name == "primary"

    def test_manager_set_default_nonexistent_fails(self) -> None:
        """Setting nonexistent binding as default fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            success = manager.set_default("does-not-exist")

            assert success is False

    def test_manager_get_default_when_none_set(self) -> None:
        """Get default returns None when no default set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            default = manager.get_default()

            assert default is None

    def test_manager_get_or_default_with_name(self) -> None:
        """get_or_default returns named binding when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("specific", lens_uri="./specific.lens")
            manager.create("default", lens_uri="./default.lens")
            manager.set_default("default")

            binding = manager.get_or_default("specific")

            assert binding is not None
            assert binding.name == "specific"

    def test_manager_get_or_default_falls_back(self) -> None:
        """get_or_default falls back to default when no name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("default", lens_uri="./default.lens")
            manager.set_default("default")

            binding = manager.get_or_default(None)

            assert binding is not None
            assert binding.name == "default"

    def test_manager_list_all(self) -> None:
        """List all bindings sorted by last_used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("first", lens_uri="./first.lens")
            manager.create("second", lens_uri="./second.lens")
            manager.create("third", lens_uri="./third.lens")

            # Use 'second' to make it most recent
            manager.use("second")

            bindings = manager.list_all()

            assert len(bindings) == 3
            # Most recently used first
            assert bindings[0].name == "second"

    def test_manager_list_all_empty(self) -> None:
        """List all returns empty list when no bindings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            bindings = manager.list_all()

            assert bindings == []

    def test_manager_delete_binding(self) -> None:
        """Delete a binding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("test", lens_uri="./test.lens")

            success = manager.delete("test")

            assert success is True
            assert manager.get("test") is None

    def test_manager_delete_clears_default(self) -> None:
        """Deleting default binding clears default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("test", lens_uri="./test.lens")
            manager.set_default("test")

            manager.delete("test")

            assert manager.get_default() is None

    def test_manager_delete_nonexistent_fails(self) -> None:
        """Deleting nonexistent binding returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)

            success = manager.delete("does-not-exist")

            assert success is False

    def test_manager_use_marks_as_used(self) -> None:
        """use() gets binding and marks it as used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("test", lens_uri="./test.lens")

            binding = manager.use("test")

            assert binding is not None
            assert binding.use_count == 1

            # Use again
            binding2 = manager.use("test")
            assert binding2 is not None
            assert binding2.use_count == 2


class TestGetBindingOrCreateTemp:
    """Tests for get_binding_or_create_temp() CLI helper.

    This function broke due to parameter rename (headspace -> simulacrum).
    These tests ensure the signature stays stable.
    """

    def test_returns_named_binding_when_exists(self) -> None:
        """Returns existing binding when name matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("existing", lens_uri="./existing.lens")

            binding, is_temp = get_binding_or_create_temp(
                binding_name="existing",
                lens_uri=None,
                provider=None,
                model=None,
                simulacrum=None,
                bindings_dir=bindings_dir,
            )

            assert binding is not None
            assert binding.name == "existing"
            assert is_temp is False

    def test_returns_default_when_no_name_or_lens(self) -> None:
        """Returns default binding when no name or lens provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("default", lens_uri="./default.lens")
            manager.set_default("default")

            binding, is_temp = get_binding_or_create_temp(
                binding_name=None,
                lens_uri=None,
                provider=None,
                model=None,
                simulacrum=None,
                bindings_dir=bindings_dir,
            )

            assert binding is not None
            assert binding.name == "default"
            assert is_temp is False

    def test_creates_temp_binding_from_lens_uri(self) -> None:
        """Creates temporary binding when lens_uri provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"

            binding, is_temp = get_binding_or_create_temp(
                binding_name=None,
                lens_uri="./temp.lens",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                simulacrum="temp-memory",
                bindings_dir=bindings_dir,
            )

            assert binding is not None
            assert binding.name == "_temp"
            assert binding.lens_uri == "./temp.lens"
            assert binding.provider == "anthropic"
            assert binding.model == "claude-sonnet-4-20250514"
            assert binding.simulacrum == "temp-memory"
            assert is_temp is True

    def test_returns_none_when_nothing_matches(self) -> None:
        """Returns None when no binding, no default, no lens_uri."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"

            binding, is_temp = get_binding_or_create_temp(
                binding_name="nonexistent",
                lens_uri=None,
                provider=None,
                model=None,
                simulacrum=None,
                bindings_dir=bindings_dir,
            )

            assert binding is None
            assert is_temp is False

    def test_overrides_binding_with_cli_args(self) -> None:
        """CLI args override binding settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bindings_dir = Path(tmpdir) / "bindings"
            manager = BindingManager(root=Path(tmpdir), bindings_dir=bindings_dir)
            manager.create("test", lens_uri="./test.lens", provider="openai", model="gpt-4o")

            binding, is_temp = get_binding_or_create_temp(
                binding_name="test",
                lens_uri=None,
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                simulacrum="override-memory",
                bindings_dir=bindings_dir,
            )

            assert binding is not None
            assert binding.provider == "anthropic"
            assert binding.model == "claude-sonnet-4-20250514"
            assert binding.simulacrum == "override-memory"

    def test_signature_accepts_lens_uri_parameter(self) -> None:
        """Verify function signature accepts 'lens_uri' (not 'lens_path').

        This test exists because the parameter was renamed and call sites
        could break. This ensures future changes maintain compatibility.
        """
        import inspect
        sig = inspect.signature(get_binding_or_create_temp)
        param_names = list(sig.parameters.keys())

        assert "lens_uri" in param_names
        assert "lens_path" not in param_names
        assert "simulacrum" in param_names
        assert "headspace" not in param_names
