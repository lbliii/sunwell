"""Execution hooks for tool instrumentation.

Provides:
- ExecutionHook: Protocol for pre/post execution hooks
- HookManager: Manages multiple hooks
- Built-in hooks: metrics, logging
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sunwell.tools.observability.metrics import MetricsCollector, get_metrics_collector

logger = logging.getLogger(__name__)


@runtime_checkable
class ExecutionHook(Protocol):
    """Protocol for tool execution hooks.

    Hooks are called before and after tool execution to enable:
    - Metrics collection
    - Logging
    - Tracing
    - Custom instrumentation
    """

    def pre_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Called before tool execution.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments

        Returns:
            Context dict to pass to post_execute
        """
        ...

    def post_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        success: bool,
        context: dict[str, Any],
    ) -> None:
        """Called after tool execution.

        Args:
            tool_name: Name of the tool called
            arguments: Tool arguments
            result: Tool result (output string or error)
            success: Whether execution succeeded
            context: Context dict from pre_execute
        """
        ...


@dataclass
class HookManager:
    """Manages execution hooks for tool calls.

    Example:
        manager = HookManager()
        manager.add_hook(create_metrics_hook())
        manager.add_hook(create_logging_hook())

        # In tool executor:
        ctx = manager.pre_execute("write_file", args)
        try:
            result = await handler(args)
            manager.post_execute("write_file", args, result, True, ctx)
        except Exception as e:
            manager.post_execute("write_file", args, str(e), False, ctx)
            raise
    """

    _hooks: list[ExecutionHook] = field(default_factory=list)

    def add_hook(self, hook: ExecutionHook) -> None:
        """Add a hook to the manager.

        Args:
            hook: Hook to add
        """
        self._hooks.append(hook)

    def remove_hook(self, hook: ExecutionHook) -> bool:
        """Remove a hook from the manager.

        Args:
            hook: Hook to remove

        Returns:
            True if hook was found and removed
        """
        try:
            self._hooks.remove(hook)
            return True
        except ValueError:
            return False

    def pre_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call all pre_execute hooks.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments

        Returns:
            Combined context from all hooks
        """
        combined_context: dict[str, Any] = {}

        for hook in self._hooks:
            try:
                ctx = hook.pre_execute(tool_name, arguments)
                if ctx:
                    combined_context.update(ctx)
            except Exception as e:
                logger.warning("Hook pre_execute failed: %s", e)

        return combined_context

    def post_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        success: bool,
        context: dict[str, Any],
    ) -> None:
        """Call all post_execute hooks.

        Args:
            tool_name: Name of the tool called
            arguments: Tool arguments
            result: Tool result
            success: Whether execution succeeded
            context: Combined context from pre_execute
        """
        for hook in self._hooks:
            try:
                hook.post_execute(tool_name, arguments, result, success, context)
            except Exception as e:
                logger.warning("Hook post_execute failed: %s", e)


# =============================================================================
# Built-in Hooks
# =============================================================================


@dataclass
class MetricsHook:
    """Hook that records tool metrics.

    Records:
    - Call count
    - Success/failure
    - Latency
    - Bytes written (for file tools)
    """

    collector: MetricsCollector = field(default_factory=get_metrics_collector)

    def pre_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Record start time."""
        return {"start_time": time.time()}

    def post_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        success: bool,
        context: dict[str, Any],
    ) -> None:
        """Record metrics."""
        start_time = context.get("start_time", time.time())
        latency_ms = (time.time() - start_time) * 1000

        # Estimate bytes written for file tools
        bytes_written = 0
        if tool_name in ("write_file", "edit_file", "patch_file"):
            content = arguments.get("content", arguments.get("new_content", ""))
            if isinstance(content, str):
                bytes_written = len(content)

        self.collector.record_call(
            tool_name,
            success=success,
            latency_ms=latency_ms,
            bytes_written=bytes_written,
        )


@dataclass
class LoggingHook:
    """Hook that logs tool execution.

    Logs:
    - Tool name and arguments (sanitized)
    - Success/failure
    - Latency
    - Result summary
    """

    log_level: int = logging.DEBUG
    log_arguments: bool = True
    max_result_length: int = 200

    def _sanitize_arguments(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Sanitize arguments for logging (remove sensitive data)."""
        sanitized = dict(args)

        # Don't log file contents
        if tool_name == "write_file" and "content" in sanitized:
            content_len = len(sanitized["content"])
            sanitized["content"] = f"<{content_len} bytes>"

        if tool_name == "edit_file":
            if "old_content" in sanitized:
                old_len = len(sanitized["old_content"])
                sanitized["old_content"] = f"<{old_len} bytes>"
            if "new_content" in sanitized:
                new_len = len(sanitized["new_content"])
                sanitized["new_content"] = f"<{new_len} bytes>"

        if tool_name == "patch_file" and "diff" in sanitized:
            diff_len = len(sanitized["diff"])
            sanitized["diff"] = f"<{diff_len} bytes>"

        return sanitized

    def pre_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Log tool call start."""
        if self.log_arguments:
            sanitized = self._sanitize_arguments(tool_name, arguments)
            logger.log(self.log_level, "Tool call: %s(%s)", tool_name, sanitized)
        else:
            logger.log(self.log_level, "Tool call: %s", tool_name)

        return {"start_time": time.time()}

    def post_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        success: bool,
        context: dict[str, Any],
    ) -> None:
        """Log tool call result."""
        start_time = context.get("start_time", time.time())
        latency_ms = (time.time() - start_time) * 1000

        result_str = str(result)
        if len(result_str) > self.max_result_length:
            result_str = result_str[:self.max_result_length] + "..."

        if success:
            logger.log(
                self.log_level,
                "Tool %s completed in %.1fms: %s",
                tool_name,
                latency_ms,
                result_str,
            )
        else:
            logger.warning(
                "Tool %s failed in %.1fms: %s",
                tool_name,
                latency_ms,
                result_str,
            )


def create_metrics_hook(collector: MetricsCollector | None = None) -> MetricsHook:
    """Create a metrics collection hook.

    Args:
        collector: Optional custom metrics collector

    Returns:
        Configured MetricsHook
    """
    if collector:
        return MetricsHook(collector=collector)
    return MetricsHook()


def create_logging_hook(
    log_level: int = logging.DEBUG,
    log_arguments: bool = True,
) -> LoggingHook:
    """Create a logging hook.

    Args:
        log_level: Logging level (default: DEBUG)
        log_arguments: Whether to log arguments (default: True)

    Returns:
        Configured LoggingHook
    """
    return LoggingHook(log_level=log_level, log_arguments=log_arguments)
