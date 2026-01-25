"""Sunwell CLI - Command-line interface.

This module imports from the modular cli/ package structure.
All commands have been extracted into separate modules for better organization.
"""

from sunwell.interface.cli.core.main import cli_entrypoint, main

__all__ = ["cli_entrypoint", "main"]
