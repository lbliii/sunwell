"""Core CLI infrastructure.

This module contains the core CLI components:
- Main entry point and command group
- Error handling
- Theme and styling
- Shortcuts
- State management
- Session handling
"""

from sunwell.interface.cli.core.main import GoalFirstGroup, cli_entrypoint, main
from sunwell.interface.cli.core.error_handler import (
    format_error_for_json,
    handle_error,
    parse_error_from_json,
)
from sunwell.interface.cli.core.theme import (
    SUNWELL_THEME,
    create_sunwell_console,
    should_reduce_motion,
)
from sunwell.interface.cli.core.shortcuts import (
    complete_shortcut,
    complete_target,
    get_default_shortcuts,
    run_shortcut,
)

__all__ = [
    # Main
    "main",
    "cli_entrypoint",
    "GoalFirstGroup",
    # Error handling
    "handle_error",
    "format_error_for_json",
    "parse_error_from_json",
    # Theme
    "create_sunwell_console",
    "SUNWELL_THEME",
    "should_reduce_motion",
    # Shortcuts
    "run_shortcut",
    "complete_shortcut",
    "complete_target",
    "get_default_shortcuts",
]
