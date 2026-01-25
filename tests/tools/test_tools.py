"""Tests for RFC-012 tool calling support."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from sunwell.tools.core.types import ToolTrust, ToolResult, ToolRateLimits, ToolPolicy
from sunwell.tools.definitions.builtins import CORE_TOOLS, get_tools_for_trust_level
from sunwell.tools.handlers.base import CoreToolHandlers, PathSecurityError, DEFAULT_BLOCKED_PATTERNS
from sunwell.knowledge.project import Project
from sunwell.tools.execution.executor import ToolExecutor
from sunwell.models.core.protocol import Tool, ToolCall, Message, GenerateResult


# =============================================================================
# Path Security Tests
# =============================================================================


class TestPathSecurity:
    """Verify path traversal prevention."""
    
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "readme.md").write_text("# README")
        return tmp_path
    
    @pytest.fixture
    def handlers(self, workspace: Path) -> CoreToolHandlers:
        """Create handlers for the workspace."""
        return CoreToolHandlers(workspace)
    
    def test_safe_path_allows_workspace_files(self, handlers: CoreToolHandlers) -> None:
        """Paths within workspace should be allowed."""
        path = handlers._safe_path("src/main.py")
        assert path.is_relative_to(handlers.workspace)
    
    def test_safe_path_blocks_traversal(self, handlers: CoreToolHandlers) -> None:
        """Path traversal attempts should be blocked."""
        with pytest.raises(PathSecurityError, match="escapes workspace"):
            handlers._safe_path("../../../etc/passwd")
    
    def test_safe_path_blocks_dotenv(self, handlers: CoreToolHandlers) -> None:
        """Access to .env files should be blocked."""
        with pytest.raises(PathSecurityError, match="blocked by pattern"):
            handlers._safe_path(".env")
    
    def test_safe_path_blocks_env_variants(self, handlers: CoreToolHandlers) -> None:
        """Access to .env.* files should be blocked."""
        with pytest.raises(PathSecurityError, match="blocked by pattern"):
            handlers._safe_path(".env.local")
    
    def test_safe_path_blocks_git(self, handlers: CoreToolHandlers) -> None:
        """Access to .git directory should be blocked."""
        with pytest.raises(PathSecurityError, match="blocked by pattern"):
            handlers._safe_path(".git/config")
    
    def test_safe_path_blocks_absolute_traversal(self, handlers: CoreToolHandlers) -> None:
        """Absolute paths outside workspace should be blocked."""
        with pytest.raises(PathSecurityError, match="escapes workspace"):
            handlers._safe_path("/etc/passwd")


# =============================================================================
# Core Tool Handler Tests
# =============================================================================


class TestCoreToolHandlers:
    """Test built-in tool handlers."""
    
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace with test files."""
        (tmp_path / "test.txt").write_text("Hello, World!")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("def main():\n    pass")
        return tmp_path
    
    @pytest.fixture
    def handlers(self, workspace: Path) -> CoreToolHandlers:
        return CoreToolHandlers(workspace)
    
    @pytest.mark.asyncio
    async def test_read_file(self, handlers: CoreToolHandlers) -> None:
        """Test reading a file."""
        result = await handlers.read_file({"path": "test.txt"})
        assert "Hello, World!" in result
        assert "bytes" in result
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, handlers: CoreToolHandlers) -> None:
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            await handlers.read_file({"path": "nonexistent.txt"})
    
    @pytest.mark.asyncio
    async def test_write_file(self, handlers: CoreToolHandlers, workspace: Path) -> None:
        """Test writing a file."""
        result = await handlers.write_file({
            "path": "output.txt",
            "content": "Test content",
        })
        assert "✓ Wrote" in result
        assert (workspace / "output.txt").read_text() == "Test content"
    
    @pytest.mark.asyncio
    async def test_write_file_creates_dirs(self, handlers: CoreToolHandlers, workspace: Path) -> None:
        """Test that write_file creates parent directories."""
        result = await handlers.write_file({
            "path": "nested/deep/file.txt",
            "content": "Nested content",
        })
        assert "✓ Wrote" in result
        assert (workspace / "nested" / "deep" / "file.txt").exists()
    
    @pytest.mark.asyncio
    async def test_list_files(self, handlers: CoreToolHandlers) -> None:
        """Test listing files."""
        result = await handlers.list_files({"path": "."})
        assert "test.txt" in result
        assert "src" in result
    
    @pytest.mark.asyncio
    async def test_list_files_with_pattern(self, handlers: CoreToolHandlers) -> None:
        """Test listing files with glob pattern."""
        result = await handlers.list_files({"path": ".", "pattern": "*.txt"})
        assert "test.txt" in result
    
    @pytest.mark.asyncio
    async def test_search_files(self, handlers: CoreToolHandlers) -> None:
        """Test searching files."""
        result = await handlers.search_files({"pattern": "Hello"})
        # Result depends on whether rg is installed
        assert "Hello" in result or "No matches" in result or "matches" in result


