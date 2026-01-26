"""Tests for the unified async runner module."""

import asyncio

import pytest

from sunwell.interface.cli.core.async_runner import async_command, run_async


class TestRunAsync:
    """Tests for run_async function."""

    def test_run_async_executes_coroutine(self) -> None:
        """run_async executes a coroutine and returns result."""

        async def simple_coro() -> str:
            return "success"

        result = run_async(simple_coro())
        assert result == "success"

    def test_run_async_propagates_exceptions(self) -> None:
        """run_async propagates exceptions from coroutine."""

        async def failing_coro() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(failing_coro())

    def test_run_async_handles_async_operations(self) -> None:
        """run_async properly handles async sleep operations."""

        async def async_sleep_coro() -> str:
            await asyncio.sleep(0.01)
            return "completed"

        result = run_async(async_sleep_coro())
        assert result == "completed"


class TestAsyncCommand:
    """Tests for async_command decorator."""

    def test_async_command_wraps_function(self) -> None:
        """async_command creates a synchronous wrapper."""

        @async_command
        async def my_async_func(x: int, y: int) -> int:
            return x + y

        # Call as synchronous function
        result = my_async_func(2, 3)
        assert result == 5

    def test_async_command_preserves_function_name(self) -> None:
        """async_command preserves the original function name."""

        @async_command
        async def named_function() -> None:
            pass

        assert named_function.__name__ == "named_function"

    def test_async_command_preserves_docstring(self) -> None:
        """async_command preserves the original function docstring."""

        @async_command
        async def documented_function() -> None:
            """This is the docstring."""
            pass

        assert documented_function.__doc__ == "This is the docstring."

    def test_async_command_handles_exceptions(self) -> None:
        """async_command propagates exceptions from wrapped function."""

        @async_command
        async def error_function() -> None:
            raise RuntimeError("wrapped error")

        with pytest.raises(RuntimeError, match="wrapped error"):
            error_function()

    def test_async_command_handles_kwargs(self) -> None:
        """async_command properly passes keyword arguments."""

        @async_command
        async def kwarg_function(a: int, b: int = 10) -> int:
            return a + b

        assert kwarg_function(5) == 15
        assert kwarg_function(5, b=20) == 25
        assert kwarg_function(a=3, b=7) == 10
