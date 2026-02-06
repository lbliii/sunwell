"""Tool execution engine with dynamic tool registry.

ToolExecutor dispatches tool calls to handlers:
- Core tools → DynamicToolRegistry (self-registering tools)
- Memory tools → MemoryToolHandler (RFC-014)
- Mirror tools → MirrorHandler (RFC-015)
- Expertise tools → ExpertiseToolHandler (RFC-027)
- Sunwell tools → SunwellToolHandlers (RFC-125)

Features:
- Synthetic loading: tools auto-enable on first call
- Idle expiry: unused tools disabled after 5 turns
- Tool hints: inactive tool descriptions for context
- Usage guidance: active tool tips for system prompt
"""


import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Callback type for file write hooks
FileWriteHook = Callable[[Path], Awaitable[None]]

from sunwell.models import ToolCall
from sunwell.tools.core.types import (
    ToolAuditEntry,
    ToolPolicy,
    ToolRateLimits,
    ToolResult,
    ToolUsageTracker,
)
from sunwell.tools.handlers import PathSecurityError

if TYPE_CHECKING:
    from sunwell.features.mirror.handler import MirrorHandler
    from sunwell.knowledge.project import Project
    from sunwell.memory.simulacrum.manager import SimulacrumToolHandler
    from sunwell.memory.simulacrum.memory_tools import MemoryToolHandler
    from sunwell.models import Tool
    from sunwell.tools.providers.expertise import ExpertiseToolHandler
    from sunwell.tools.providers.web_search import WebSearchHandler
    from sunwell.tools.registry import DynamicToolRegistry
    from sunwell.tools.sunwell.handlers import SunwellToolHandlers

# =============================================================================
# Tool Category Constants (O(1) lookup, no per-instance rebuilding)
# =============================================================================

from sunwell.tools.core.constants import (
    EXPERTISE_TOOLS as _EXPERTISE_TOOLS,
)
from sunwell.tools.core.constants import (
    MEMORY_TOOLS as _MEMORY_TOOLS,
)
from sunwell.tools.core.constants import (
    MIRROR_TOOLS as _MIRROR_TOOLS,
)
from sunwell.tools.core.constants import (
    SIMULACRUM_TOOLS as _SIMULACRUM_TOOLS,
)
from sunwell.tools.core.constants import (
    SUNWELL_TOOLS as _SUNWELL_TOOLS,
)
from sunwell.tools.core.constants import (
    WEB_TOOLS as _WEB_TOOLS,
)