# =============================================================================
# Tool Executor Tests
# =============================================================================


class TestToolExecutor:
    """Test tool execution and dispatch."""
    
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "test.txt").write_text("Test content")
        return tmp_path
    
    @pytest.fixture
    def executor(self, workspace: Path) -> ToolExecutor:
        project = Project(root=workspace, id="test-project", name="Test Project")
        return ToolExecutor(project=project)
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, executor: ToolExecutor) -> None:
        """Unknown tools should return an error."""
        result = await executor.execute(ToolCall(
            id="1",
            name="nonexistent_tool",
            arguments={},
        ))
        assert not result.success
        assert "Unknown tool" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_read_file(self, executor: ToolExecutor) -> None:
        """Test executing read_file tool."""
        result = await executor.execute(ToolCall(
            id="1",
            name="read_file",
            arguments={"path": "test.txt"},
        ))
        assert result.success
        assert "Test content" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_batch_sequential(self, executor: ToolExecutor) -> None:
        """Test executing multiple tools sequentially."""
        results = await executor.execute_batch([
            ToolCall(id="1", name="list_files", arguments={"path": "."}),
            ToolCall(id="2", name="read_file", arguments={"path": "test.txt"}),
        ])
        assert len(results) == 2
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, workspace: Path) -> None:
        """Test that rate limiting works."""
        limits = ToolRateLimits(max_tool_calls_per_minute=2)
        policy = ToolPolicy(rate_limits=limits)
        project = Project(root=workspace, id="test-project", name="Test Project")
        executor = ToolExecutor(project=project, policy=policy)
        
        # First two calls should succeed
        r1 = await executor.execute(ToolCall(id="1", name="list_files", arguments={}))
        r2 = await executor.execute(ToolCall(id="2", name="list_files", arguments={}))
        assert r1.success
        assert r2.success
        
        # Third call should be rate limited
        r3 = await executor.execute(ToolCall(id="3", name="list_files", arguments={}))
        assert not r3.success
        assert "Rate limit" in r3.output


# =============================================================================
# Tool Trust Level Tests
# =============================================================================


class TestToolTrust:
    """Test trust level functionality."""
    
    def test_trust_level_parsing(self) -> None:
        """Test parsing trust levels from strings."""
        assert ToolTrust.from_string("discovery") == ToolTrust.DISCOVERY
        assert ToolTrust.from_string("read_only") == ToolTrust.READ_ONLY
        assert ToolTrust.from_string("workspace") == ToolTrust.WORKSPACE
        assert ToolTrust.from_string("shell") == ToolTrust.SHELL
        assert ToolTrust.from_string("full") == ToolTrust.FULL
    
    def test_trust_includes(self) -> None:
        """Test trust level inclusion."""
        assert ToolTrust.FULL.includes(ToolTrust.DISCOVERY)
        assert ToolTrust.SHELL.includes(ToolTrust.WORKSPACE)
        assert ToolTrust.WORKSPACE.includes(ToolTrust.READ_ONLY)
        assert not ToolTrust.DISCOVERY.includes(ToolTrust.SHELL)
    
    def test_tools_for_trust_level(self) -> None:
        """Test getting tools for each trust level."""
        discovery = get_tools_for_trust_level("discovery")
        read_only = get_tools_for_trust_level("read_only")
        workspace = get_tools_for_trust_level("workspace")
        shell = get_tools_for_trust_level("shell")
        
        discovery_names = {t.name for t in discovery}
        read_only_names = {t.name for t in read_only}
        workspace_names = {t.name for t in workspace}
        shell_names = {t.name for t in shell}
        
        # Discovery should only have list_files and search_files
        assert "list_files" in discovery_names
        assert "search_files" in discovery_names
        assert "read_file" not in discovery_names
        
        # Read-only adds read_file
        assert "read_file" in read_only_names
        assert "write_file" not in read_only_names
        
        # Workspace adds write_file
        assert "write_file" in workspace_names
        assert "run_command" not in workspace_names
        
        # Shell adds run_command
        assert "run_command" in shell_names


