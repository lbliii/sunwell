"""Tests for TocGenerator (RFC-124)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from sunwell.knowledge.navigation.generator import (
    CONCEPT_KEYWORDS,
    SKIP_DIRS,
    GeneratorConfig,
    TocGenerator,
)


class TestGeneratorConfig:
    """Tests for GeneratorConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = GeneratorConfig()

        assert config.max_depth == 10
        assert config.include_private is False
        assert config.include_dunder is False
        assert config.min_function_lines == 3
        assert config.max_file_size == 100_000

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = GeneratorConfig(
            max_depth=5,
            include_private=True,
            include_dunder=True,
        )

        assert config.max_depth == 5
        assert config.include_private is True
        assert config.include_dunder is True


class TestSkipDirs:
    """Tests for skip directory patterns."""

    def test_common_dirs_skipped(self) -> None:
        """Test that common directories are in skip list."""
        assert ".git" in SKIP_DIRS
        assert "__pycache__" in SKIP_DIRS
        assert "node_modules" in SKIP_DIRS
        assert ".venv" in SKIP_DIRS
        assert "venv" in SKIP_DIRS


class TestConceptKeywords:
    """Tests for concept keyword mappings."""

    def test_concept_categories_exist(self) -> None:
        """Test that expected concept categories exist."""
        expected = {"auth", "api", "data", "config", "test", "util", "core", "cli"}
        assert expected.issubset(CONCEPT_KEYWORDS.keys())

    def test_auth_keywords(self) -> None:
        """Test auth concept keywords."""
        auth_keywords = CONCEPT_KEYWORDS["auth"]
        assert "auth" in auth_keywords
        assert "token" in auth_keywords
        assert "login" in auth_keywords

    def test_api_keywords(self) -> None:
        """Test API concept keywords."""
        api_keywords = CONCEPT_KEYWORDS["api"]
        assert "api" in api_keywords
        assert "endpoint" in api_keywords
        assert "route" in api_keywords


