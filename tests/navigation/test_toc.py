"""Tests for TocNode and ProjectToc (RFC-124)."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sunwell.navigation.toc import ProjectToc, TocNode, node_id_from_path


class TestTocNode:
    """Tests for TocNode dataclass."""

    def test_create_node(self) -> None:
        """Test basic node creation."""
        node = TocNode(
            node_id="sunwell.naaru.harmonic",
            title="Harmonic Resonance",
            node_type="module",
            summary="Coordinates multi-model consensus",
            path="sunwell/naaru/harmonic.py",
        )

        assert node.node_id == "sunwell.naaru.harmonic"
        assert node.title == "Harmonic Resonance"
        assert node.node_type == "module"
        assert node.summary == "Coordinates multi-model consensus"
        assert node.path == "sunwell/naaru/harmonic.py"
        assert node.line_range is None
        assert node.children == ()
        assert node.cross_refs == ()
        assert node.concepts == ()

    def test_node_immutable(self) -> None:
        """Test that TocNode is frozen (immutable)."""
        node = TocNode(
            node_id="test",
            title="Test",
            node_type="module",
            summary="Test node",
            path="test.py",
        )

        with pytest.raises(AttributeError):
            node.title = "Changed"  # type: ignore

    def test_node_with_all_fields(self) -> None:
        """Test node creation with all optional fields."""
        node = TocNode(
            node_id="sunwell.auth.token",
            title="TokenValidator",
            node_type="class",
            summary="Validates authentication tokens",
            path="sunwell/auth/token.py",
            line_range=(45, 120),
            children=("sunwell.auth.token.validate", "sunwell.auth.token.refresh"),
            cross_refs=("import:sunwell.core.errors", "see:security/audit.py"),
            concepts=("auth", "security"),
        )

        assert node.line_range == (45, 120)
        assert len(node.children) == 2
        assert len(node.cross_refs) == 2
        assert "auth" in node.concepts

    def test_to_compact_dict_minimal(self) -> None:
        """Test compact dict serialization with minimal fields."""
        node = TocNode(
            node_id="test.module",
            title="module",
            node_type="module",
            summary="A test module",
            path="test/module.py",
        )

        compact = node.to_compact_dict()

        assert compact["id"] == "test.module"
        assert compact["t"] == "module"
        assert compact["s"] == "A test module"
        assert "c" not in compact  # No children
        assert "r" not in compact  # No cross_refs
        assert "k" not in compact  # No concepts

    def test_to_compact_dict_full(self) -> None:
        """Test compact dict with all optional fields."""
        node = TocNode(
            node_id="test.module",
            title="module",
            node_type="module",
            summary="A test module",
            path="test/module.py",
            children=("test.module.func",),
            cross_refs=("import:other",),
            concepts=("core",),
        )

        compact = node.to_compact_dict()

        assert compact["c"] == ["test.module.func"]
        assert compact["r"] == ["import:other"]
        assert compact["k"] == ["core"]


class TestProjectToc:
    """Tests for ProjectToc container."""

    def test_create_empty_toc(self) -> None:
        """Test empty ToC creation."""
        toc = ProjectToc(root_id="project")

        assert toc.root_id == "project"
        assert toc.node_count == 0
        assert toc.file_count == 0
        assert len(toc.nodes) == 0
        assert len(toc.path_to_node) == 0

    def test_add_node(self) -> None:
        """Test adding nodes to ToC."""
        toc = ProjectToc(root_id="project")

        node = TocNode(
            node_id="project.src",
            title="src",
            node_type="directory",
            summary="Source code",
            path="src",
            concepts=("core",),
        )
        toc.add_node(node)

        assert toc.node_count == 1
        assert "project.src" in toc.nodes
        assert toc.path_to_node["src"] == "project.src"
        assert "project.src" in toc.concept_index.get("core", [])

    def test_get_node(self) -> None:
        """Test node retrieval."""
        toc = ProjectToc(root_id="project")
        node = TocNode(
            node_id="project.src",
            title="src",
            node_type="directory",
            summary="Source code",
            path="src",
        )
        toc.add_node(node)

        retrieved = toc.get_node("project.src")
        assert retrieved is not None
        assert retrieved.title == "src"

        missing = toc.get_node("nonexistent")
        assert missing is None

    def test_get_children(self) -> None:
        """Test child node retrieval."""
        toc = ProjectToc(root_id="project")

        parent = TocNode(
            node_id="project",
            title="Project",
            node_type="directory",
            summary="Root",
            path=".",
            children=("project.src", "project.tests"),
        )
        child1 = TocNode(
            node_id="project.src",
            title="src",
            node_type="directory",
            summary="Source",
            path="src",
        )
        child2 = TocNode(
            node_id="project.tests",
            title="tests",
            node_type="directory",
            summary="Tests",
            path="tests",
        )

        toc.add_node(parent)
        toc.add_node(child1)
        toc.add_node(child2)

        children = toc.get_children("project")
        assert len(children) == 2
        assert {c.node_id for c in children} == {"project.src", "project.tests"}

    def test_get_nodes_by_concept(self) -> None:
        """Test concept-based lookup."""
        toc = ProjectToc(root_id="project")

        auth_node = TocNode(
            node_id="project.auth",
            title="auth",
            node_type="module",
            summary="Authentication",
            path="auth.py",
            concepts=("auth", "security"),
        )
        api_node = TocNode(
            node_id="project.api",
            title="api",
            node_type="module",
            summary="API endpoints",
            path="api.py",
            concepts=("api",),
        )

        toc.add_node(auth_node)
        toc.add_node(api_node)

        auth_nodes = toc.get_nodes_by_concept("auth")
        assert len(auth_nodes) == 1
        assert auth_nodes[0].node_id == "project.auth"

        security_nodes = toc.get_nodes_by_concept("security")
        assert len(security_nodes) == 1

        missing_nodes = toc.get_nodes_by_concept("nonexistent")
        assert len(missing_nodes) == 0

    def test_to_context_json(self) -> None:
        """Test JSON serialization for LLM context."""
        toc = _create_sample_toc()

        json_str = toc.to_context_json(max_depth=2)
        data = json.loads(json_str)

        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of first node
        first = data[0]
        assert "id" in first
        assert "t" in first
        assert "s" in first

    def test_get_subtree(self) -> None:
        """Test subtree extraction."""
        toc = _create_sample_toc()

        subtree = toc.get_subtree("project.src", depth=1)
        data = json.loads(subtree)

        assert isinstance(data, list)
        # Should include src and its immediate children
        ids = {n["id"] for n in data}
        assert "project.src" in ids

    def test_estimate_tokens(self) -> None:
        """Test token estimation."""
        toc = _create_sample_toc()

        tokens_d1 = toc.estimate_tokens(max_depth=1)
        tokens_d2 = toc.estimate_tokens(max_depth=2)

        assert tokens_d1 > 0
        assert tokens_d2 >= tokens_d1  # More depth = more tokens

    def test_save_and_load(self) -> None:
        """Test persistence round-trip."""
        toc = _create_sample_toc()
        toc.generated_at = datetime.now()

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            toc.save(base)

            loaded = ProjectToc.load(base)

            assert loaded is not None
            assert loaded.root_id == toc.root_id
            assert loaded.node_count == toc.node_count
            assert loaded.generated_at is not None

    def test_load_nonexistent(self) -> None:
        """Test loading from nonexistent path."""
        result = ProjectToc.load(Path("/nonexistent/path"))
        assert result is None

    def test_is_stale(self) -> None:
        """Test staleness detection."""
        toc = ProjectToc(root_id="project")

        # No timestamp = stale
        assert toc.is_stale()

        # Recent timestamp = fresh
        toc.generated_at = datetime.now()
        assert not toc.is_stale()

        # Old timestamp = stale
        toc.generated_at = datetime.now() - timedelta(hours=25)
        assert toc.is_stale()

        # Custom max age
        toc.generated_at = datetime.now() - timedelta(hours=2)
        assert not toc.is_stale(max_age_hours=24)
        assert toc.is_stale(max_age_hours=1)


class TestNodeIdFromPath:
    """Tests for node_id_from_path helper."""

    def test_simple_path(self) -> None:
        """Test simple path conversion."""
        nid = node_id_from_path(Path("src/sunwell/naaru/harmonic.py"), Path("src"))
        assert nid == "sunwell.naaru.harmonic"

    def test_init_file(self) -> None:
        """Test __init__.py path."""
        nid = node_id_from_path(Path("src/sunwell/__init__.py"), Path("src"))
        assert nid == "sunwell.__init__"

    def test_path_with_special_chars(self) -> None:
        """Test path with special characters."""
        nid = node_id_from_path(Path("src/my-module/file.py"), Path("src"))
        assert "my_module" in nid  # Hyphen converted to underscore

    def test_numeric_start(self) -> None:
        """Test path component starting with number."""
        nid = node_id_from_path(Path("src/123module/file.py"), Path("src"))
        assert "_123module" in nid  # Prepended underscore


def _create_sample_toc() -> ProjectToc:
    """Create a sample ToC for testing."""
    toc = ProjectToc(root_id="project")

    root = TocNode(
        node_id="project",
        title="Project",
        node_type="directory",
        summary="Root directory",
        path=".",
        children=("project.src", "project.tests"),
    )
    toc.add_node(root)

    src = TocNode(
        node_id="project.src",
        title="src",
        node_type="directory",
        summary="Source code",
        path="src",
        children=("project.src.auth", "project.src.api"),
        concepts=("core",),
    )
    toc.add_node(src)

    auth = TocNode(
        node_id="project.src.auth",
        title="auth",
        node_type="module",
        summary="Authentication module",
        path="src/auth.py",
        concepts=("auth",),
    )
    toc.add_node(auth)

    api = TocNode(
        node_id="project.src.api",
        title="api",
        node_type="module",
        summary="API endpoints",
        path="src/api.py",
        concepts=("api",),
    )
    toc.add_node(api)

    tests = TocNode(
        node_id="project.tests",
        title="tests",
        node_type="directory",
        summary="Test suite",
        path="tests",
        concepts=("test",),
    )
    toc.add_node(tests)

    return toc
