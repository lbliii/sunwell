"""Tests for RFC-133 Phase 2: Project slug registry and URL resolution."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from sunwell.knowledge.project.registry import (
    ProjectRegistry,
    generate_slug,
    is_valid_slug,
)
from sunwell.knowledge.project.types import Project, WorkspaceType


class TestGenerateSlug:
    """Tests for slug generation from project names."""

    def test_simple_name(self):
        assert generate_slug("My App") == "my-app"

    def test_underscores_to_hyphens(self):
        assert generate_slug("my_cool_app") == "my-cool-app"

    def test_removes_special_characters(self):
        assert generate_slug("My App! (v2)") == "my-app-v2"

    def test_collapses_multiple_hyphens(self):
        assert generate_slug("my---app") == "my-app"

    def test_strips_leading_trailing_hyphens(self):
        assert generate_slug("-my-app-") == "my-app"

    def test_truncates_to_30_chars(self):
        long_name = "this-is-a-very-long-project-name-that-exceeds-thirty-chars"
        slug = generate_slug(long_name)
        assert len(slug) <= 30

    def test_empty_name_returns_project(self):
        assert generate_slug("!!!") == "project"

    def test_numbers_preserved(self):
        assert generate_slug("app123") == "app123"


class TestIsValidSlug:
    """Tests for slug validation."""

    def test_valid_simple_slug(self):
        assert is_valid_slug("my-app") is True

    def test_valid_with_numbers(self):
        assert is_valid_slug("app123") is True

    def test_valid_single_char(self):
        assert is_valid_slug("a") is True

    def test_valid_two_chars(self):
        assert is_valid_slug("ab") is True

    def test_valid_with_disambiguator(self):
        assert is_valid_slug("my-app~2") is True
        assert is_valid_slug("my-app~123") is True

    def test_invalid_empty(self):
        assert is_valid_slug("") is False

    def test_invalid_uppercase(self):
        assert is_valid_slug("My-App") is False

    def test_invalid_spaces(self):
        assert is_valid_slug("my app") is False

    def test_invalid_underscores(self):
        assert is_valid_slug("my_app") is False


class TestProjectRegistrySlug:
    """Tests for ProjectRegistry slug functionality."""

    @pytest.fixture
    def temp_registry(self, tmp_path, monkeypatch):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / ".sunwell" / "projects.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Monkeypatch the registry path
        monkeypatch.setattr(
            "sunwell.knowledge.project.registry._get_registry_path",
            lambda: registry_path,
        )

        return ProjectRegistry()

    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create a sample project."""
        project_root = tmp_path / "my-app"
        project_root.mkdir()
        return Project(
            id="proj_abc123",
            name="My Cool App",
            root=project_root,
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )

    def test_register_generates_slug(self, temp_registry, sample_project):
        """Registering a project should generate and return a slug."""
        slug = temp_registry.register(sample_project)
        assert slug == "my-cool-app"

    def test_get_slug_returns_slug(self, temp_registry, sample_project):
        """get_slug should return the registered slug."""
        temp_registry.register(sample_project)
        slug = temp_registry.get_slug(sample_project.id)
        assert slug == "my-cool-app"

    def test_get_slug_nonexistent_returns_none(self, temp_registry):
        """get_slug for unregistered project returns None."""
        slug = temp_registry.get_slug("nonexistent")
        assert slug is None

    def test_resolve_slug_finds_project(self, temp_registry, sample_project):
        """resolve_slug should return the correct project."""
        temp_registry.register(sample_project)
        project, ambiguous = temp_registry.resolve_slug("my-cool-app")
        assert project is not None
        assert project.id == sample_project.id
        assert ambiguous is None

    def test_resolve_slug_not_found(self, temp_registry):
        """resolve_slug for unknown slug returns None."""
        project, ambiguous = temp_registry.resolve_slug("unknown")
        assert project is None
        assert ambiguous is None

    def test_resolve_slug_by_id_fallback(self, temp_registry, sample_project):
        """resolve_slug should try project ID as fallback."""
        temp_registry.register(sample_project)
        project, _ = temp_registry.resolve_slug(sample_project.id)
        assert project is not None
        assert project.id == sample_project.id

    def test_ensure_slug_creates_new(self, temp_registry, sample_project):
        """ensure_slug creates a new slug if none exists."""
        temp_registry._data["projects"][sample_project.id] = sample_project.to_registry_entry()
        slug = temp_registry.ensure_slug(sample_project.id, sample_project.name)
        assert slug == "my-cool-app"

    def test_ensure_slug_returns_existing(self, temp_registry, sample_project):
        """ensure_slug returns existing slug if already registered."""
        temp_registry.register(sample_project)
        slug = temp_registry.ensure_slug(sample_project.id, "Different Name")
        assert slug == "my-cool-app"  # Original slug, not regenerated

    def test_slug_disambiguation(self, temp_registry, tmp_path):
        """Multiple projects with same name get disambiguated slugs."""
        # Create two projects with same name
        project1 = Project(
            id="proj_1",
            name="My App",
            root=tmp_path / "my-app-1",
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        project2 = Project(
            id="proj_2",
            name="My App",
            root=tmp_path / "my-app-2",
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        (tmp_path / "my-app-1").mkdir()
        (tmp_path / "my-app-2").mkdir()

        slug1 = temp_registry.register(project1)
        slug2 = temp_registry.register(project2)

        assert slug1 == "my-app"
        assert slug2 == "my-app~2"

    def test_unregister_removes_slug(self, temp_registry, sample_project):
        """Unregistering a project should remove its slug mapping."""
        temp_registry.register(sample_project)
        assert temp_registry.get_slug(sample_project.id) == "my-cool-app"

        temp_registry.unregister(sample_project.id)
        assert temp_registry.get_slug(sample_project.id) is None

    def test_list_slugs(self, temp_registry, tmp_path):
        """list_slugs returns all slug mappings."""
        project1 = Project(
            id="proj_1",
            name="App One",
            root=tmp_path / "app-one",
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        project2 = Project(
            id="proj_2",
            name="App Two",
            root=tmp_path / "app-two",
            workspace_type=WorkspaceType.REGISTERED,
            created_at=datetime.now(),
        )
        (tmp_path / "app-one").mkdir()
        (tmp_path / "app-two").mkdir()

        temp_registry.register(project1)
        temp_registry.register(project2)

        slugs = temp_registry.list_slugs()
        assert len(slugs) == 2
        slug_names = [s[0] for s in slugs]
        assert "app-one" in slug_names
        assert "app-two" in slug_names
