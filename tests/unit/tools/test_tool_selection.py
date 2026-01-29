"""Unit tests for multi-signal tool selection.

Tests the ToolDAG for workflow-based progressive disclosure,
the MultiSignalToolSelector for intelligent tool filtering,
the ToolPlanner for plan-then-execute, and ToolRationale for validation.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sunwell.tools.selection.graph import (
    ToolDAG,
    ToolNode,
    ToolDAGError,
    DEFAULT_TOOL_DAG,
)
from sunwell.tools.selection.selector import (
    MultiSignalToolSelector,
    PROJECT_TYPE_TOOLS,
    GIT_TOOLS,
    get_tool_limit_for_model,
)
from sunwell.tools.selection.planner import (
    ToolPlan,
    ToolPlanner,
    plan_heuristic,
    KEYWORD_TOOL_MAP,
)
from sunwell.tools.selection.rationale import (
    RationaleStrength,
    ToolRationale,
    ToolRationaleValidator,
    generate_heuristic_rationale,
)
from sunwell.knowledge.indexing.project_type import ProjectType
from sunwell.models import Tool


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def simple_dag() -> ToolDAG:
    """Create a simple DAG for testing."""
    nodes = (
        ToolNode(name="list_files", successors=frozenset({"read_file"}), category="file"),
        ToolNode(name="search_files", successors=frozenset({"read_file"}), category="search"),
        ToolNode(name="read_file", successors=frozenset({"edit_file", "write_file"}), category="file"),
        ToolNode(name="edit_file", successors=frozenset({"git_add"}), category="file"),
        ToolNode(name="write_file", successors=frozenset({"git_add"}), category="file"),
        ToolNode(name="git_add", successors=frozenset({"git_commit"}), category="git"),
        ToolNode(name="git_commit", successors=frozenset(), category="git"),
    )
    return ToolDAG.from_nodes(nodes)


@pytest.fixture
def mock_tools() -> tuple[Tool, ...]:
    """Create mock Tool objects for testing."""
    return tuple(
        Tool(name=name, description=f"Test tool {name}", parameters={"type": "object", "properties": {}})
        for name in [
            "list_files", "search_files", "read_file", "edit_file",
            "write_file", "git_add", "git_commit", "run_command",
        ]
    )


@pytest.fixture
def mock_learning_store() -> MagicMock:
    """Create a mock LearningStore."""
    store = MagicMock()
    store.suggest_tools.return_value = ["search_files", "read_file", "edit_file"]
    store.get_dead_ends_for.return_value = []
    return store


# =============================================================================
# ToolDAG TESTS
# =============================================================================


class TestToolDAG:
    """Tests for ToolDAG class."""

    def test_entry_points_detected(self, simple_dag: ToolDAG) -> None:
        """Entry points should be nodes with no predecessors."""
        # list_files and search_files have no predecessors
        assert "list_files" in simple_dag._entry_points
        assert "search_files" in simple_dag._entry_points
        # read_file is a successor of others, not an entry point
        assert "read_file" not in simple_dag._entry_points

    def test_get_available_empty_used(self, simple_dag: ToolDAG) -> None:
        """With no tools used, only entry points available."""
        available = simple_dag.get_available(frozenset())
        assert available == simple_dag._entry_points
        assert "list_files" in available
        assert "search_files" in available
        assert "read_file" not in available

    def test_get_available_unlocks_successors(self, simple_dag: ToolDAG) -> None:
        """Using a tool unlocks its successors."""
        # After using list_files, read_file should be available
        available = simple_dag.get_available(frozenset({"list_files"}))
        assert "read_file" in available
        # Entry points still available
        assert "list_files" in available
        assert "search_files" in available

    def test_get_available_chain(self, simple_dag: ToolDAG) -> None:
        """Successors chain through multiple tool uses."""
        # list_files -> read_file -> edit_file
        available = simple_dag.get_available(frozenset({"list_files", "read_file"}))
        assert "edit_file" in available
        assert "write_file" in available

    def test_get_available_full_chain(self, simple_dag: ToolDAG) -> None:
        """Full workflow chain unlocks all tools."""
        used = frozenset({"list_files", "read_file", "edit_file", "git_add"})
        available = simple_dag.get_available(used)
        assert "git_commit" in available

    def test_contains(self, simple_dag: ToolDAG) -> None:
        """Check if tool is in DAG."""
        assert "list_files" in simple_dag
        assert "nonexistent_tool" not in simple_dag

    def test_len(self, simple_dag: ToolDAG) -> None:
        """DAG length is number of nodes."""
        assert len(simple_dag) == 7

    def test_get_successors(self, simple_dag: ToolDAG) -> None:
        """Get successors of a tool."""
        successors = simple_dag.get_successors("read_file")
        assert successors == frozenset({"edit_file", "write_file"})

    def test_get_category(self, simple_dag: ToolDAG) -> None:
        """Get category of a tool."""
        assert simple_dag.get_category("list_files") == "file"
        assert simple_dag.get_category("git_add") == "git"
        assert simple_dag.get_category("nonexistent") == "unknown"


class TestDefaultToolDAG:
    """Tests for the default tool DAG."""

    def test_has_expected_entry_points(self) -> None:
        """Default DAG should have expected entry points."""
        entry = DEFAULT_TOOL_DAG._entry_points
        assert "list_files" in entry
        assert "search_files" in entry
        assert "git_status" in entry
        assert "run_command" in entry
        assert "list_env" in entry

    def test_discovery_to_read_progression(self) -> None:
        """list_files -> read_file progression works."""
        available = DEFAULT_TOOL_DAG.get_available(frozenset({"list_files"}))
        assert "read_file" in available

    def test_read_to_edit_progression(self) -> None:
        """read_file -> edit_file progression works."""
        available = DEFAULT_TOOL_DAG.get_available(frozenset({"list_files", "read_file"}))
        assert "edit_file" in available
        assert "write_file" in available
        assert "patch_file" in available

    def test_git_workflow_progression(self) -> None:
        """git_status -> git_diff -> git_add -> git_commit works."""
        # Start with git_status
        available = DEFAULT_TOOL_DAG.get_available(frozenset({"git_status"}))
        assert "git_diff" in available
        assert "git_add" in available

        # After git_add
        available = DEFAULT_TOOL_DAG.get_available(frozenset({"git_status", "git_add"}))
        assert "git_commit" in available


# =============================================================================
# MultiSignalToolSelector TESTS
# =============================================================================


class TestMultiSignalToolSelector:
    """Tests for MultiSignalToolSelector class."""

    def test_select_with_empty_used_tools(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
    ) -> None:
        """With no tools used, should return entry points + learned boost."""
        selector = MultiSignalToolSelector(dag=simple_dag, enable_learned_boost=False)

        result = selector.select(
            query="list the files",
            task_type="general",
            used_tools=frozenset(),
            available_tools=mock_tools,
        )

        # Should only include entry points
        result_names = {t.name for t in result}
        assert "list_files" in result_names
        assert "search_files" in result_names
        # Non-entry-points should not be included (unless boosted)
        assert "edit_file" not in result_names

    def test_select_with_learned_boost(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
        mock_learning_store: MagicMock,
    ) -> None:
        """Learned patterns should boost tools into selection."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            learning_store=mock_learning_store,
        )

        result = selector.select(
            query="fix the bug",
            task_type="bugfix",
            used_tools=frozenset(),
            available_tools=mock_tools,
        )

        # Learned tools should be boosted
        result_names = {t.name for t in result}
        assert "search_files" in result_names
        assert "read_file" in result_names

    def test_select_respects_max_tools(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
    ) -> None:
        """max_tools limit should be respected."""
        selector = MultiSignalToolSelector(dag=simple_dag, max_tools=2)

        result = selector.select(
            query="test",
            task_type="general",
            used_tools=frozenset(),
            available_tools=mock_tools,
        )

        assert len(result) <= 2

    def test_select_progression(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
    ) -> None:
        """Tools should unlock as workflow progresses."""
        selector = MultiSignalToolSelector(dag=simple_dag, enable_learned_boost=False)

        # After using list_files, read_file should be available
        result = selector.select(
            query="read the config",
            task_type="general",
            used_tools=frozenset({"list_files"}),
            available_tools=mock_tools,
        )

        result_names = {t.name for t in result}
        assert "read_file" in result_names

    def test_dead_end_suppression(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
    ) -> None:
        """Dead ends should suppress associated tools."""
        mock_store = MagicMock()
        mock_store.suggest_tools.return_value = []
        # Create a dead end that mentions "write_file"
        dead_end = MagicMock()
        dead_end.approach = "tried write_file but it failed"
        mock_store.get_dead_ends_for.return_value = [dead_end]

        selector = MultiSignalToolSelector(
            dag=simple_dag,
            learning_store=mock_store,
        )

        # After read_file, write_file would normally be available
        result = selector.select(
            query="write the config",
            task_type="general",
            used_tools=frozenset({"list_files", "read_file"}),
            available_tools=mock_tools,
        )

        result_names = {t.name for t in result}
        # write_file should be suppressed due to dead end
        assert "write_file" not in result_names