@dataclass(slots=True)
class ToolExecutor:
    """Execute tool calls via dynamic tool registry.

    Routes tool calls to appropriate handlers:
    - Core tools → DynamicToolRegistry (self-registering tools from implementations/)
    - Memory tools → MemoryToolHandler (RFC-014)
    - Mirror tools → MirrorHandler (RFC-015)
    - Expertise tools → ExpertiseToolHandler (RFC-027)
    - Sunwell tools → SunwellToolHandlers (RFC-125)

    Features:
    - Synthetic loading: tools auto-enable on first call
    - Idle expiry: unused tools disabled after 5 turns
    - Tool hints: inactive tool descriptions for context
    - Usage guidance: active tool tips for system prompt

    Args:
        project: Project instance with validated root (RFC-117, required)
        memory_handler: For memory tools (RFC-014)
        policy: Tool execution policy (trust level, allowed tools)
        audit_path: Where to write audit logs (None to disable)
    """

    # RFC-117: Use project for validated workspace context
    project: Project
    memory_handler: MemoryToolHandler | None = None
    headspace_handler: SimulacrumToolHandler | None = None
    web_search_handler: WebSearchHandler | None = None
    mirror_handler: MirrorHandler | None = None
    expertise_handler: ExpertiseToolHandler | None = None
    sunwell_handler: SunwellToolHandlers | None = None
    policy: ToolPolicy | None = None
    audit_path: Path | None = None

    # RFC-123: Convergence hook
    on_file_write: Callable[[Path], Awaitable[None]] | None = None
    """Hook called after successful write_file or edit_file operations."""

    # Internal state
    _rate_limits: ToolRateLimits = field(default_factory=ToolRateLimits, init=False)
    _audit_entries: list[ToolAuditEntry] = field(default_factory=list, init=False)
    _resolved_workspace: Path | None = field(default=None, init=False)

    # Dynamic Tool Registry
    _registry: DynamicToolRegistry | None = field(default=None, init=False)
    """Dynamic tool registry for self-registering tools."""

    _usage_tracker: ToolUsageTracker | None = field(default=None, init=False)
    """Tool usage tracker for idle expiry."""

    def __post_init__(self) -> None:
        """Initialize dynamic tool registry."""
        # RFC-117: Resolve workspace from project
        workspace = self.project.root

        # Store resolved workspace for internal use
        self._resolved_workspace = workspace

        # Initialize rate limits from policy
        if self.policy and self.policy.rate_limits:
            self._rate_limits = self.policy.rate_limits

        # Initialize dynamic tool registry
        self._init_registry(workspace)


    # =========================================================================
    # Dynamic Tool Registry
    # =========================================================================

    def _init_registry(self, workspace: Path) -> None:
        """Initialize the dynamic tool registry.

        Creates a DynamicToolRegistry, discovers tools from implementations/,
        and sets up usage tracking for idle expiry.

        Args:
            workspace: Workspace root for tool context
        """
        from sunwell.tools.registry import DynamicToolRegistry

        # Create registry with rich context
        self._registry = DynamicToolRegistry(
            project=self.project,
            memory_store=(
                self.memory_handler.store
                if self.memory_handler and hasattr(self.memory_handler, "store")
                else None
            ),
            llm_provider=None,  # Can be set later if needed
        )

        # Discover tools from implementations package
        self._registry.discover()

        # Initialize usage tracker for idle expiry
        self._usage_tracker = ToolUsageTracker()

    @property
    def registry(self) -> DynamicToolRegistry:
        """Access the dynamic tool registry."""
        if not self._registry:
            raise RuntimeError("Registry not initialized")
        return self._registry

    def get_tool_hints(self) -> dict[str, str]:
        """Get hints for inactive tools.

        Returns:
            Dict mapping tool name to simple description for inactive tools
        """
        return self._registry.get_hints() if self._registry else {}

    def get_tool_guidance(self) -> str:
        """Get usage guidance for active tools.

        Returns:
            Formatted guidance string for system prompt
        """
        return self._registry.get_active_guidance() if self._registry else ""

    def advance_turn(self) -> list[str]:
        """Advance turn counter and expire idle tools.

        Call this at the end of each model response turn.

        Returns:
            List of tool names that were disabled due to inactivity
        """
        if not self._usage_tracker or not self._registry:
            return []

        expired = self._usage_tracker.advance_turn()
        for name in expired:
            if self._registry.is_known(name):
                self._registry.disable(name)

        return expired

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names (active + known)."""
        if not self._registry:
            return []
        return self._registry.list_all_tools()

    def get_tool_definitions(self) -> tuple[Tool, ...]:
        """Get Tool definitions for active tools.

        Returns Tool objects with name, description, and JSON Schema parameters.
        Use this when passing tools to model.generate(tools=...).
        """
        if not self._registry:
            return ()
        return self._registry.get_active_schemas()

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            ToolResult with success status, output, and metadata
        """
        start = time.monotonic()

        # RFC-014: Route memory tools to memory handler
        if tool_call.name in _MEMORY_TOOLS:
            if self.memory_handler:
                try:
                    output = await self.memory_handler.handle(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, True, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Memory tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Memory tools not configured. Set memory_handler on ToolExecutor.",
                )

        # RFC-014: Route headspace tools to headspace handler
        if tool_call.name in _SIMULACRUM_TOOLS:
            if self.headspace_handler:
                try:
                    output = await self.headspace_handler.handle(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, True, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Simulacrum tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Simulacrum tools not configured. "
                    "Set headspace_handler on ToolExecutor.",
                )

        # RFC-015: Route mirror tools to mirror handler
        if tool_call.name in _MIRROR_TOOLS:
            if self.mirror_handler:
                try:
                    output = await self.mirror_handler.handle(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, True, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Mirror tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Mirror tools not configured. Enable with --mirror flag.",
                )

        # RFC-027: Route expertise tools to expertise handler
        if tool_call.name in _EXPERTISE_TOOLS:
            if self.expertise_handler:
                try:
                    output = await self.expertise_handler.handle(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, True, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Expertise tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Expertise tools not configured. Set expertise_handler on ToolExecutor.",
                )

        # RFC-125: Route Sunwell self-access tools to sunwell handler
        if tool_call.name in _SUNWELL_TOOLS:
            if self.sunwell_handler:
                try:
                    result = await self._execute_sunwell_tool(tool_call)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, result.success, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=result.success,
                        output=result.output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Sunwell tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Sunwell tools not configured. Set sunwell_handler on ToolExecutor.",
                )

        # Route web tools to web_search_handler
        if tool_call.name in _WEB_TOOLS:
            if self.web_search_handler:
                try:
                    if tool_call.name == "web_search":
                        output = await self.web_search_handler.web_search(
                            tool_call.arguments,
                        )
                    elif tool_call.name == "web_fetch":
                        output = await self.web_search_handler.web_fetch(
                            tool_call.arguments,
                        )
                    else:
                        output = f"Unknown web tool: {tool_call.name}"
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, True, elapsed_ms)
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    self._log_audit(tool_call, False, elapsed_ms, str(e))
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Web tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Web tools not configured. Set web_search_handler on ToolExecutor.",
                )

        # Check rate limits
        if not self._rate_limits.check_tool_call():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Rate limit exceeded. Please wait before making more tool calls.",
            )

        # Additional rate limit checks for specific tools
        if tool_call.name == "write_file":
            content = tool_call.arguments.get("content", "")
            if not self._rate_limits.check_file_write(len(content)):
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="File write rate limit exceeded.",
                )

        if tool_call.name == "edit_file":
            new_content = tool_call.arguments.get("new_content", "")
            if not self._rate_limits.check_file_write(len(new_content)):
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="File edit rate limit exceeded.",
                )

        if tool_call.name == "run_command" and not self._rate_limits.check_shell_command():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Shell command rate limit exceeded.",
            )

        # Execute via dynamic tool registry (synthetic loading)
        if not self._registry:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Tool registry not initialized.",
            )

        if not self._registry.is_known(tool_call.name):
            available = ", ".join(self._registry.list_all_tools())
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Unknown tool: {tool_call.name}. Available: {available}",
            )

        try:
            # Synthetic loading: auto_enable=True means tools load on first call
            output = await self._registry.execute(
                tool_call.name,
                tool_call.arguments,
                auto_enable=True,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Track usage for idle expiry
            if self._usage_tracker:
                self._usage_tracker.record_use(tool_call.name)

            # RFC-123: Fire convergence hook after successful file writes
            await self._fire_write_hook(tool_call)

            # Audit log
            self._log_audit(tool_call, True, elapsed_ms)

            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                output=output,
                execution_time_ms=elapsed_ms,
            )
        except PathSecurityError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Permission denied: {e}",
            )
        except PermissionError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Permission denied: {e}",
            )
        except FileNotFoundError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Not found: {e}",
            )
        except TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, "Timeout")
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Tool execution timed out",
            )
        except KeyError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Tool error: {e}",
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_audit(tool_call, False, elapsed_ms, str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Error: {type(e).__name__}: {e}",
            )

    async def execute_batch(
        self,
        tool_calls: Sequence[ToolCall],
        parallel: bool = False,
    ) -> tuple[ToolResult, ...]:
        """Execute multiple tool calls.

        Args:
            tool_calls: Tool calls to execute
            parallel: If True, execute concurrently (use with caution for
                     read-only operations only)

        Returns:
            Tuple of ToolResult objects in the same order as input
        """
        if parallel:
            results = await asyncio.gather(*[
                self.execute(tc) for tc in tool_calls
            ])
            return tuple(results)
        else:
            results = []
            for tc in tool_calls:
                results.append(await self.execute(tc))
            return tuple(results)

    def _sanitize_arguments(self, tool_name: str, args: dict) -> dict:
        """Sanitize arguments for audit logging (remove sensitive data)."""
        sanitized = dict(args)

        # Don't log file contents
        if tool_name == "write_file" and "content" in sanitized:
            content_len = len(sanitized["content"])
            sanitized["content"] = f"<{content_len} bytes>"

        # Don't log edit_file content (both old and new)
        if tool_name == "edit_file":
            if "old_content" in sanitized:
                old_len = len(sanitized["old_content"])
                sanitized["old_content"] = f"<{old_len} bytes>"
            if "new_content" in sanitized:
                new_len = len(sanitized["new_content"])
                sanitized["new_content"] = f"<{new_len} bytes>"

        return sanitized

    def _log_audit(
        self,
        tool_call: ToolCall,
        success: bool,
        execution_time_ms: int,
        error: str | None = None,
    ) -> None:
        """Log tool execution for audit and self-analysis (RFC-085)."""
        entry = ToolAuditEntry(
            timestamp=datetime.now(),
            tool_name=tool_call.name,
            arguments=self._sanitize_arguments(tool_call.name, tool_call.arguments),
            success=success,
            execution_time_ms=execution_time_ms,
            error=error,
        )
        self._audit_entries.append(entry)

        # Write to file if audit path configured
        if self.audit_path:
            self._write_audit_entry(entry)

        # RFC-085: Record execution event to Self.analysis for pattern detection
        try:
            from sunwell.features.mirror.self import Self
            from sunwell.features.mirror.self.types import ExecutionEvent

            Self.get().analysis.record_execution(ExecutionEvent(
                tool_name=tool_call.name,
                success=success,
                latency_ms=execution_time_ms,
                error=error,
                timestamp=entry.timestamp,
            ))
        except Exception:
            # Don't let analysis recording failures break tool execution
            pass

    def _write_audit_entry(self, entry: ToolAuditEntry) -> None:
        """Write audit entry to file."""
        # Create audit directory
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Write to daily log file (JSONL format)
        log_file = self.audit_path / f"tools-{entry.timestamp.strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    async def _fire_write_hook(self, tool_call: ToolCall) -> None:
        """Fire on_file_write hook if this was a file mutation (RFC-123).

        Called after successful write_file or edit_file operations.
        Hook is async to allow convergence validation to run.

        Args:
            tool_call: The tool call that just completed
        """
        if not self.on_file_write:
            return

        if tool_call.name not in ("write_file", "edit_file"):
            return

        path_str = tool_call.arguments.get("path", "")
        if not path_str:
            return

        # Resolve path relative to workspace (use cached value)
        path = self.project.root / path_str

        await self.on_file_write(path)

    def get_audit_log(self) -> list[ToolAuditEntry]:
        """Get all audit entries for this session."""
        return list(self._audit_entries)

    def get_stats(self) -> dict:
        """Get execution statistics."""
        total = len(self._audit_entries)
        successful = sum(1 for e in self._audit_entries if e.success)
        failed = total - successful

        total_time = sum(e.execution_time_ms for e in self._audit_entries)
        avg_time = total_time / total if total > 0 else 0

        tool_counts = {}
        for e in self._audit_entries:
            tool_counts[e.tool_name] = tool_counts.get(e.tool_name, 0) + 1

        return {
            "total_calls": total,
            "successful": successful,
            "failed": failed,
            "total_time_ms": total_time,
            "avg_time_ms": round(avg_time, 1),
            "by_tool": tool_counts,
        }

    async def _execute_sunwell_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a Sunwell self-access tool (RFC-125).

        Routes tool calls to the appropriate handler method based on tool name.
        """
        handler_map = {
            "sunwell_intel_decisions": self.sunwell_handler.handle_intel_decisions,
            "sunwell_intel_failures": self.sunwell_handler.handle_intel_failures,
            "sunwell_intel_patterns": self.sunwell_handler.handle_intel_patterns,
            "sunwell_search_semantic": self.sunwell_handler.handle_search_semantic,
            "sunwell_lineage_file": self.sunwell_handler.handle_lineage_file,
            "sunwell_lineage_impact": self.sunwell_handler.handle_lineage_impact,
            "sunwell_weakness_scan": self.sunwell_handler.handle_weakness_scan,
            "sunwell_weakness_preview": self.sunwell_handler.handle_weakness_preview,
            "sunwell_self_modules": self.sunwell_handler.handle_self_modules,
            "sunwell_self_search": self.sunwell_handler.handle_self_search,
            "sunwell_self_read": self.sunwell_handler.handle_self_read,
            "sunwell_workflow_chains": self.sunwell_handler.handle_workflow_chains,
            "sunwell_workflow_route": self.sunwell_handler.handle_workflow_route,
        }

        handler = handler_map.get(tool_call.name)
        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Unknown Sunwell tool: {tool_call.name}",
            )

        return await handler(**tool_call.arguments)
