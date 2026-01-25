"""Tests for Project Intent Analyzer (RFC-079)."""

from pathlib import Path

from sunwell.knowledge.project import (
    WORKSPACE_PRIMARIES,
    DevCommand,
    GitStatus,
    InferredGoal,
    PipelineStep,
    Prerequisite,
    ProjectAnalysis,
    ProjectType,
    SuggestedAction,
    detect_sub_projects,
    gather_project_signals,
    is_monorepo,
)


class TestProjectSignals:
    """Test signal gathering."""

    def test_gather_project_signals_basic(self, tmp_path: Path) -> None:
        """Test basic signal gathering."""
        # Create minimal project structure
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "src").mkdir()
        (tmp_path / "README.md").write_text("# Test Project")

        signals = gather_project_signals(tmp_path)

        assert signals.has_pyproject is True
        assert signals.has_src_dir is True
        assert signals.readme_content is not None
        assert "Test Project" in signals.readme_content

    def test_gather_signals_node_project(self, tmp_path: Path) -> None:
        """Test signal gathering for Node.js project."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "node_modules").mkdir()

        signals = gather_project_signals(tmp_path)

        assert signals.has_package_json is True

    def test_gather_signals_documentation_project(self, tmp_path: Path) -> None:
        """Test signal gathering for documentation project."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "conf.py").write_text("# Sphinx config")
        for i in range(10):
            (tmp_path / f"doc{i}.md").write_text(f"# Doc {i}")

        signals = gather_project_signals(tmp_path)

        assert signals.has_docs_dir is True
        assert signals.has_sphinx_conf is True
        assert signals.markdown_count >= 10

    def test_signal_summary(self, tmp_path: Path) -> None:
        """Test signal summary generation."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "src").mkdir()

        signals = gather_project_signals(tmp_path)
        summary = signals.summary

        assert "has_pyproject" in summary
        assert "has_src_dir" in summary


class TestProjectType:
    """Test project type classification."""

    def test_workspace_primaries_mapping(self) -> None:
        """Test that all project types have workspace mappings."""
        for pt in ProjectType:
            assert pt in WORKSPACE_PRIMARIES, f"Missing workspace for {pt}"

    def test_workspace_primaries_values(self) -> None:
        """Test workspace primary values are valid primitives."""
        valid_primitives = {
            "CodeEditor",
            "ProseEditor",
            "NotebookEditor",
            "Kanban",
        }
        for pt, workspace in WORKSPACE_PRIMARIES.items():
            assert workspace in valid_primitives, f"Invalid workspace {workspace} for {pt}"


class TestProjectAnalysis:
    """Test ProjectAnalysis dataclass."""

    def test_cache_round_trip(self) -> None:
        """Test serialization and deserialization."""
        analysis = ProjectAnalysis(
            name="test-project",
            path=Path("/tmp/test"),
            project_type=ProjectType.CODE,
            project_subtype="fastapi-api",
            confidence=0.85,
            confidence_level="high",
            detection_signals=("has_pyproject", "has_src_dir"),
        )

        cache_dict = analysis.to_cache_dict()
        restored = ProjectAnalysis.from_cache(cache_dict)

        assert restored.name == analysis.name
        assert restored.project_type == analysis.project_type
        assert restored.project_subtype == analysis.project_subtype
        assert restored.confidence == analysis.confidence

    def test_cache_with_goals(self) -> None:
        """Test caching with inferred goals."""
        goals = (
            InferredGoal(
                id="goal-1",
                title="Test goal",
                description="A test goal",
                priority="high",
                confidence=0.8,
            ),
        )
        pipeline = (
            PipelineStep(
                id="goal-1",
                title="Test goal",
                status="pending",
            ),
        )

        analysis = ProjectAnalysis(
            name="test",
            path=Path("/tmp/test"),
            project_type=ProjectType.CODE,
            goals=goals,
            pipeline=pipeline,
        )

        cache_dict = analysis.to_cache_dict()
        restored = ProjectAnalysis.from_cache(cache_dict)

        assert len(restored.goals) == 1
        assert restored.goals[0].title == "Test goal"
        assert len(restored.pipeline) == 1

    def test_cache_with_dev_command(self) -> None:
        """Test caching with dev command."""
        dev_cmd = DevCommand(
            command="npm run dev",
            description="Start dev server",
            prerequisites=(
                Prerequisite(
                    command="npm install",
                    description="Install deps",
                    check_command="test -d node_modules",
                ),
            ),
            expected_url="http://localhost:5173",
        )

        analysis = ProjectAnalysis(
            name="test",
            path=Path("/tmp/test"),
            project_type=ProjectType.CODE,
            dev_command=dev_cmd,
        )

        cache_dict = analysis.to_cache_dict()
        restored = ProjectAnalysis.from_cache(cache_dict)

        assert restored.dev_command is not None
        assert restored.dev_command.command == "npm run dev"
        assert len(restored.dev_command.prerequisites) == 1


class TestMonorepoDetection:
    """Test monorepo detection."""

    def test_is_monorepo_pnpm(self, tmp_path: Path) -> None:
        """Test pnpm workspace detection."""
        (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'")

        assert is_monorepo(tmp_path) is True

    def test_is_monorepo_packages_dir(self, tmp_path: Path) -> None:
        """Test packages directory detection."""
        (tmp_path / "packages").mkdir()

        assert is_monorepo(tmp_path) is True

    def test_is_monorepo_npm_workspaces(self, tmp_path: Path) -> None:
        """Test npm workspaces detection."""
        (tmp_path / "package.json").write_text('{"workspaces": ["packages/*"]}')

        assert is_monorepo(tmp_path) is True

    def test_is_not_monorepo(self, tmp_path: Path) -> None:
        """Test non-monorepo project."""
        (tmp_path / "package.json").write_text('{"name": "simple-app"}')

        assert is_monorepo(tmp_path) is False

    def test_detect_sub_projects_npm(self, tmp_path: Path) -> None:
        """Test sub-project detection for npm workspaces."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()

        web_pkg = packages_dir / "web"
        web_pkg.mkdir()
        (web_pkg / "package.json").write_text('{"name": "@monorepo/web"}')

        api_pkg = packages_dir / "api"
        api_pkg.mkdir()
        (api_pkg / "package.json").write_text('{"name": "@monorepo/api"}')

        sub_projects = detect_sub_projects(tmp_path)

        assert len(sub_projects) == 2
        names = {sp.name for sp in sub_projects}
        assert "web" in names
        assert "api" in names


class TestSuggestedAction:
    """Test suggested action types."""

    def test_suggested_action_types(self) -> None:
        """Test all suggested action types are valid."""
        valid_types = {"execute_goal", "continue_work", "start_server", "review", "add_goal"}

        for action_type in valid_types:
            action = SuggestedAction(
                action_type=action_type,  # type: ignore[arg-type]
                description="Test action",
            )
            assert action.action_type == action_type


class TestGitStatus:
    """Test GitStatus dataclass."""

    def test_git_status_defaults(self) -> None:
        """Test default values."""
        status = GitStatus()

        assert status.branch == "unknown"
        assert status.commit_count == 0
        assert status.uncommitted_changes is False
        assert status.recent_commits == ()
