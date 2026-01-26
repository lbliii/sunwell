"""Tests for Sunwell self-access tools (RFC-125)."""

import pytest
from pathlib import Path

from sunwell.tools.sunwell import SunwellToolHandlers
from sunwell.tools.definitions.sunwell import (
    SUNWELL_TOOLS,
    SUNWELL_WORKSPACE_TOOLS,
    SUNWELL_READ_ONLY_TOOLS,
)


class TestToolDefinitions:
    """Tool definition tests."""

    def test_all_tools_have_names(self) -> None:
        """All tools should have matching name in dict key and Tool.name."""
        for name, tool in SUNWELL_TOOLS.items():
            assert tool.name == name, f"Tool {name} has mismatched name: {tool.name}"

    def test_workspace_tools_subset_of_all(self) -> None:
        """WORKSPACE tools should be a subset of all tools."""
        all_names = set(SUNWELL_TOOLS.keys())
        assert SUNWELL_WORKSPACE_TOOLS.issubset(all_names)

    def test_read_only_tools_subset_of_all(self) -> None:
        """READ_ONLY tools should be a subset of all tools."""
        all_names = set(SUNWELL_TOOLS.keys())
        assert SUNWELL_READ_ONLY_TOOLS.issubset(all_names)

    def test_tool_count(self) -> None:
        """Should have exactly 13 tools."""
        assert len(SUNWELL_TOOLS) == 13

    def test_all_tools_have_descriptions(self) -> None:
        """All tools should have non-empty descriptions."""
        for name, tool in SUNWELL_TOOLS.items():
            assert tool.description, f"Tool {name} has no description"
            assert len(tool.description) > 20, f"Tool {name} description too short"


class TestSecurityGuardrails:
    """Security constraint tests."""

    def test_no_recursive_agent_spawn(self) -> None:
        """Should not have agent spawning tools."""
        dangerous_names = ["agent_run", "agent_spawn", "chat_start", "agent_execute"]
        for name in dangerous_names:
            assert f"sunwell_{name}" not in SUNWELL_TOOLS

    def test_self_access_read_only(self) -> None:
        """Self-access tools should be read-only (no write/edit/modify)."""
        write_names = ["self_edit", "self_write", "self_modify", "self_delete"]
        for name in write_names:
            assert f"sunwell_{name}" not in SUNWELL_TOOLS

    def test_self_tools_at_read_only_level(self) -> None:
        """Self-knowledge tools should be at READ_ONLY level."""
        self_tools = {"sunwell_self_modules", "sunwell_self_search", "sunwell_self_read"}
        assert self_tools == SUNWELL_READ_ONLY_TOOLS


class TestIntelligenceHandlers:
    """Project intelligence tool handler tests."""

    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        """Create handlers with minimal project structure."""
        # Create minimal .sunwell directory structure
        (tmp_path / ".sunwell" / "intelligence").mkdir(parents=True)
        (tmp_path / ".sunwell" / "sessions").mkdir(parents=True)
        (tmp_path / ".sunwell" / "lineage" / "artifacts").mkdir(parents=True)
        return SunwellToolHandlers(workspace=tmp_path)

    @pytest.mark.asyncio
    async def test_decisions_empty_project(self, handlers: SunwellToolHandlers) -> None:
        """Should return helpful message for empty project."""
        result = await handlers.handle_intel_decisions(query="authentication")
        assert result.success
        assert "No matching decisions" in result.output or "decision" in result.output.lower()

    @pytest.mark.asyncio
    async def test_failures_empty_project(self, handlers: SunwellToolHandlers) -> None:
        """Should return helpful message when no failures."""
        result = await handlers.handle_intel_failures(query="async database")
        assert result.success
        assert "No similar failures" in result.output or "Proceed with caution" in result.output

    @pytest.mark.asyncio
    async def test_patterns_returns_structure(self, handlers: SunwellToolHandlers) -> None:
        """Should return pattern structure even for new project."""
        result = await handlers.handle_intel_patterns()
        assert result.success
        assert "Code Patterns" in result.output


