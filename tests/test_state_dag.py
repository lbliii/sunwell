"""Tests for State DAG scanning (RFC-100 Phase 0).

Tests the StateDagBuilder, CodeScanner, DocsScanner, and related components.
"""

from datetime import datetime
from pathlib import Path

import pytest

from sunwell.knowledge.analysis import StateDag, StateDagBuilder, StateDagNode, scan_project
from sunwell.knowledge.analysis.scanners.code import CodeScanner
from sunwell.knowledge.analysis.scanners.docs import DocsScanner
from sunwell.knowledge.analysis.state_dag import HealthProbeResult


class TestStateDagNode:
    """Tests for StateDagNode dataclass."""

    def test_confidence_band_high(self) -> None:
        """Health score 0.9+ maps to 'high' band."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.95,
            health_probes=(),
        )
        assert node.confidence_band == "high"

    def test_confidence_band_moderate(self) -> None:
        """Health score 0.7-0.89 maps to 'moderate' band."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.75,
            health_probes=(),
        )
        assert node.confidence_band == "moderate"

    def test_confidence_band_low(self) -> None:
        """Health score 0.5-0.69 maps to 'low' band."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.55,
            health_probes=(),
        )
        assert node.confidence_band == "low"

    def test_confidence_band_uncertain(self) -> None:
        """Health score <0.5 maps to 'uncertain' band."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.3,
            health_probes=(),
        )
        assert node.confidence_band == "uncertain"


