"""Unified async execution for CLI commands.

Provides a consistent pattern for running async code from Click commands,
replacing scattered asyncio.run() calls throughout the CLI.

This module handles:
- Proper event loop management
- Nested async context detection
- Consistent error propagation
- Clean resource cleanup
"""

import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async code with proper event loop handling.

    Handles the common case of running async code from synchronous Click commands.
    Properly manages event loop lifecycle and ensures clean resource cleanup.

    Args:
        coro: The coroutine to execute

    Returns:
        The result of the coroutine

    Raises:
        Any exception raised by the coroutine is propagated
    """
    try:
        # Check if we're already in an async context
        asyncio.get_running_loop()
        # If we get here, there's a running loop - this shouldn't happen
        # in normal CLI usage, but handle it gracefully
        import nest_asyncio

        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No running loop - this is the normal case for CLI commands
        return asyncio.run(coro)


def async_command(
    f: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, T]:
    """Decorator that wraps async functions for Click commands.

    This decorator allows writing Click commands as async functions
    while Click itself expects synchronous callables.

    Usage:
        @click.command()
        @async_command
        async def my_command(arg: str) -> None:
            result = await some_async_operation(arg)
            console.print(result)

    The decorator preserves the function signature for Click's
    introspection and ensures proper async execution.
    """

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return run_async(f(*args, **kwargs))

    return wrapper


def async_callback(
    f: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, T]:
    """Decorator for async Click callbacks (e.g., result_callback).

    Similar to async_command but intended for Click group callbacks
    and other non-command async functions.

    Usage:
        @click.group()
        @click.pass_context
        @async_callback
        async def my_group(ctx: click.Context) -> None:
            ctx.obj = await load_config()
    """
    return async_command(f)
