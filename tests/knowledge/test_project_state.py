"""Tests for central state directory resolution.

Verifies the precedence logic in resolve_state_dir():
  1. SUNWELL_STATE_DIR env var
  2. state_dir field in .sunwell/project.toml
  3. Legacy default: {workspace}/.sunwell/
"""

from pathlib import Path

import pytest

from sunwell.knowledge.project.state import (
    IN_TREE_ITEMS,
    STATE_SUBDIRS,
    default_state_root,
    ensure_state_dir,
    resolve_state_dir,
    xdg_data_home,
)


class TestResolveStateDir:
    """Tests for resolve_state_dir()."""

    def test_defaults_to_legacy_in_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without any config, state lives in .sunwell/ (backward compat)."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        result = resolve_state_dir(tmp_path)
        assert result == tmp_path / ".sunwell"

    def test_env_var_overrides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SUNWELL_STATE_DIR env var takes highest precedence."""
        custom = tmp_path / "custom-state"
        monkeypatch.setenv("SUNWELL_STATE_DIR", str(custom))

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        result = resolve_state_dir(workspace)
        assert result == custom

    def test_manifest_state_dir_overrides_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """state_dir in project.toml overrides legacy default."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()
        sunwell = workspace / ".sunwell"
        sunwell.mkdir()
        manifest = sunwell / "project.toml"

        external = tmp_path / "external-state"
        manifest.write_text(
            f'[project]\nid = "test"\nname = "test"\ncreated = "2025-01-01"\n\n'
            f'[state]\ndir = "{external}"\n'
        )

        result = resolve_state_dir(workspace)
        assert result == external

    def test_manifest_relative_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relative state_dir is resolved against workspace root."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()
        sunwell = workspace / ".sunwell"
        sunwell.mkdir()
        manifest = sunwell / "project.toml"
        manifest.write_text(
            '[project]\nid = "test"\nname = "test"\ncreated = "2025-01-01"\n\n'
            '[state]\ndir = "../shared-state"\n'
        )

        result = resolve_state_dir(workspace)
        assert result == (workspace / "../shared-state").resolve()

    def test_env_var_beats_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var takes precedence over manifest state_dir."""
        env_dir = tmp_path / "env-state"
        monkeypatch.setenv("SUNWELL_STATE_DIR", str(env_dir))

        workspace = tmp_path / "ws"
        workspace.mkdir()
        sunwell = workspace / ".sunwell"
        sunwell.mkdir()
        manifest = sunwell / "project.toml"
        manifest.write_text(
            '[project]\nid = "test"\nname = "test"\ncreated = "2025-01-01"\n\n'
            '[state]\ndir = "/some/other/dir"\n'
        )

        result = resolve_state_dir(workspace)
        assert result == env_dir

    def test_missing_manifest_uses_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No manifest at all falls back to legacy default."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()

        result = resolve_state_dir(workspace)
        assert result == workspace / ".sunwell"

    def test_manifest_without_state_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Manifest without [state] section falls back to legacy."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()
        sunwell = workspace / ".sunwell"
        sunwell.mkdir()
        manifest = sunwell / "project.toml"
        manifest.write_text(
            '[project]\nid = "test"\nname = "test"\ncreated = "2025-01-01"\n'
        )

        result = resolve_state_dir(workspace)
        assert result == workspace / ".sunwell"


class TestEnsureStateDir:
    """Tests for ensure_state_dir()."""

    def test_creates_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ensure_state_dir creates the state directory."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()

        result = ensure_state_dir(workspace)
        assert result.exists()
        assert result.is_dir()

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling ensure_state_dir twice doesn't fail."""
        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()

        result1 = ensure_state_dir(workspace)
        result2 = ensure_state_dir(workspace)
        assert result1 == result2


