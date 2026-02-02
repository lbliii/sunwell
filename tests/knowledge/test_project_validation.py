"""Tests for project workspace validation (RFC-117).

Tests the validation guards that prevent using invalid directories as workspaces.
"""

from pathlib import Path

import pytest

from sunwell.knowledge.project.validation import (
    ProjectValidationError,
    validate_not_sunwell_directory,
    validate_not_sunwell_repo,
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


class TestValidateNotSunwellRepo:
    """Tests for Sunwell repository guard."""

    def test_rejects_sunwell_repo_by_pyproject(self, tmp_path: Path) -> None:
        """Rejects directory with sunwell pyproject.toml."""
        project_dir = tmp_path / "sunwell-repo"
        project_dir.mkdir()
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "sunwell"\nversion = "1.0.0"\n'
        )

        with pytest.raises(ProjectValidationError) as exc_info:
            validate_not_sunwell_repo(project_dir)

        assert "Sunwell's own repository" in str(exc_info.value)

    def test_rejects_sunwell_repo_by_structure(self, tmp_path: Path) -> None:
        """Rejects directory with sunwell source structure."""
        project_dir = tmp_path / "sunwell-clone"
        project_dir.mkdir()

        # Create src/sunwell with core modules
        src_sunwell = project_dir / "src" / "sunwell"
        src_sunwell.mkdir(parents=True)
        (src_sunwell / "agent").mkdir()
        (src_sunwell / "tools").mkdir()

        with pytest.raises(ProjectValidationError) as exc_info:
            validate_not_sunwell_repo(project_dir)

        assert "Sunwell's own repository" in str(exc_info.value)

    def test_accepts_regular_python_project(self, tmp_path: Path) -> None:
        """Accepts regular Python projects."""
        project_dir = tmp_path / "my-app"
        project_dir.mkdir()
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "my-app"\nversion = "1.0.0"\n'
        )

        # Should not raise
        validate_not_sunwell_repo(project_dir)
