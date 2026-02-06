"""Tests for project workspace validation (RFC-117).

Tests the validation guards that prevent using invalid directories as workspaces.
With out-of-tree state isolation, the self-repo guard has been removed; Sunwell
can now be used to build itself without any special flags.
"""

from pathlib import Path

import pytest

from sunwell.knowledge.project.validation import (
    ProjectValidationError,
    _is_sunwell_repo,
    validate_not_sunwell_directory,
    validate_workspace,
)


class TestValidateNotSunwellDirectory:
    """Tests for .sunwell directory guard."""

    def test_rejects_sunwell_directory(self, tmp_path: Path) -> None:
        """Validation rejects .sunwell directory as workspace."""
        sunwell_dir = tmp_path / ".sunwell"
        sunwell_dir.mkdir()

        with pytest.raises(ProjectValidationError) as exc_info:
            validate_not_sunwell_directory(sunwell_dir)

        assert ".sunwell" in str(exc_info.value)
        assert "reserved for internal sunwell data" in str(exc_info.value)

    def test_accepts_regular_directory(self, tmp_path: Path) -> None:
        """Validation accepts regular directories."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        # Should not raise
        validate_not_sunwell_directory(project_dir)

    def test_accepts_directory_with_sunwell_in_name(self, tmp_path: Path) -> None:
        """Validation accepts directories that contain 'sunwell' but aren't named '.sunwell'."""
        project_dir = tmp_path / "my-sunwell-project"
        project_dir.mkdir()

        # Should not raise
        validate_not_sunwell_directory(project_dir)

    def test_accepts_sunwell_without_dot(self, tmp_path: Path) -> None:
        """Validation accepts 'sunwell' directory (no leading dot)."""
        project_dir = tmp_path / "sunwell"
        project_dir.mkdir()

        # Should not raise - only .sunwell is blocked
        validate_not_sunwell_directory(project_dir)


class TestValidateWorkspace:
    """Tests for combined workspace validation."""

    def test_rejects_sunwell_directory(self, tmp_path: Path) -> None:
        """validate_workspace rejects .sunwell directory."""
        sunwell_dir = tmp_path / ".sunwell"
        sunwell_dir.mkdir()

        with pytest.raises(ProjectValidationError) as exc_info:
            validate_workspace(sunwell_dir)

        assert ".sunwell" in str(exc_info.value)

    def test_accepts_valid_workspace(self, tmp_path: Path) -> None:
        """validate_workspace accepts valid workspace."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        # Should not raise
        validate_workspace(project_dir)

    def test_accepts_sunwell_repo_as_workspace(self, tmp_path: Path) -> None:
        """validate_workspace now accepts Sunwell's own repo (guard removed)."""
        repo = tmp_path / "sunwell"
        repo.mkdir()
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "sunwell"\nversion = "1.0.0"\n'
        )

        # Should NOT raise — self-repo guard is removed
        validate_workspace(repo)


class TestIsSunwellRepo:
    """Tests for _is_sunwell_repo detection helper.

    _is_sunwell_repo is still used by the CLI for auto-detecting Sunwell's
    repo and configuring external state at init time.
    """

    def test_detects_by_pyproject(self, tmp_path: Path) -> None:
        """Detects Sunwell repo via pyproject.toml."""
        project_dir = tmp_path / "sw"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "sunwell"\n'
        )
        assert _is_sunwell_repo(project_dir) is True

    def test_detects_by_source_structure(self, tmp_path: Path) -> None:
        """Detects Sunwell repo via src/sunwell/ layout."""
        project_dir = tmp_path / "sw"
        project_dir.mkdir()
        src = project_dir / "src" / "sunwell"
        src.mkdir(parents=True)
        (src / "agent").mkdir()
        (src / "tools").mkdir()
        assert _is_sunwell_repo(project_dir) is True

    def test_rejects_regular_project(self, tmp_path: Path) -> None:
        """Regular projects are not detected as Sunwell."""
        project_dir = tmp_path / "my-app"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "my-app"\n'
        )
        assert _is_sunwell_repo(project_dir) is False

    def test_rejects_empty_directory(self, tmp_path: Path) -> None:
        """Empty directories are not detected as Sunwell."""
        project_dir = tmp_path / "empty"
        project_dir.mkdir()
        assert _is_sunwell_repo(project_dir) is False

    def test_insufficient_core_modules(self, tmp_path: Path) -> None:
        """Fewer than 2 core modules is not enough for detection."""
        project_dir = tmp_path / "partial"
        project_dir.mkdir()
        src = project_dir / "src" / "sunwell"
        src.mkdir(parents=True)
        (src / "agent").mkdir()
        # Only 1 core marker — not enough
        assert _is_sunwell_repo(project_dir) is False
