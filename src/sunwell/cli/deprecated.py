"""Deprecated command aliases (RFC-109).

This module provides backward-compatible aliases for deprecated commands,
showing migration warnings while still executing the intended functionality.

Migration Guide:
    agent run "goal"     → sunwell "goal"
    ask "question"       → sunwell "question"
    do ::a-2 file        → sunwell -s a-2 file
    apply lens           → sunwell -l lens
    bind ...             → sunwell config binding ...
    env ...              → sunwell config env ...
    bootstrap            → sunwell setup
    plan ...             → sunwell --plan ...
    scan path            → sunwell project --scan path
    workspace ...        → sunwell project ...
    import path          → sunwell project --import path
    open .               → sunwell .
    verify ...           → sunwell -s verify ...
    guardrails ...       → sunwell config safety ...
    team ...             → sunwell session ...
"""

import sys

import click
from rich.console import Console

console = Console()


# ============================================================================
# Deprecation Registry
# ============================================================================

# Commands that have moved elsewhere (aliased with warnings)
DEPRECATED_ALIASES: dict[str, str | None] = {
    # "Talk to agent" variants → main entry point
    "agent": "sunwell",  # agent run "goal" → sunwell "goal"
    "ask": "sunwell",  # ask "question" → sunwell "question"
    "apply": "sunwell -s",  # apply lens → sunwell -l lens
    # Shortcut execution absorbed into -s flag
    "do": "sunwell -s",  # do ::a-2 file → sunwell -s a-2 file
    # Absorbed into config command
    "bind": "sunwell config binding",
    "env": "sunwell config env",
    "bootstrap": "sunwell setup",
    # Absorbed into project command
    "plan": "sunwell --plan",
    "scan": "sunwell project --scan",
    "workspace": "sunwell project",
    "import": "sunwell project --import",
    # Absorbed into main
    "open": "sunwell",  # open . → sunwell .
    "verify": "sunwell -s verify",
    "guardrails": "sunwell config safety",
    "team": "sunwell session",
    # Internal leakage (should never have been top-level) - remove
    "briefing": None,  # Agent continuity is internal
    "intel": None,  # Absorbed into project analysis
    "reason": None,  # Internal LLM routing
    "external": None,  # Internal integration
}


def _show_deprecation_warning(old_cmd: str, new_cmd: str | None) -> None:
    """Show a deprecation warning with migration hint."""
    if new_cmd:
        console.print(
            f"[yellow]⚠️  '{old_cmd}' is deprecated. Use '{new_cmd}' instead.[/yellow]",
            file=sys.stderr,
        )
    else:
        console.print(
            f"[yellow]⚠️  '{old_cmd}' is deprecated and will be removed.[/yellow]",
            file=sys.stderr,
        )


def make_deprecated_command(old_name: str, new_cmd: str | None) -> click.Command:
    """Create a deprecated command that shows warning and forwards to new command.

    Args:
        old_name: The deprecated command name
        new_cmd: The new command to use (or None if removed entirely)

    Returns:
        A click.Command that shows warning and forwards
    """

    @click.command(name=old_name, hidden=True)
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    @click.pass_context
    def deprecated_cmd(ctx: click.Context, args: tuple[str, ...]) -> None:
        """Deprecated command that shows warning and forwards to new command."""
        _show_deprecation_warning(old_name, new_cmd)

        if new_cmd is None:
            console.print("[red]This command has been removed.[/red]")
            ctx.exit(1)
            return

        # For commands that map to main entry point
        if new_cmd == "sunwell":
            # Forward to main with the args
            console.print(f"[dim]→ Forwarding to: sunwell {' '.join(args)}[/dim]")
            # Re-invoke the main command
            from sunwell.cli.main import main

            ctx.invoke(main, *args)
        elif new_cmd.startswith("sunwell -s"):
            # Forward to shortcut execution
            console.print(f"[dim]→ Forwarding to: sunwell -s {' '.join(args)}[/dim]")
            # This will be handled by the main command's -s flag
            from sunwell.cli.main import main

            # Parse args: first is shortcut, rest is target
            if args:
                # Remove :: prefix if present
                shortcut = args[0].lstrip(":")
                target = args[1] if len(args) > 1 else None
                # Import and run shortcut
                import asyncio

                from sunwell.cli.shortcuts import run_shortcut

                asyncio.run(
                    run_shortcut(
                        shortcut=shortcut,
                        target=target,
                        context_str=None,
                        lens_name="tech-writer",
                        provider=None,
                        model=None,
                        plan_only=False,
                        json_output=False,
                        verbose=False,
                    )
                )
        else:
            # Generic forwarding message
            console.print(f"[dim]→ Use instead: {new_cmd} {' '.join(args)}[/dim]")
            ctx.exit(0)

    return deprecated_cmd


def register_deprecated_commands(group: click.Group) -> None:
    """Register all deprecated commands on the given group.

    Args:
        group: The click.Group to add deprecated commands to
    """
    for old_name, new_cmd in DEPRECATED_ALIASES.items():
        # Skip if already registered (some commands still exist)
        if old_name in group.commands:
            continue

        cmd = make_deprecated_command(old_name, new_cmd)
        group.add_command(cmd, name=old_name)