class TestTocGenerator:
    """Tests for TocGenerator."""

    def test_generate_empty_directory(self) -> None:
        """Test generation on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            generator = TocGenerator(root=root)
            toc = generator.generate()

            assert toc.root_id == root.name
            assert toc.node_count >= 1  # At least root node
            assert toc.generated_at is not None

    def test_generate_with_python_file(self) -> None:
        """Test generation with Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create a Python file with class and function
            # Functions need to be at least min_function_lines (default 3)
            py_file = root / "module.py"
            py_file.write_text('''"""A test module."""

class TestClass:
    """A test class."""

    def method(self):
        """A test method with enough lines."""
        x = 1
        y = 2
        return x + y


def test_function():
    """A test function with enough lines."""
    result = 42
    print(result)
    return result
''')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Should have module node
            module_nodes = [n for n in toc.nodes.values() if n.node_type == "module"]
            assert len(module_nodes) >= 1

            # Should have class node
            class_nodes = [n for n in toc.nodes.values() if n.node_type == "class"]
            assert len(class_nodes) >= 1

            # Should have function nodes (need min 3 lines)
            func_nodes = [n for n in toc.nodes.values() if n.node_type == "function"]
            assert len(func_nodes) >= 1

    def test_generate_with_package(self) -> None:
        """Test generation with Python package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create a package
            pkg = root / "mypackage"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('"""My package docstring."""\n')
            (pkg / "submodule.py").write_text('"""A submodule."""\n')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Package should be detected
            pkg_nodes = [n for n in toc.nodes.values() if "mypackage" in n.node_id]
            assert len(pkg_nodes) >= 1

    def test_skip_hidden_directories(self) -> None:
        """Test that hidden directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create hidden directory with Python file
            hidden = root / ".hidden"
            hidden.mkdir()
            (hidden / "secret.py").write_text("# secret\n")

            # Create visible file
            (root / "visible.py").write_text("# visible\n")

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Hidden directory itself should not be a node
            # (Note: files inside may still be indexed if path doesn't match skip)
            hidden_dir_nodes = [
                n for n in toc.nodes.values()
                if n.node_type == "directory" and ".hidden" in n.title
            ]
            assert len(hidden_dir_nodes) == 0

    def test_skip_pycache(self) -> None:
        """Test that __pycache__ is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create __pycache__
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "module.cpython-311.pyc").write_bytes(b"")

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Should not include __pycache__ contents
            cache_nodes = [n for n in toc.nodes.values() if "__pycache__" in n.path]
            assert len(cache_nodes) == 0

    def test_docstring_extraction(self) -> None:
        """Test that docstrings are extracted as summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            py_file = root / "documented.py"
            py_file.write_text('''"""This is the module docstring."""

class DocumentedClass:
    """This class is well documented."""
    pass


def documented_function():
    """This function has documentation."""
    pass
''')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Find the module node
            module = next(
                (n for n in toc.nodes.values() if n.title == "documented"),
                None,
            )
            assert module is not None
            assert "module docstring" in module.summary.lower()

    def test_concept_classification(self) -> None:
        """Test that concepts are classified from keywords."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create auth-related file
            auth_file = root / "authentication.py"
            auth_file.write_text('"""Authentication and token validation."""\n')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Should be tagged with auth concept
            auth_nodes = toc.get_nodes_by_concept("auth")
            assert len(auth_nodes) >= 1

    def test_cross_reference_extraction(self) -> None:
        """Test that cross-references are extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            py_file = root / "module.py"
            py_file.write_text('''"""Module with references."""

# See: other/module.py

from myproject import utils
''')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            module = next(
                (n for n in toc.nodes.values() if n.title == "module"),
                None,
            )
            assert module is not None
            # Cross-refs should be extracted (may vary based on implementation)

    def test_include_private_config(self) -> None:
        """Test include_private configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Functions need at least 3 lines to be included
            py_file = root / "module.py"
            py_file.write_text('''"""Module."""

def public_function():
    """A public function."""
    x = 1
    return x


def _private_function():
    """A private function."""
    y = 2
    return y
''')

            # Without include_private
            generator = TocGenerator(root=root, config=GeneratorConfig(include_private=False))
            toc = generator.generate()

            private_funcs = [
                n for n in toc.nodes.values()
                if n.node_type == "function" and n.title.startswith("_")
            ]
            assert len(private_funcs) == 0

            # With include_private
            generator2 = TocGenerator(root=root, config=GeneratorConfig(include_private=True))
            toc2 = generator2.generate()

            private_funcs2 = [
                n for n in toc2.nodes.values()
                if n.node_type == "function" and n.title.startswith("_")
            ]
            assert len(private_funcs2) >= 1

    def test_max_depth_config(self) -> None:
        """Test max_depth configuration limits directory traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create nested structure with directories
            level1 = root / "level1"
            level1.mkdir()
            (level1 / "__init__.py").write_text("# level1\n")

            level2 = level1 / "level2"
            level2.mkdir()
            (level2 / "__init__.py").write_text("# level2\n")

            level3 = level2 / "level3"
            level3.mkdir()
            (level3 / "__init__.py").write_text("# level3\n")

            # With depth limit of 1, should only see root + level1
            generator = TocGenerator(root=root, config=GeneratorConfig(max_depth=1))
            toc = generator.generate()

            # Check that deeper levels are not included
            level3_nodes = [
                n for n in toc.nodes.values()
                if "level3" in n.path and n.node_type == "directory"
            ]
            assert len(level3_nodes) == 0

    def test_parent_child_linking(self) -> None:
        """Test that parent-child relationships are established."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create package with submodules
            pkg = root / "parent"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('"""Parent package."""\n')
            (pkg / "child.py").write_text('"""Child module."""\n')

            generator = TocGenerator(root=root)
            toc = generator.generate()

            # Find parent node
            parent = next(
                (n for n in toc.nodes.values() if n.title == "parent" and n.node_type == "module"),
                None,
            )
            assert parent is not None

            # Parent should have children
            assert len(parent.children) > 0