class TestSelfKnowledgeHandlers:
    """Self-knowledge tool handler tests."""

    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        """Create handlers."""
        return SunwellToolHandlers(workspace=tmp_path)

    @pytest.mark.asyncio
    async def test_modules_lists_sunwell(self, handlers: SunwellToolHandlers) -> None:
        """Should list Sunwell modules."""
        result = await handlers.handle_self_modules()
        assert result.success
        assert "sunwell" in result.output.lower()

    @pytest.mark.asyncio
    async def test_modules_with_pattern(self, handlers: SunwellToolHandlers) -> None:
        """Should filter modules by pattern."""
        result = await handlers.handle_self_modules(pattern="sunwell.tools")
        assert result.success
        # Should contain tools-related output
        assert "tools" in result.output.lower()

    @pytest.mark.asyncio
    async def test_self_search_finds_code(self, handlers: SunwellToolHandlers) -> None:
        """Should find code by semantic query."""
        result = await handlers.handle_self_search(query="tool executor dispatch")
        assert result.success
        # Should find something or return "no matches"

    @pytest.mark.asyncio
    async def test_self_read_returns_source(self, handlers: SunwellToolHandlers) -> None:
        """Should return module source code."""
        result = await handlers.handle_self_read(module="sunwell.tools.types")
        assert result.success
        # Should contain ToolTrust or class definitions
        assert "ToolTrust" in result.output or "class" in result.output

    @pytest.mark.asyncio
    async def test_self_read_module_not_found(self, handlers: SunwellToolHandlers) -> None:
        """Should handle non-existent module."""
        result = await handlers.handle_self_read(module="sunwell.nonexistent.module")
        assert not result.success
        assert "not found" in result.output.lower()


class TestLineageHandlers:
    """Lineage tool handler tests."""

    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        """Create handlers with lineage structure."""
        (tmp_path / ".sunwell" / "lineage" / "artifacts").mkdir(parents=True)
        return SunwellToolHandlers(workspace=tmp_path)

    @pytest.mark.asyncio
    async def test_lineage_file_not_found(self, handlers: SunwellToolHandlers) -> None:
        """Should handle file with no lineage."""
        result = await handlers.handle_lineage_file(path="nonexistent.py")
        assert result.success
        assert "No lineage found" in result.output

    @pytest.mark.asyncio
    async def test_impact_file_not_found(self, handlers: SunwellToolHandlers) -> None:
        """Should handle impact for file with no lineage."""
        result = await handlers.handle_lineage_impact(path="nonexistent.py")
        assert result.success
        assert "No lineage found" in result.output


class TestWorkflowHandlers:
    """Workflow tool handler tests."""

    @pytest.fixture
    def handlers(self, tmp_path: Path) -> SunwellToolHandlers:
        """Create handlers."""
        return SunwellToolHandlers(workspace=tmp_path)

    @pytest.mark.asyncio
    async def test_workflow_chains_lists_available(self, handlers: SunwellToolHandlers) -> None:
        """Should list available workflow chains."""
        result = await handlers.handle_workflow_chains()
        assert result.success
        assert "Workflow Chains" in result.output

    @pytest.mark.asyncio
    async def test_workflow_route_classifies_intent(self, handlers: SunwellToolHandlers) -> None:
        """Should classify and route user request."""
        result = await handlers.handle_workflow_route(request="audit and fix this documentation")
        assert result.success
        assert "Workflow Routing" in result.output
        assert "Category" in result.output
        assert "Confidence" in result.output


class TestTrustLevelIntegration:
    """Trust level integration tests."""

    def test_workspace_tools_in_trust_levels(self) -> None:
        """Workspace tools should be in WORKSPACE trust level."""
        from sunwell.tools.core.types import TRUST_LEVEL_TOOLS, ToolTrust

        workspace_allowed = TRUST_LEVEL_TOOLS[ToolTrust.WORKSPACE]
        for tool in SUNWELL_WORKSPACE_TOOLS:
            assert tool in workspace_allowed, f"{tool} not in WORKSPACE trust level"

    def test_read_only_tools_in_trust_levels(self) -> None:
        """Read-only tools should be in READ_ONLY trust level."""
        from sunwell.tools.core.types import TRUST_LEVEL_TOOLS, ToolTrust

        read_only_allowed = TRUST_LEVEL_TOOLS[ToolTrust.READ_ONLY]
        for tool in SUNWELL_READ_ONLY_TOOLS:
            assert tool in read_only_allowed, f"{tool} not in READ_ONLY trust level"

    def test_all_sunwell_tools_in_full_level(self) -> None:
        """All Sunwell tools should be available at FULL trust level."""
        from sunwell.tools.core.types import TRUST_LEVEL_TOOLS, ToolTrust

        full_allowed = TRUST_LEVEL_TOOLS[ToolTrust.FULL]
        for tool in SUNWELL_TOOLS:
            assert tool in full_allowed, f"{tool} not in FULL trust level"


class TestBuiltinsExport:
    """Test that tools are exported in builtins."""

    def test_sunwell_tools_in_get_all_tools(self) -> None:
        """Sunwell tools should be included in get_all_tools()."""
        from sunwell.tools.definitions.builtins import get_all_tools

        all_tools = get_all_tools()
        for tool_name in SUNWELL_TOOLS:
            assert tool_name in all_tools, f"{tool_name} not in get_all_tools()"
