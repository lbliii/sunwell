"""MCP Server entry point for Sunwell.

Exposes Sunwell's full intelligence to MCP hosts (Cursor, Claude Desktop, etc.):
lenses, memory, knowledge, planning, backlog, introspection, execution, and delegation.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# MCP imports - optional dependency
try:
    from mcp.server.fastmcp import FastMCP

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    FastMCP = None  # type: ignore[misc, assignment]

from sunwell.mcp.instructions import SUNWELL_INSTRUCTIONS

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP as FastMCPType


def create_server(
    lenses_dir: str | None = None,
    workspace: str | None = None,
) -> FastMCPType:
    """Create MCP server with all Sunwell tools and resources.

    Args:
        lenses_dir: Path to lenses directory. If None, uses default discovery.
        workspace: Path to workspace root. If None, uses current directory.

    Returns:
        Configured FastMCP server instance
    """
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP package not installed. Install with: pip install 'sunwell[mcp]'"
        )

    from sunwell.mcp.resources import register_resources
    from sunwell.mcp.tools import register_tools

    mcp = FastMCP("sunwell", instructions=SUNWELL_INSTRUCTIONS)

    # Register all tools (lenses, memory, knowledge, planning, backlog, mirror, execution, delegation)
    register_tools(mcp, lenses_dir, workspace)

    # Register all resources (core, lens, knowledge, memory, backlog, reference)
    register_resources(mcp, workspace, lenses_dir)

    # Store config for reference
    mcp._sunwell_lenses_dir = lenses_dir  # type: ignore[attr-defined]
    mcp._sunwell_workspace = workspace  # type: ignore[attr-defined]

    return mcp


async def run_server_async(mcp: FastMCPType) -> None:
    """Run MCP server with graceful shutdown support.

    Args:
        mcp: Configured FastMCP server instance
    """
    # Create shutdown event
    shutdown_event = asyncio.Event()

    # Install signal handlers for async context
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        """Signal handler that requests graceful shutdown."""
        shutdown_event.set()

    # Add signal handlers (Unix only)
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, request_shutdown)

    try:
        # Run MCP server in a thread (FastMCP.run() is blocking)
        server_task = asyncio.create_task(asyncio.to_thread(mcp.run))
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either server completion or shutdown request
        _done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks gracefully
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        # Remove signal handlers to restore defaults
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)


def main() -> None:
    """CLI entry point for MCP server."""
    parser = argparse.ArgumentParser(description="Sunwell MCP Server")
    parser.add_argument(
        "--lenses-dir",
        default=None,
        help="Lenses directory (default: auto-discovered)",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory (default: current directory)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test server setup and exit",
    )

    args = parser.parse_args()

    if not MCP_AVAILABLE:
        print("Error: MCP package not installed")
        print("Install with: pip install 'sunwell[mcp]'")
        sys.exit(1)

    if args.test:
        print("Testing Sunwell MCP Server setup...")
        if args.lenses_dir:
            print(f"  Lenses directory: {args.lenses_dir}")
        else:
            print("  Lenses directory: Auto-discovering...")
        if args.workspace:
            print(f"  Workspace: {args.workspace}")
        else:
            print(f"  Workspace: {Path.cwd()}")

        try:
            mcp = create_server(args.lenses_dir, args.workspace)
            print(f"  Server created: {mcp.name}")
            print("  MCP server is ready!")
        except Exception as e:
            print(f"  Error: {e}")
            sys.exit(1)
        return

    # Validate lenses directory if provided
    if args.lenses_dir:
        lenses_path = Path(args.lenses_dir)
        if not lenses_path.exists():
            print(f"Error: Lenses directory not found: {lenses_path}")
            sys.exit(1)

    # Validate workspace directory if provided
    if args.workspace:
        workspace_path = Path(args.workspace)
        if not workspace_path.exists():
            print(f"Error: Workspace directory not found: {workspace_path}")
            sys.exit(1)

    # Run server
    mcp = create_server(args.lenses_dir, args.workspace)

    try:
        asyncio.run(run_server_async(mcp))
    except KeyboardInterrupt:
        pass  # Clean exit for MCP subprocess

    sys.exit(0)


if __name__ == "__main__":
    main()