class TestStateDag:
    """Tests for StateDag dataclass."""

    def test_overall_health_empty(self) -> None:
        """Empty DAG should have 100% health."""
        dag = StateDag(root=Path("/tmp"), nodes=[], edges=[])
        assert dag.overall_health == 1.0

    def test_overall_health_single_node(self) -> None:
        """Single node should determine overall health."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.8,
            health_probes=(),
        )
        dag = StateDag(root=Path("/tmp"), nodes=[node], edges=[])
        assert dag.overall_health == 0.8

    def test_overall_health_multiple_nodes(self) -> None:
        """Multiple nodes should average their health scores."""
        nodes = [
            StateDagNode(
                id=f"test-{i}",
                path=Path(f"/tmp/test_{i}.py"),
                artifact_type="module",
                title=f"Test {i}",
                health_score=score,
                health_probes=(),
            )
            for i, score in enumerate([1.0, 0.8, 0.6])
        ]
        dag = StateDag(root=Path("/tmp"), nodes=nodes, edges=[])
        assert abs(dag.overall_health - 0.8) < 0.01  # (1.0 + 0.8 + 0.6) / 3

    def test_unhealthy_nodes(self) -> None:
        """Should return nodes with health < 0.7."""
        nodes = [
            StateDagNode(
                id=f"test-{i}",
                path=Path(f"/tmp/test_{i}.py"),
                artifact_type="module",
                title=f"Test {i}",
                health_score=score,
                health_probes=(),
            )
            for i, score in enumerate([0.9, 0.6, 0.5])
        ]
        dag = StateDag(root=Path("/tmp"), nodes=nodes, edges=[])
        assert len(dag.unhealthy_nodes) == 2
        assert all(n.health_score < 0.7 for n in dag.unhealthy_nodes)

    def test_critical_nodes(self) -> None:
        """Should return nodes with health < 0.5."""
        nodes = [
            StateDagNode(
                id=f"test-{i}",
                path=Path(f"/tmp/test_{i}.py"),
                artifact_type="module",
                title=f"Test {i}",
                health_score=score,
                health_probes=(),
            )
            for i, score in enumerate([0.9, 0.6, 0.3])
        ]
        dag = StateDag(root=Path("/tmp"), nodes=nodes, edges=[])
        assert len(dag.critical_nodes) == 1
        assert dag.critical_nodes[0].health_score == 0.3

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        node = StateDagNode(
            id="test",
            path=Path("/tmp/test.py"),
            artifact_type="module",
            title="Test",
            health_score=0.9,
            health_probes=(
                HealthProbeResult(probe_name="test_probe", score=0.9, issues=()),
            ),
            last_modified=datetime(2026, 1, 22, 12, 0, 0),
            line_count=100,
        )
        dag = StateDag(root=Path("/tmp"), nodes=[node], edges=[])

        result = dag.to_dict()

        assert result["root"] == "/tmp"
        assert result["node_count"] == 1
        assert result["edge_count"] == 0
        assert result["overall_health"] == 0.9
        assert result["nodes"][0]["title"] == "Test"
        assert result["nodes"][0]["confidence_band"] == "high"

    def test_to_json(self) -> None:
        """Should serialize to JSON string."""
        dag = StateDag(root=Path("/tmp"), nodes=[], edges=[])
        json_str = dag.to_json()
        assert '"root": "/tmp"' in json_str


class TestCodeScanner:
    """Tests for CodeScanner."""

    @pytest.fixture
    def scanner(self) -> CodeScanner:
        """Create a code scanner instance."""
        return CodeScanner()

    def test_should_skip_venv(self, scanner: CodeScanner) -> None:
        """Should skip .venv directories."""
        assert scanner._should_skip(Path("/project/.venv/lib/package.py"))
        assert scanner._should_skip(Path("/project/.venv-ft/lib/package.py"))
        assert scanner._should_skip(Path("/project/venv/lib/package.py"))
        assert scanner._should_skip(Path("/project/venv312/lib/package.py"))

    def test_should_skip_common_dirs(self, scanner: CodeScanner) -> None:
        """Should skip common build/cache directories."""
        assert scanner._should_skip(Path("/project/.git/objects/pack.py"))
        assert scanner._should_skip(Path("/project/__pycache__/module.pyc"))
        assert scanner._should_skip(Path("/project/node_modules/pkg/index.js"))
        assert scanner._should_skip(Path("/project/dist/bundle.js"))
        assert scanner._should_skip(Path("/project/.pytest_cache/v/cache.py"))

    def test_should_not_skip_source(self, scanner: CodeScanner) -> None:
        """Should not skip source directories."""
        assert not scanner._should_skip(Path("/project/src/module.py"))
        assert not scanner._should_skip(Path("/project/lib/utils.py"))
        assert not scanner._should_skip(Path("/project/tests/test_module.py"))

    def test_detect_project_type_python(self, scanner: CodeScanner, tmp_path: Path) -> None:
        """Should detect Python projects."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert scanner._detect_project_type(tmp_path) == "python"

    def test_detect_project_type_javascript(self, scanner: CodeScanner, tmp_path: Path) -> None:
        """Should detect JavaScript projects."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert scanner._detect_project_type(tmp_path) == "javascript"

    def test_detect_project_type_rust(self, scanner: CodeScanner, tmp_path: Path) -> None:
        """Should detect Rust projects."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        assert scanner._detect_project_type(tmp_path) == "rust"

    def test_get_module_title(self, scanner: CodeScanner) -> None:
        """Should generate readable titles from module names."""
        assert scanner._get_module_title(Path("src/user_auth.py"), "python") == "User Auth"
        assert scanner._get_module_title(Path("src/__init__.py"), "python") == "src (package)"
        assert scanner._get_module_title(Path("src/__main__.py"), "python") == "src (main)"

    def test_get_artifact_type(self, scanner: CodeScanner) -> None:
        """Should determine artifact types correctly."""
        assert scanner._get_artifact_type(Path("tests/test_module.py"), "python") == "test"
        assert scanner._get_artifact_type(Path("src/config.py"), "python") == "config"
        assert scanner._get_artifact_type(Path("src/main.py"), "python") == "entry"
        assert scanner._get_artifact_type(Path("src/utils.py"), "python") == "module"

    def test_extract_python_imports(self, scanner: CodeScanner, tmp_path: Path) -> None:
        """Should extract Python imports correctly."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
import os
import json
from pathlib import Path
from typing import Any
from myproject.utils import helper
""")
        imports = scanner._extract_python_imports(py_file)
        assert "os" in imports
        assert "json" in imports
        assert "pathlib" in imports
        assert "typing" in imports
        assert "myproject" in imports


