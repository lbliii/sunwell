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
        
        # Mock the tools registration to avoid loading actual lenses
        with patch("sunwell.mcp.tools.register_tools"):
            server = create_server()
            assert server is not None
            assert server.name == "sunwell"


class TestMCPInstructions:
    """Tests for MCP server instructions."""

    def test_instructions_content(self):
        """Instructions should contain key guidance."""
        from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS
        
        assert "sunwell_lens" in SUNWELL_INSTRUCTIONS
        assert "sunwell_list" in SUNWELL_INSTRUCTIONS
        assert "sunwell_route" in SUNWELL_INSTRUCTIONS
        assert "expertise" in SUNWELL_INSTRUCTIONS.lower()
