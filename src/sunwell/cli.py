"""Sunwell CLI - Command-line interface.

This module now imports from the modular cli/ package structure.
All commands have been extracted into separate modules for better organization.

For backward compatibility, this file re-exports the main CLI entry point.
"""

from sunwell.cli import main

# Re-export for backward compatibility
__all__ = ["main"]