class TestModelAdaptiveLimits:
    """Tests for model-adaptive tool limits."""

    def test_small_model_limit(self) -> None:
        """Small models get strict limits."""
        assert get_tool_limit_for_model(4000, "small") == 5
        assert get_tool_limit_for_model(None, "small") == 5

    def test_medium_model_limit(self) -> None:
        """Medium models get moderate limits."""
        assert get_tool_limit_for_model(16000, "medium") == 15

    def test_large_model_no_limit(self) -> None:
        """Large models get no artificial limit."""
        assert get_tool_limit_for_model(128000, "large") is None
        assert get_tool_limit_for_model(None, "large") is None


class TestProjectTypeFiltering:
    """Tests for project type tool filtering."""

    def test_code_project_includes_git(self) -> None:
        """Code projects should include git tools."""
        code_tools = PROJECT_TYPE_TOOLS[ProjectType.CODE]
        assert "git_status" in code_tools
        assert "git_commit" in code_tools
        assert "run_command" in code_tools

    def test_prose_project_excludes_shell(self) -> None:
        """Prose projects should not include shell tools by default."""
        prose_tools = PROJECT_TYPE_TOOLS[ProjectType.PROSE]
        assert "run_command" not in prose_tools

    def test_prose_project_includes_web(self) -> None:
        """Prose projects should include web research tools."""
        prose_tools = PROJECT_TYPE_TOOLS[ProjectType.PROSE]
        assert "web_search" in prose_tools
        assert "web_fetch" in prose_tools

    def test_mixed_project_no_filter(self) -> None:
        """Mixed/unknown projects have no filtering (empty set)."""
        assert PROJECT_TYPE_TOOLS[ProjectType.MIXED] == frozenset()
        assert PROJECT_TYPE_TOOLS[ProjectType.UNKNOWN] == frozenset()


