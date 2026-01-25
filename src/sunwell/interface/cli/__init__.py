"""Sunwell CLI - Modular command-line interface.

This package contains all CLI commands, organized by functionality.

RFC-138: Module Architecture Consolidation - Reorganized into:
- core/ - Core CLI infrastructure (main, theme, shortcuts, etc.)
- commands/ - All command implementations (*_cmd.py files)
- chat/ - Chat functionality
- helpers/ - Helper utilities
- utils/ - Formatting utilities
"""

# Only export the main entry points - everything else should be imported directly
from sunwell.interface.cli.core.main import cli_entrypoint, main

__all__ = ["cli_entrypoint", "main"]