# =============================================================================
# Tool Policy Tests
# =============================================================================


class TestToolPolicy:
    """Test tool policy functionality."""
    
    def test_default_policy_allows_workspace_tools(self) -> None:
        """Default policy should allow workspace-level tools."""
        policy = ToolPolicy()
        assert policy.is_tool_allowed("read_file")
        assert policy.is_tool_allowed("write_file")
        assert policy.is_tool_allowed("list_files")
        assert policy.is_tool_allowed("search_files")
        assert not policy.is_tool_allowed("run_command")
    
    def test_explicit_allowlist(self) -> None:
        """Explicit allowlist should override trust level."""
        policy = ToolPolicy(
            trust_level=ToolTrust.SHELL,
            allowed_tools=frozenset({"read_file"}),
        )
        assert policy.is_tool_allowed("read_file")
        assert not policy.is_tool_allowed("write_file")
        assert not policy.is_tool_allowed("run_command")
    
    def test_shell_trust_allows_run_command(self) -> None:
        """Shell trust should allow run_command."""
        policy = ToolPolicy(trust_level=ToolTrust.SHELL)
        assert policy.is_tool_allowed("run_command")


# =============================================================================
# Message and Tool Types Tests
# =============================================================================


class TestMessageTypes:
    """Test message and tool types."""
    
    def test_message_creation(self) -> None:
        """Test creating messages."""
        user_msg = Message(role="user", content="Hello")
        assert user_msg.role == "user"
        assert user_msg.content == "Hello"
        
        assistant_msg = Message(
            role="assistant",
            content="Hi!",
            tool_calls=(ToolCall(id="1", name="test", arguments={}),),
        )
        assert len(assistant_msg.tool_calls) == 1
    
    def test_tool_call_creation(self) -> None:
        """Test creating tool calls."""
        tc = ToolCall(id="test-1", name="read_file", arguments={"path": "x.txt"})
        assert tc.id == "test-1"
        assert tc.name == "read_file"
        assert tc.arguments["path"] == "x.txt"
    
    def test_generate_result_text_property(self) -> None:
        """Test GenerateResult.text property."""
        # With content
        result = GenerateResult(content="Hello", model="test")
        assert result.text == "Hello"
        
        # Without content (tool-only response)
        result_no_content = GenerateResult(
            content=None,
            model="test",
            tool_calls=(ToolCall(id="1", name="test", arguments={}),),
        )
        assert result_no_content.text == ""
        assert result_no_content.has_tool_calls


# =============================================================================
# CORE_TOOLS Tests
# =============================================================================


class TestCoreTools:
    """Test CORE_TOOLS definitions."""
    
    def test_all_core_tools_defined(self) -> None:
        """All expected core tools should be defined."""
        expected_tools = {
            "read_file", "write_file", "edit_file", "list_files", "search_files", "run_command",
            "mkdir", "git_init",  # Directory and git init tools
            "web_search", "web_fetch",  # Web access tools
            "git_info",  # Git info tool
        }
        assert expected_tools == set(CORE_TOOLS.keys())
    
    def test_tool_has_required_fields(self) -> None:
        """Each tool should have required fields."""
        for name, tool in CORE_TOOLS.items():
            assert tool.name == name
            assert tool.description
            assert "type" in tool.parameters
            assert tool.parameters["type"] == "object"
