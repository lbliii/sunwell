"""CLI Error Handler.

Provides unified error handling for the CLI with support for:
- Human-readable output (default)
- JSON output for machine consumption (Tauri/programmatic use)

This module bridges the Python error system (core/errors.py) with external
consumers like Tauri Studio.
"""

import json
import sys
from typing import NoReturn

from sunwell.core.errors import SunwellError


def handle_error(
    error: SunwellError | Exception,
    json_output: bool = False,
) -> NoReturn:
    """Handle an error with optional JSON output for machine consumption.

    Args:
        error: The error to handle (SunwellError or generic Exception)
        json_output: If True, output JSON to stderr for Tauri/programmatic use

    Raises:
        SystemExit: Always exits with code 1
    """
    # Wrap generic exceptions in SunwellError
    if not isinstance(error, SunwellError):
        from sunwell.core.errors import ErrorCode

        error = SunwellError(
            code=ErrorCode.RUNTIME_STATE_INVALID,
            context={"detail": str(error)},
            cause=error if isinstance(error, Exception) else None,
        )

    if json_output:
        # Structured output for Tauri/programmatic use
        error_dict = error.to_dict()
        # Add cause if present (for debugging)
        if error.cause:
            error_dict["cause"] = str(error.cause)
        print(json.dumps(error_dict), file=sys.stderr)
        sys.exit(1)

    # Human-readable output for CLI
    _print_human_error(error)
    sys.exit(1)


def _print_human_error(error: SunwellError) -> None:
    """Print error in human-readable format using rich if available."""
    try:
        from rich.console import Console
        from rich.text import Text

        console = Console(stderr=True)

        # Header with error ID and category icon
        icons = {
            "model": "🤖",
            "lens": "🔍",
            "tool": "🔧",
            "validation": "✓",
            "config": "⚙️",
            "runtime": "⚡",
            "io": "📁",
        }
        icon = icons.get(error.category, "❌")

        # Build error message
        header = Text()
        header.append(f"{icon} ", style="bold")
        header.append(f"{error.error_id}", style="bold red")
        header.append(f" {error.message}")

        console.print(header)

        # Recovery hints
        if error.recovery_hints:
            console.print("\n[bold]What you can do:[/]")
            for i, hint in enumerate(error.recovery_hints, 1):
                console.print(f"  {i}. {hint}")

    except ImportError:
        # Fallback without rich
        print(f"[{error.error_id}] {error.message}", file=sys.stderr)
        if error.recovery_hints:
            print("\nWhat you can do:", file=sys.stderr)
            for i, hint in enumerate(error.recovery_hints, 1):
                print(f"  {i}. {hint}", file=sys.stderr)


def format_error_for_json(error: SunwellError | Exception) -> str:
    """Format an error as JSON string.

    Useful for returning errors from functions that will be parsed by Tauri.

    Args:
        error: The error to format

    Returns:
        JSON string representation of the error
    """
    if not isinstance(error, SunwellError):
        from sunwell.core.errors import ErrorCode

        error = SunwellError(
            code=ErrorCode.RUNTIME_STATE_INVALID,
            context={"detail": str(error)},
            cause=error if isinstance(error, Exception) else None,
        )

    error_dict = error.to_dict()
    if error.cause:
        error_dict["cause"] = str(error.cause)

    return json.dumps(error_dict)


def parse_error_from_json(json_str: str) -> SunwellError | None:
    """Parse a SunwellError from JSON string.

    Args:
        json_str: JSON string representation of an error

    Returns:
        SunwellError if parsing succeeded, None otherwise
    """
    try:
        data = json.loads(json_str)

        # Must have required fields
        if not all(k in data for k in ("error_id", "code", "message")):
            return None

        from sunwell.core.errors import ErrorCode

        # Try to get ErrorCode from code
        try:
            code = ErrorCode(data["code"])
        except ValueError:
            # Unknown code, use a fallback
            code = ErrorCode.RUNTIME_STATE_INVALID

        return SunwellError(
            code=code,
            context=data.get("context", {}),
        )
    except (json.JSONDecodeError, KeyError):
        return None
