"""Runtime environment checks."""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from sunwell.foundation.threading import is_free_threaded


def check_free_threading(quiet: bool = False) -> bool:
    """Check if running on free-threaded Python and warn if not.

    Returns True if free-threaded, False otherwise.
    Warnings are printed to stderr to keep stdout clean for --json mode.
    """
    if is_free_threaded():
        return True

    if not quiet and os.environ.get("SUNWELL_NO_GIL_WARNING") != "1":
        from rich.console import Console

        stderr_console = Console(file=os.sys.stderr)
        # RFC-053: Print to stderr so --json mode isn't corrupted
        stderr_console.print(
            "[yellow]⚠️  Running on standard Python (GIL enabled)[/yellow]"
        )
        stderr_console.print(
            "[dim]   For optimal performance, use Python 3.14t (free-threaded):[/dim]"
        )
        stderr_console.print(
            "[dim]   /usr/local/bin/python3.14t -m sunwell chat[/dim]"
        )
        stderr_console.print(
            "[dim]   Set SUNWELL_NO_GIL_WARNING=1 to suppress this message.[/dim]"
        )
        stderr_console.print()

    return False
