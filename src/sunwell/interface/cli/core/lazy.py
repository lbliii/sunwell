"""Lazy loading utilities for CLI commands.

Provides lazy import patterns to improve CLI cold start time by deferring
heavy module imports until the command is actually invoked.
"""

from collections.abc import Callable
from typing import Any

import click


class LazyCommand(click.Command):
    """A Click command that lazily imports its callback module.

    This delays the import of heavy dependencies until the command is
    actually invoked, improving --help and --version performance.
    """

    def __init__(
        self,
        name: str,
        import_path: str,
        callback_name: str,
        help_text: str = "",
        hidden: bool = False,
        params: list[click.Parameter] | None = None,
    ):
        """Initialize a lazy command.

        Args:
            name: Command name
            import_path: Full module path to import (e.g., "sunwell.interface.cli.commands.config_cmd")
            callback_name: Name of the callback function/command in the module
            help_text: Help text for the command
            hidden: Whether command is hidden
            params: Command parameters (if known upfront)
        """
        self._import_path = import_path
        self._callback_name = callback_name
        self._loaded = False
        self._real_command: click.Command | None = None

        # Initialize with a placeholder callback
        super().__init__(
            name=name,
            callback=self._lazy_callback,
            help=help_text,
            hidden=hidden,
            params=params or [],
        )

    def _load_command(self) -> click.Command:
        """Load the actual command module."""
        if self._real_command is not None:
            return self._real_command

        import importlib

        module = importlib.import_module(self._import_path)
        self._real_command = getattr(module, self._callback_name)
        self._loaded = True
        return self._real_command

    def _lazy_callback(self, **kwargs: Any) -> Any:
        """Placeholder callback that loads and invokes the real command."""
        cmd = self._load_command()
        ctx = click.get_current_context()
        return ctx.invoke(cmd, **kwargs)

    def get_params(self, ctx: click.Context) -> list[click.Parameter]:
        """Get parameters, loading real command if needed."""
        if not self._loaded:
            cmd = self._load_command()
            if hasattr(cmd, "params"):
                return cmd.params
        return super().get_params(ctx)

    def invoke(self, ctx: click.Context) -> Any:
        """Invoke the command, loading if needed."""
        cmd = self._load_command()
        return cmd.invoke(ctx)


class LazyGroup(click.Group):
    """A Click group that lazily loads subcommands.

    Subcommands are only imported when actually invoked, not when
    listing commands or showing help.
    """

    def __init__(
        self,
        name: str | None = None,
        commands: dict[str, click.Command] | None = None,
        lazy_commands: dict[str, tuple[str, str, str, bool]] | None = None,
        **attrs: Any,
    ):
        """Initialize a lazy group.

        Args:
            name: Group name
            commands: Eagerly loaded commands
            lazy_commands: Dict mapping command name to (import_path, callback_name, help_text, hidden)
            **attrs: Additional Click group attributes
        """
        super().__init__(name=name, commands=commands, **attrs)
        self._lazy_commands = lazy_commands or {}

    def list_commands(self, ctx: click.Context) -> list[str]:
        """List all commands (both loaded and lazy)."""
        commands = list(super().list_commands(ctx))
        commands.extend(self._lazy_commands.keys())
        return sorted(set(commands))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Get a command, loading lazily if needed."""
        # Try already-loaded commands first
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd

        # Try lazy commands
        if cmd_name in self._lazy_commands:
            import_path, callback_name, help_text, hidden = self._lazy_commands[cmd_name]
            return LazyCommand(
                name=cmd_name,
                import_path=import_path,
                callback_name=callback_name,
                help_text=help_text,
                hidden=hidden,
            )

        return None


def lazy_command(
    import_path: str,
    callback_name: str,
    help_text: str = "",
    hidden: bool = False,
) -> Callable[[str], click.Command]:
    """Factory function to create lazy commands.

    Usage:
        main.add_command(
            lazy_command(
                "sunwell.interface.cli.commands.heavy_cmd",
                "heavy",
                help_text="A command with heavy deps",
            )("heavy")
        )
    """

    def make_command(name: str) -> click.Command:
        return LazyCommand(
            name=name,
            import_path=import_path,
            callback_name=callback_name,
            help_text=help_text,
            hidden=hidden,
        )

    return make_command
