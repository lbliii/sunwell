"""Tests for MCP server creation and configuration."""

import pytest
from unittest.mock import patch, MagicMock


def _mcp_available() -> bool:
    """Check if MCP package is available."""
    try:
        from sunwell.mcp.server import MCP_AVAILABLE
        return MCP_AVAILABLE
    except ImportError:
        return False


class TestMCPServerCreation:
    """Tests for MCP server creation."""

    def test_import_without_mcp_installed(self):
        """Import should work even without MCP installed."""
        # The module should be importable
        from sunwell.mcp import server
        assert hasattr(server, "create_server")
        assert hasattr(server, "main")

    def test_create_server_without_mcp_raises(self):
        """create_server should raise ImportError if MCP not installed."""
        from sunwell.mcp.server import MCP_AVAILABLE
        
        if not MCP_AVAILABLE:
            from sunwell.mcp.server import create_server
            with pytest.raises(ImportError) as exc_info:
                create_server()
            assert "MCP package not installed" in str(exc_info.value)

    @pytest.mark.skipif(
        not _mcp_available(),
        reason="MCP package not installed"
    )
    def test_create_server_with_mcp(self):
        """create_server should return FastMCP instance when MCP is available."""
        from sunwell.mcp.server import create_server
        
        # Mock tools, resources, and runtime to avoid loading actual subsystems
        with patch("sunwell.mcp.tools.register_tools"):
            with patch("sunwell.mcp.resources.register_resources"):
                with patch("sunwell.mcp.runtime.MCPRuntime") as mock_runtime_cls:
                    mock_runtime_cls.return_value = MagicMock()
                    server = create_server()
                    assert server is not None
                    assert server.name == "sunwell"
                    # Verify runtime was created and stored
                    mock_runtime_cls.assert_called_once_with(workspace=None)
                    assert hasattr(server, "_sunwell_runtime")

    @pytest.mark.skipif(
        not _mcp_available(),
        reason="MCP package not installed"
    )
    def test_create_server_passes_runtime_to_tools(self):
        """create_server should pass the runtime to register_tools."""
        from sunwell.mcp.server import create_server

        with patch("sunwell.mcp.tools.register_tools") as mock_tools:
            with patch("sunwell.mcp.resources.register_resources") as mock_resources:
                with patch("sunwell.mcp.runtime.MCPRuntime") as mock_runtime_cls:
                    mock_rt = MagicMock()
                    mock_runtime_cls.return_value = mock_rt
                    server = create_server(workspace="/tmp/test")

                    # Verify runtime was passed (not raw workspace string)
                    mock_tools.assert_called_once()
                    call_args = mock_tools.call_args
                    assert call_args[0][2] is mock_rt  # third positional arg is runtime

                    mock_resources.assert_called_once()
                    res_args = mock_resources.call_args
                    assert res_args[0][1] is mock_rt  # second positional arg is runtime


class TestMCPInstructions:
    """Tests for MCP server instructions."""

    def test_instructions_content(self):
        """Instructions should contain key guidance."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "sunwell_lens" in SUNWELL_INSTRUCTIONS
        assert "sunwell_list" in SUNWELL_INSTRUCTIONS
        assert "sunwell_route" in SUNWELL_INSTRUCTIONS
        assert "expertise" in SUNWELL_INSTRUCTIONS.lower()

    def test_instructions_document_format_tiers(self):
        """Instructions should document the format tier system."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "Format Tiers" in SUNWELL_INSTRUCTIONS
        assert "summary" in SUNWELL_INSTRUCTIONS
        assert "compact" in SUNWELL_INSTRUCTIONS
        assert "full" in SUNWELL_INSTRUCTIONS

    def test_instructions_document_thin_mode(self):
        """Instructions should document thin mode for large content tools."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "Thin Mode" in SUNWELL_INSTRUCTIONS
        assert "include_context" in SUNWELL_INSTRUCTIONS

    def test_instructions_document_summary_resources(self):
        """Instructions should document summary resource variants."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "sunwell://briefing/summary" in SUNWELL_INSTRUCTIONS
        assert "sunwell://learnings/summary" in SUNWELL_INSTRUCTIONS
        assert "sunwell://goals/summary" in SUNWELL_INSTRUCTIONS
        assert "sunwell://lenses/minimal" in SUNWELL_INSTRUCTIONS

    def test_instructions_document_token_budget_guidance(self):
        """Instructions should include token budget guidance."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "Token Budget" in SUNWELL_INSTRUCTIONS
        assert "Scanning phase" in SUNWELL_INSTRUCTIONS
