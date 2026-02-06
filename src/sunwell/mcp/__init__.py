"""Sunwell MCP Server - Expose full intelligence to AI agents.

This module provides MCP (Model Context Protocol) integration for Sunwell,
allowing AI agents in Cursor, Claude Desktop, and other MCP hosts to access
Sunwell's full capabilities: lenses, memory, knowledge, planning, backlog,
introspection, execution, and model delegation.

Usage:
    # As MCP server
    python -m sunwell.mcp

    # With workspace
    python -m sunwell.mcp --workspace /path/to/project

    # Configure for Cursor
    sunwell setup cursor
"""

from sunwell.mcp.server import create_server, main

__all__ = ["create_server", "main"]