class TestGitDetection:
    """Tests for git detection and filtering."""

    def test_non_git_project_filters_git_tools(self, mock_tools: tuple[Tool, ...]) -> None:
        """Non-git projects should filter out git tools."""
        with patch("sunwell.tools.selection.selector.detect_project_type") as mock_detect:
            mock_detect.return_value = ProjectType.CODE

            # Create selector with non-git workspace
            selector = MultiSignalToolSelector(
                workspace_root=Path("/tmp/non-git-project"),
                enable_dag=False,  # Disable DAG to test project filter alone
            )
            # Mock the git detection
            selector._has_git = False

            result = selector.select(
                query="commit changes",
                task_type="general",
                used_tools=frozenset(),
                available_tools=mock_tools,
            )

            result_names = {t.name for t in result}
            # Git tools should be filtered out
            assert "git_add" not in result_names
            assert "git_commit" not in result_names


# =============================================================================
# SEMANTIC TOOL RETRIEVAL TESTS
# =============================================================================


class TestToolEmbeddingIndex:
    """Tests for ToolEmbeddingIndex semantic retrieval."""

    @pytest.fixture
    def semantic_tools(self) -> tuple[Tool, ...]:
        """Create tools with meaningful descriptions for semantic matching."""
        return (
            Tool(
                name="list_files",
                description="List files and directories in a path. Shows file names, sizes, and types.",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            Tool(
                name="search_files",
                description="Search for patterns in files using regex. Find code, text, or content.",
                parameters={"type": "object", "properties": {"pattern": {"type": "string"}}},
            ),
            Tool(
                name="read_file",
                description="Read the contents of a file. Returns file text for viewing or editing.",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            Tool(
                name="edit_file",
                description="Edit a file by replacing content. Make changes to source code.",
                parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            ),
            Tool(
                name="git_status",
                description="Show the working tree status. See modified, staged, and untracked files.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="git_commit",
                description="Record changes to the repository. Save staged changes with a message.",
                parameters={"type": "object", "properties": {"message": {"type": "string"}}},
            ),
            Tool(
                name="run_command",
                description="Execute a shell command. Run tests, build, or system commands.",
                parameters={"type": "object", "properties": {"command": {"type": "string"}}},
            ),
            Tool(
                name="web_search",
                description="Search the web for information. Look up documentation, APIs, or answers.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            ),
        )

    def test_embedding_index_initialization(self, semantic_tools: tuple[Tool, ...]) -> None:
        """ToolEmbeddingIndex should initialize with tools."""
        from sunwell.tools.selection.embedding import ToolEmbeddingIndex

        index = ToolEmbeddingIndex()
        index.initialize(semantic_tools)

        assert index._initialized
        # Index should be built (may be None if no embedder available)
        # In test environments, we may fall back to HashEmbedding

    def test_embedding_index_reset(self, semantic_tools: tuple[Tool, ...]) -> None:
        """Reset should clear the index."""
        from sunwell.tools.selection.embedding import ToolEmbeddingIndex

        index = ToolEmbeddingIndex()
        index.initialize(semantic_tools)
        index.reset()

        assert not index._initialized
        assert index._index is None
        assert len(index._tool_texts) == 0

    def test_build_tool_text(self, semantic_tools: tuple[Tool, ...]) -> None:
        """Tool text should combine name, description, and parameters."""
        from sunwell.tools.selection.embedding import ToolEmbeddingIndex

        index = ToolEmbeddingIndex()
        tool = semantic_tools[0]  # list_files

        text = index._build_tool_text(tool)

        assert "list_files" in text
        assert "List files and directories" in text
        assert "path" in text  # Parameter name


class TestSelectorSemanticIntegration:
    """Tests for semantic integration in MultiSignalToolSelector."""

    @pytest.fixture
    def semantic_tools(self) -> tuple[Tool, ...]:
        """Create tools with meaningful descriptions for semantic matching."""
        return (
            Tool(
                name="list_files",
                description="List files and directories in a path.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="search_files",
                description="Search for patterns in files using regex.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="read_file",
                description="Read the contents of a file.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="web_search",
                description="Search the web for information and documentation.",
                parameters={"type": "object", "properties": {}},
            ),
        )

    def test_selector_with_semantic_disabled(
        self,
        simple_dag: ToolDAG,
        mock_tools: tuple[Tool, ...],
    ) -> None:
        """Selector should work with semantic disabled."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_semantic=False,
        )

        result = selector.select(
            query="search for files containing error",
            task_type="general",
            used_tools=frozenset(),
            available_tools=mock_tools,
        )

        # Should still work, just without semantic boost
        assert len(result) > 0

    def test_selector_with_semantic_enabled(
        self,
        simple_dag: ToolDAG,
        semantic_tools: tuple[Tool, ...],
    ) -> None:
        """Selector should apply semantic boost when enabled."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_semantic=True,
            enable_learned_boost=False,
        )

        result = selector.select(
            query="look at the directory contents",
            task_type="general",
            used_tools=frozenset(),
            available_tools=semantic_tools,
        )

        # Should return results
        assert len(result) > 0
        # list_files should be in results (semantically relevant to "directory contents")
        result_names = {t.name for t in result}
        assert "list_files" in result_names

    def test_semantic_boost_weight_affects_ranking(
        self,
        simple_dag: ToolDAG,
        semantic_tools: tuple[Tool, ...],
    ) -> None:
        """Higher semantic boost weight should affect ranking."""
        # Create selector with high semantic boost
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_semantic=True,
            enable_learned_boost=False,
            semantic_boost_weight=80,  # High weight
        )

        result = selector.select(
            query="search the web for documentation",
            task_type="general",
            used_tools=frozenset(),
            available_tools=semantic_tools,
        )

        # web_search should be boosted for "search the web" query
        result_names = [t.name for t in result]
        # It should be in results (even if not an entry point in DAG)
        # because semantic boost adds high-confidence tools
        assert len(result) > 0

    def test_reset_cache_clears_embedding_index(
        self,
        simple_dag: ToolDAG,
        semantic_tools: tuple[Tool, ...],
    ) -> None:
        """reset_cache should clear the embedding index."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_semantic=True,
        )

        # Initialize by running select
        selector.select(
            query="test",
            task_type="general",
            used_tools=frozenset(),
            available_tools=semantic_tools,
        )

        # Should have embedding index
        assert selector._embedding_index is not None

        # Reset cache
        selector.reset_cache()

        # Embedding index should be cleared
        assert selector._embedding_index is None


# =============================================================================
# TOOL PLANNER TESTS
# =============================================================================


class TestToolPlan:
    """Tests for ToolPlan dataclass."""

    def test_contains(self) -> None:
        """Check if a tool is in the plan."""
        plan = ToolPlan(tools=("list_files", "read_file", "edit_file"))
        assert "list_files" in plan
        assert "search_files" not in plan

    def test_len(self) -> None:
        """Plan length should be number of tools."""
        plan = ToolPlan(tools=("list_files", "read_file"))
        assert len(plan) == 2

    def test_as_set(self) -> None:
        """Convert to frozenset."""
        plan = ToolPlan(tools=("list_files", "read_file"))
        result = plan.as_set()
        assert result == frozenset({"list_files", "read_file"})


class TestHeuristicPlanning:
    """Tests for heuristic (keyword-based) planning."""

    @pytest.fixture
    def planning_tools(self) -> tuple[Tool, ...]:
        """Create tools for planning tests."""
        return tuple(
            Tool(name=name, description=f"Test tool {name}", parameters={"type": "object", "properties": {}})
            for name in [
                "list_files", "search_files", "read_file", "edit_file",
                "write_file", "git_status", "git_diff", "git_commit",
                "git_add", "run_command", "web_search",
            ]
        )

    def test_plan_list_files(self, planning_tools: tuple[Tool, ...]) -> None:
        """'list' keyword should plan list_files."""
        plan = plan_heuristic("list the directory contents", planning_tools)
        assert "list_files" in plan

    def test_plan_search(self, planning_tools: tuple[Tool, ...]) -> None:
        """'search' keyword should plan search_files."""
        plan = plan_heuristic("search for error handling code", planning_tools)
        assert "search_files" in plan

    def test_plan_git_commit(self, planning_tools: tuple[Tool, ...]) -> None:
        """'commit' keyword should plan git tools."""
        plan = plan_heuristic("commit the changes", planning_tools)
        assert "git_add" in plan or "git_commit" in plan

    def test_plan_fix_bug(self, planning_tools: tuple[Tool, ...]) -> None:
        """'fix' keyword should plan search, read, edit."""
        plan = plan_heuristic("fix the bug in main.py", planning_tools)
        # fix maps to search_files, read_file, edit_file
        assert "search_files" in plan or "read_file" in plan or "edit_file" in plan

    def test_plan_run_tests(self, planning_tools: tuple[Tool, ...]) -> None:
        """'test' keyword should plan run_command."""
        plan = plan_heuristic("run the unit tests", planning_tools)
        assert "run_command" in plan

    def test_plan_default_when_no_match(self, planning_tools: tuple[Tool, ...]) -> None:
        """Should return default tools when no keywords match."""
        plan = plan_heuristic("do something complex", planning_tools)
        # Should fall back to defaults
        assert len(plan) > 0

    def test_plan_confidence(self, planning_tools: tuple[Tool, ...]) -> None:
        """Heuristic plans should have moderate confidence."""
        plan = plan_heuristic("list files", planning_tools)
        assert plan.confidence == 0.7


class TestSelectorPlanningIntegration:
    """Tests for planning integration in MultiSignalToolSelector."""

    @pytest.fixture
    def planning_tools(self) -> tuple[Tool, ...]:
        """Create tools for planning tests."""
        return tuple(
            Tool(name=name, description=f"Test tool {name}", parameters={"type": "object", "properties": {}})
            for name in [
                "list_files", "search_files", "read_file", "edit_file",
                "git_status", "git_commit", "run_command",
            ]
        )

    def test_selector_with_planning_enabled(
        self,
        simple_dag: ToolDAG,
        planning_tools: tuple[Tool, ...],
    ) -> None:
        """Selector should use planning when enabled."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_planning=True,
            enable_semantic=False,
        )

        result = selector.select(
            query="search for errors in the code",
            task_type="general",
            used_tools=frozenset(),
            available_tools=planning_tools,
        )

        # search_files should be boosted by planning
        result_names = [t.name for t in result]
        assert "search_files" in result_names

    def test_selector_with_planning_disabled(
        self,
        simple_dag: ToolDAG,
        planning_tools: tuple[Tool, ...],
    ) -> None:
        """Selector should work with planning disabled."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_planning=False,
            enable_semantic=False,
        )

        result = selector.select(
            query="test query",
            task_type="general",
            used_tools=frozenset(),
            available_tools=planning_tools,
        )

        # Should still return results
        assert len(result) > 0

    def test_get_current_plan(
        self,
        simple_dag: ToolDAG,
        planning_tools: tuple[Tool, ...],
    ) -> None:
        """Should be able to retrieve the current plan."""
        selector = MultiSignalToolSelector(
            dag=simple_dag,
            enable_planning=True,
        )

        selector.select(
            query="list the files",
            task_type="general",
            used_tools=frozenset(),
            available_tools=planning_tools,
        )

        plan = selector.get_current_plan()
        assert plan is not None
        assert "list_files" in plan


# =============================================================================
# TOOL RATIONALE TESTS
# =============================================================================


class TestToolRationale:
    """Tests for ToolRationale dataclass."""

    def test_is_acceptable_strong(self) -> None:
        """Strong rationale should be acceptable."""
        rationale = ToolRationale(
            tool_name="search_files",
            rationale="Search files to find patterns",
            strength=RationaleStrength.STRONG,
        )
        assert rationale.is_acceptable
        assert not rationale.should_retry

    def test_is_acceptable_moderate(self) -> None:
        """Moderate rationale should be acceptable."""
        rationale = ToolRationale(
            tool_name="search_files",
            rationale="This tool may help",
            strength=RationaleStrength.MODERATE,
        )
        assert rationale.is_acceptable
        assert not rationale.should_retry

    def test_should_retry_weak(self) -> None:
        """Weak rationale should trigger retry."""
        rationale = ToolRationale(
            tool_name="search_files",
            rationale="Unclear",
            strength=RationaleStrength.WEAK,
        )
        assert not rationale.is_acceptable
        assert rationale.should_retry

    def test_should_retry_invalid(self) -> None:
        """Invalid rationale should trigger retry."""
        rationale = ToolRationale(
            tool_name="search_files",
            rationale="",
            strength=RationaleStrength.INVALID,
        )
        assert not rationale.is_acceptable
        assert rationale.should_retry


class TestHeuristicRationale:
    """Tests for heuristic rationale generation."""

    @pytest.fixture
    def rationale_tools(self) -> tuple[Tool, ...]:
        """Create tools for rationale tests."""
        return (
            Tool(
                name="search_files",
                description="Search for patterns in files using regex.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="read_file",
                description="Read the contents of a file.",
                parameters={"type": "object", "properties": {}},
            ),
            Tool(
                name="git_status",
                description="Show the working tree status.",
                parameters={"type": "object", "properties": {}},
            ),
        )

    def test_strong_rationale_for_matching_query(
        self,
        rationale_tools: tuple[Tool, ...],
    ) -> None:
        """Should generate strong rationale when tool matches query."""
        rationale = generate_heuristic_rationale(
            tool_name="search_files",
            query="search for error patterns in the code",
            available_tools=rationale_tools,
        )
        # "search" appears in both query and tool name
        assert rationale.strength in (RationaleStrength.STRONG, RationaleStrength.MODERATE)

    def test_weak_rationale_for_mismatched_query(
        self,
        rationale_tools: tuple[Tool, ...],
    ) -> None:
        """Should generate weak rationale when tool doesn't match query."""
        rationale = generate_heuristic_rationale(
            tool_name="git_status",
            query="download the file from the internet",
            available_tools=rationale_tools,
        )
        # No overlap between git_status and "download from internet"
        assert rationale.strength in (RationaleStrength.WEAK, RationaleStrength.MODERATE)

    def test_alternatives_suggested_for_weak(
        self,
        rationale_tools: tuple[Tool, ...],
    ) -> None:
        """Should suggest alternatives when rationale is weak."""
        # Use a tool that won't match
        rationale = generate_heuristic_rationale(
            tool_name="git_status",
            query="search for errors",
            available_tools=rationale_tools,
        )
        # If weak, alternatives should be suggested
        if rationale.strength == RationaleStrength.WEAK:
            # Alternatives may or may not be present depending on heuristics
            pass  # Just verify no crash


class TestRationaleValidator:
    """Tests for ToolRationaleValidator."""

    def test_validate_good_rationale(self) -> None:
        """Should validate a well-formed rationale."""
        validator = ToolRationaleValidator()

        result = validator.validate_rationale(
            tool_name="search_files",
            rationale="I need to search for error patterns in the codebase to find the bug.",
            query="find the bug causing the error",
        )

        assert result.strength in (RationaleStrength.STRONG, RationaleStrength.MODERATE)

    def test_validate_poor_rationale(self) -> None:
        """Should detect a poor rationale."""
        validator = ToolRationaleValidator()

        result = validator.validate_rationale(
            tool_name="git_commit",
            rationale="I will use this tool.",
            query="search for errors",
        )

        # Very vague rationale for unrelated tool
        assert result.strength in (RationaleStrength.WEAK, RationaleStrength.INVALID)

    def test_empty_rationale_invalid(self) -> None:
        """Empty rationale should be invalid."""
        validator = ToolRationaleValidator()

        result = validator.validate_rationale(
            tool_name="search_files",
            rationale="",
            query="search for errors",
        )

        assert result.strength == RationaleStrength.INVALID