class TestDocsScanner:
    """Tests for DocsScanner."""

    @pytest.fixture
    def scanner(self) -> DocsScanner:
        """Create a docs scanner instance."""
        return DocsScanner()

    def test_should_skip_venv(self, scanner: DocsScanner) -> None:
        """Should skip .venv directories."""
        assert scanner._should_skip(Path("/project/.venv/docs/readme.md"))
        assert scanner._should_skip(Path("/project/.venv-ft/readme.md"))

    def test_should_skip_build(self, scanner: DocsScanner) -> None:
        """Should skip build output directories."""
        assert scanner._should_skip(Path("/project/_build/html/index.html"))
        assert scanner._should_skip(Path("/project/site/index.html"))

    def test_should_not_skip_docs(self, scanner: DocsScanner) -> None:
        """Should not skip documentation directories."""
        assert not scanner._should_skip(Path("/project/docs/index.md"))
        assert not scanner._should_skip(Path("/project/content/guide.rst"))


class TestStateDagBuilder:
    """Tests for StateDagBuilder."""

    @pytest.mark.asyncio
    async def test_build_python_project(self, tmp_path: Path) -> None:
        """Should build a State DAG for a Python project."""
        # Create a minimal Python project
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("")
        (tmp_path / "src" / "main.py").write_text("def main():\n    pass")

        builder = StateDagBuilder(root=tmp_path)
        dag = await builder.build()

        assert dag.root == tmp_path
        assert len(dag.nodes) >= 2  # At least __init__.py and main.py
        assert isinstance(dag.overall_health, float)
        assert 0.0 <= dag.overall_health <= 1.0

    @pytest.mark.asyncio
    async def test_build_docs_project(self, tmp_path: Path) -> None:
        """Should build a State DAG for a docs project."""
        # Create a minimal Sphinx project
        (tmp_path / "conf.py").write_text("project = 'Test'")
        (tmp_path / "index.rst").write_text("Title\n=====\n\nContent here.")
        (tmp_path / "guide.md").write_text("# Guide\n\nSome content.")

        builder = StateDagBuilder(root=tmp_path)
        dag = await builder.build()

        assert dag.root == tmp_path
        assert len(dag.nodes) >= 2  # At least conf.py or index/guide
        assert isinstance(dag.overall_health, float)

    @pytest.mark.asyncio
    async def test_is_docs_project(self, tmp_path: Path) -> None:
        """Should detect documentation projects correctly."""
        # Sphinx project
        sphinx_dir = tmp_path / "sphinx"
        sphinx_dir.mkdir()
        (sphinx_dir / "conf.py").write_text("project = 'Test'")

        builder = StateDagBuilder(root=sphinx_dir)
        assert builder._is_docs_project()

        # MkDocs project
        mkdocs_dir = tmp_path / "mkdocs"
        mkdocs_dir.mkdir()
        (mkdocs_dir / "mkdocs.yml").write_text("site_name: Test")

        builder = StateDagBuilder(root=mkdocs_dir)
        assert builder._is_docs_project()

        # Python project (not docs)
        python_dir = tmp_path / "python"
        python_dir.mkdir()
        (python_dir / "pyproject.toml").write_text("[project]")
        (python_dir / "main.py").write_text("print('hello')")

        builder = StateDagBuilder(root=python_dir)
        assert not builder._is_docs_project()


class TestScanProject:
    """Tests for the scan_project convenience function."""

    @pytest.mark.asyncio
    async def test_scan_project_function(self, tmp_path: Path) -> None:
        """Should scan a project and return a State DAG."""
        # Create a minimal project
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "main.py").write_text("print('hello')")

        dag = await scan_project(tmp_path)

        assert isinstance(dag, StateDag)
        assert dag.root == tmp_path
        assert len(dag.nodes) >= 1


class TestHealthProbeResult:
    """Tests for HealthProbeResult dataclass."""

    def test_create_health_probe_result(self) -> None:
        """Should create a health probe result."""
        result = HealthProbeResult(
            probe_name="test_probe",
            score=0.85,
            issues=("Issue 1", "Issue 2"),
            metadata={"extra": "data"},
        )

        assert result.probe_name == "test_probe"
        assert result.score == 0.85
        assert len(result.issues) == 2
        assert result.metadata["extra"] == "data"

    def test_frozen_dataclass(self) -> None:
        """HealthProbeResult should be immutable."""
        result = HealthProbeResult(
            probe_name="test",
            score=0.9,
            issues=(),
        )
        with pytest.raises(AttributeError):
            result.score = 0.5  # type: ignore