class TestXdgDataHome:
    """Tests for xdg_data_home()."""

    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to ~/.local/share when XDG_DATA_HOME is unset."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = xdg_data_home()
        assert result == Path.home() / ".local" / "share"

    def test_custom(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Respects XDG_DATA_HOME when set."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        result = xdg_data_home()
        assert result == tmp_path / "data"


class TestDefaultStateRoot:
    """Tests for default_state_root()."""

    def test_returns_xdg_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns $XDG_DATA_HOME/sunwell/projects/."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = default_state_root()
        assert result == Path.home() / ".local" / "share" / "sunwell" / "projects"


class TestConstants:
    """Tests for module-level constants."""

    def test_state_subdirs_non_empty(self) -> None:
        """STATE_SUBDIRS has expected entries."""
        assert len(STATE_SUBDIRS) > 0
        assert "backlog" in STATE_SUBDIRS
        assert "memory" in STATE_SUBDIRS
        assert "index" in STATE_SUBDIRS

    def test_in_tree_items_non_empty(self) -> None:
        """IN_TREE_ITEMS has expected entries."""
        assert len(IN_TREE_ITEMS) > 0
        assert "project.toml" in IN_TREE_ITEMS
        assert "config.yaml" in IN_TREE_ITEMS
        assert "lenses" in IN_TREE_ITEMS

    def test_no_overlap(self) -> None:
        """STATE_SUBDIRS and IN_TREE_ITEMS don't overlap."""
        overlap = set(STATE_SUBDIRS) & set(IN_TREE_ITEMS)
        assert overlap == set(), f"Unexpected overlap: {overlap}"


class TestProjectManifestStateDir:
    """Tests for ProjectManifest.state_dir field and round-trip serialization."""

    def test_default_state_dir_is_none(self) -> None:
        """New manifests have no state_dir by default."""
        from sunwell.knowledge.project.manifest import create_manifest

        manifest = create_manifest(project_id="test")
        assert manifest.state_dir is None

    def test_state_dir_set_at_creation(self) -> None:
        """create_manifest accepts state_dir argument."""
        from sunwell.knowledge.project.manifest import create_manifest

        manifest = create_manifest(project_id="test", state_dir="/tmp/external")
        assert manifest.state_dir == "/tmp/external"

    def test_to_dict_omits_state_when_none(self) -> None:
        """to_dict does not include [state] section when state_dir is None."""
        from sunwell.knowledge.project.manifest import create_manifest

        manifest = create_manifest(project_id="test")
        d = manifest.to_dict()
        assert "state" not in d

    def test_to_dict_includes_state_when_set(self) -> None:
        """to_dict includes [state] section when state_dir is set."""
        from sunwell.knowledge.project.manifest import create_manifest

        manifest = create_manifest(project_id="test", state_dir="/tmp/ext")
        d = manifest.to_dict()
        assert d["state"] == {"dir": "/tmp/ext"}

    def test_from_dict_reads_state_dir(self) -> None:
        """from_dict parses [state] dir field."""
        from sunwell.knowledge.project.types import ProjectManifest

        data = {
            "project": {"id": "test", "name": "Test", "created": "2025-01-01"},
            "state": {"dir": "/custom/state"},
        }
        manifest = ProjectManifest.from_dict(data)
        assert manifest.state_dir == "/custom/state"

    def test_from_dict_without_state_section(self) -> None:
        """from_dict returns None state_dir when [state] section is missing."""
        from sunwell.knowledge.project.types import ProjectManifest

        data = {
            "project": {"id": "test", "name": "Test", "created": "2025-01-01"},
        }
        manifest = ProjectManifest.from_dict(data)
        assert manifest.state_dir is None

    def test_round_trip_with_state_dir(self, tmp_path: Path) -> None:
        """Save and reload manifest preserves state_dir."""
        from sunwell.knowledge.project.manifest import (
            create_manifest,
            load_manifest,
            save_manifest,
        )

        manifest = create_manifest(project_id="test", state_dir="/ext/state")
        manifest_path = tmp_path / "project.toml"
        save_manifest(manifest, manifest_path)

        loaded = load_manifest(manifest_path)
        assert loaded.state_dir == "/ext/state"
        assert loaded.id == "test"

    def test_round_trip_without_state_dir(self, tmp_path: Path) -> None:
        """Save and reload manifest without state_dir."""
        from sunwell.knowledge.project.manifest import (
            create_manifest,
            load_manifest,
            save_manifest,
        )

        manifest = create_manifest(project_id="test")
        manifest_path = tmp_path / "project.toml"
        save_manifest(manifest, manifest_path)

        loaded = load_manifest(manifest_path)
        assert loaded.state_dir is None


class TestProjectStateDirProperty:
    """Tests for Project.state_dir property with central resolution."""

    def test_defaults_to_in_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without state_root, Project.state_dir uses resolve_state_dir()."""
        from datetime import datetime

        from sunwell.knowledge.project.types import Project, WorkspaceType

        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        project = Project(
            id="test",
            name="Test",
            root=tmp_path,
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        assert project.state_dir == tmp_path / ".sunwell"

    def test_explicit_state_root_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit state_root on Project overrides all resolution."""
        from datetime import datetime

        from sunwell.knowledge.project.types import Project, WorkspaceType

        monkeypatch.delenv("SUNWELL_STATE_DIR", raising=False)

        custom = tmp_path / "custom-state"
        project = Project(
            id="test",
            name="Test",
            root=tmp_path,
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
            state_root=custom,
        )
        assert project.state_dir == custom

    def test_env_var_overrides_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SUNWELL_STATE_DIR env var overrides default for Project.state_dir."""
        from datetime import datetime

        from sunwell.knowledge.project.types import Project, WorkspaceType

        env_dir = tmp_path / "env-state"
        monkeypatch.setenv("SUNWELL_STATE_DIR", str(env_dir))

        project = Project(
            id="test",
            name="Test",
            root=tmp_path,
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        assert project.state_dir == env_dir
