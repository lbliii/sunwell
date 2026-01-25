"""Tool execution engine for RFC-012 tool calling.

ToolExecutor dispatches tool calls to appropriate handlers:
- Built-in tools → CoreToolHandlers
- Skill-derived tools → SkillExecutor (RFC-011)
- Memory tools → MemoryToolHandler (RFC-014)
- Web search tools → WebSearchHandler
- Learned tools → LearnedToolHandler (Phase 6 - future)

RFC-117: Project-centric workspace isolation
- Prefer passing `project` parameter instead of raw `workspace` path
- Project provides validated root path and configuration
- Direct `workspace` parameter still supported for backward compatibility
"""


import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.models.protocol import ToolCall
from sunwell.tools.handlers import CoreToolHandlers, PathSecurityError
from sunwell.tools.types import (
    ToolAuditEntry,
    ToolPolicy,
    ToolRateLimits,
    ToolResult,
)

if TYPE_CHECKING:
    from sunwell.mirror.handler import MirrorHandler
    from sunwell.models.protocol import Tool
    from sunwell.project import Project
    from sunwell.simulacrum.manager import SimulacrumToolHandler
    from sunwell.simulacrum.memory_tools import MemoryToolHandler
    from sunwell.skills.executor import SkillExecutor
    from sunwell.skills.sandbox import ScriptSandbox
    from sunwell.tools.expertise import ExpertiseToolHandler
    from sunwell.tools.sunwell_handlers import SunwellToolHandlers
    from sunwell.tools.web_search import WebSearchHandler


# Type alias for tool handlers
ToolHandler = Callable[[dict], Awaitable[str]]

# =============================================================================
# Tool Category Constants (O(1) lookup, no per-instance rebuilding)
# =============================================================================

# RFC-014: Memory tools (always available regardless of trust level)
_MEMORY_TOOLS: frozenset[str] = frozenset({
    "search_memory", "recall_user_info", "find_related",
    "find_contradictions", "add_learning", "mark_dead_end",
})

# RFC-014: Simulacrum management tools (always available)
_SIMULACRUM_TOOLS: frozenset[str] = frozenset({
    "list_headspaces", "switch_headspace", "create_headspace",
    "suggest_headspace", "query_all_headspaces", "current_headspace",
    "route_query", "spawn_status",  # Auto-spawning tools
    "headspace_health", "archive_headspace", "restore_headspace",  # Lifecycle tools
    "list_archived", "cleanup_headspaces", "shrink_headspace",
})

# Web search tools (require FULL trust level)
_WEB_TOOLS: frozenset[str] = frozenset({
    "web_search", "web_fetch",
})

# RFC-015: Mirror neuron tools (self-introspection and self-improvement)
_MIRROR_TOOLS: frozenset[str] = frozenset({
    # Introspection (DISCOVERY trust)
    "introspect_source", "introspect_lens", "introspect_headspace",
    "introspect_execution",
    # Analysis (READ_ONLY trust)
    "analyze_patterns", "analyze_failures", "analyze_model_performance",
    # Proposals (READ_ONLY trust)
    "propose_improvement", "propose_model_routing", "list_proposals",
    "get_proposal", "submit_proposal",
    # Application (WORKSPACE trust)
    "approve_proposal", "apply_proposal", "rollback_proposal",
})

# RFC-027: Expertise tools (self-directed expertise retrieval)
_EXPERTISE_TOOLS: frozenset[str] = frozenset({
    "get_expertise", "verify_against_expertise", "list_expertise_areas",
})

# RFC-125: Sunwell self-access tools
_SUNWELL_TOOLS: frozenset[str] = frozenset({
    "sunwell_intel_decisions", "sunwell_intel_failures", "sunwell_intel_patterns",
    "sunwell_search_semantic", "sunwell_lineage_file", "sunwell_lineage_impact",
    "sunwell_weakness_scan", "sunwell_weakness_preview",
    "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
    "sunwell_workflow_chains", "sunwell_workflow_route",
})


@dataclass(slots=True)
class ToolExecutor:
    """Execute tool calls locally.

    This is a dispatcher that routes tool calls to appropriate handlers:
    - Built-in tools → CoreToolHandlers
    - Skill-derived tools → SkillExecutor (RFC-011)
    - Memory tools → MemoryToolHandler (RFC-014)
    - Learned tools → LearnedToolHandler (future)

    RFC-117: Project-centric workspace isolation
    - Prefer `project` parameter for validated workspace context
    - Falls back to `workspace` for backward compatibility
    - Validates workspace is not Sunwell's own repo

    Args:
        workspace: Root directory for file operations (deprecated, use project)
        project: Project instance with validated root (RFC-117, preferred)
        sandbox: ScriptSandbox for command execution (RFC-011)
        skill_executor: For skill-derived tools
        memory_handler: For memory tools (RFC-014)
        policy: Tool execution policy (trust level, allowed tools)
        audit_path: Where to write audit logs (None to disable)
    """

    # RFC-117: Accept either project or workspace (project preferred)
    workspace: Path | None = None
    project: Project | None = None
    sandbox: ScriptSandbox | None = None
    skill_executor: SkillExecutor | None = None
    memory_handler: MemoryToolHandler | None = None  # RFC-014
    headspace_handler: SimulacrumToolHandler | None = None  # RFC-014: Multi-headspace
    web_search_handler: WebSearchHandler | None = None  # Web search tools
    mirror_handler: MirrorHandler | None = None  # RFC-015: Mirror neurons
    expertise_handler: ExpertiseToolHandler | None = None  # RFC-027: Self-directed expertise
    sunwell_handler: SunwellToolHandlers | None = None  # RFC-125: Agent self-access
    policy: ToolPolicy | None = None
    audit_path: Path | None = None

    # RFC-123: Convergence hook
    on_file_write: Callable[[Path], Awaitable[None]] | None = None
    """Hook called after successful write_file or edit_file operations."""

    # Handler registry
    _handlers: dict[str, ToolHandler] = field(default_factory=dict)
    _core_handlers: CoreToolHandlers | None = field(default=None, init=False)
    _rate_limits: ToolRateLimits = field(default_factory=ToolRateLimits, init=False)
    _audit_entries: list[ToolAuditEntry] = field(default_factory=list, init=False)
    _resolved_workspace: Path | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize core tool handlers."""
        from sunwell.project.validation import (
            ProjectValidationError,
            validate_not_sunwell_repo,
        )

        # RFC-117: Resolve workspace from project or direct parameter
        workspace = self._resolve_workspace()

        # Validate workspace is not Sunwell's own repo
        try:
            validate_not_sunwell_repo(workspace)
        except ProjectValidationError as e:
            raise ProjectValidationError(
                f"{e}\n\nHint: Use --project-root or -p <project-id> to specify a project."
            ) from None

        # Store resolved workspace for internal use
        self._resolved_workspace = workspace

        # Get blocked patterns from policy, project, or defaults
        blocked_patterns = self._get_blocked_patterns()

        # Initialize core tool handlers
        if blocked_patterns is not None:
            self._core_handlers = CoreToolHandlers(
                workspace,
                self.sandbox,
                blocked_patterns=blocked_patterns,
            )
        else:
            self._core_handlers = CoreToolHandlers(
                workspace,
                self.sandbox,
            )

        # Initialize rate limits from policy
        if self.policy and self.policy.rate_limits:
            self._rate_limits = self.policy.rate_limits

        # Register built-in tools (filtered by policy)
        self._register_core_tools()

    def _resolve_workspace(self) -> Path:
        """Resolve workspace from project or direct parameter.

        RFC-117: Project takes precedence over direct workspace.

        Returns:
            Resolved workspace path

        Raises:
            ValueError: If neither project nor workspace is provided
        """
        if self.project is not None:
            return self.project.root

        if self.workspace is not None:
            return self.workspace

        raise ValueError(
            "ToolExecutor requires either 'project' or 'workspace' parameter.\n"
            "Preferred: ToolExecutor(project=resolve_project(...))\n"
            "Legacy: ToolExecutor(workspace=Path('/path/to/project'))"
        )

    def _get_blocked_patterns(self) -> frozenset[str] | None:
        """Get blocked patterns from policy and project.

        Combines patterns from:
        1. Default patterns
        2. Policy blocked_paths
        3. Project protected paths (RFC-117)

        Returns:
            Combined blocked patterns or None to use defaults
        """
        from sunwell.tools.handlers import DEFAULT_BLOCKED_PATTERNS

        patterns: set[str] = set()
        has_custom = False

        # Add policy blocked paths
        if self.policy and self.policy.blocked_paths:
            patterns.update(DEFAULT_BLOCKED_PATTERNS)
            patterns.update(self.policy.blocked_paths)
            has_custom = True

        # Add project protected paths (RFC-117)
        if self.project and self.project.protected_paths:
            if not has_custom:
                patterns.update(DEFAULT_BLOCKED_PATTERNS)
            # Convert protected paths to glob patterns
            for protected in self.project.protected_paths:
                patterns.add(f"**/{protected}/**")
                patterns.add(f"**/{protected}")
            has_custom = True

        return frozenset(patterns) if has_custom else None

    def _register_core_tools(self) -> None:
        """Register built-in tools filtered by policy."""
        # Map tool names to handlers
        all_handlers = {
            # Core file tools
            "read_file": self._core_handlers.read_file,
            "write_file": self._core_handlers.write_file,
            "edit_file": self._core_handlers.edit_file,  # RFC-041: Surgical editing
            "list_files": self._core_handlers.list_files,
            "search_files": self._core_handlers.search_files,
            "run_command": self._core_handlers.run_command,
            "mkdir": self._core_handlers.mkdir,
            # Git tools (RFC-024)
            "git_init": self._core_handlers.git_init,
            "git_info": self._core_handlers.git_info,
            "git_status": self._core_handlers.git_status,
            "git_diff": self._core_handlers.git_diff,
            "git_log": self._core_handlers.git_log,
            "git_blame": self._core_handlers.git_blame,
            "git_show": self._core_handlers.git_show,
            "git_add": self._core_handlers.git_add,
            "git_restore": self._core_handlers.git_restore,
            "git_commit": self._core_handlers.git_commit,
            "git_branch": self._core_handlers.git_branch,
            "git_checkout": self._core_handlers.git_checkout,
            "git_stash": self._core_handlers.git_stash,
            "git_reset": self._core_handlers.git_reset,
            "git_merge": self._core_handlers.git_merge,
            # Environment tools (RFC-024)
            "get_env": self._core_handlers.get_env,
            "list_env": self._core_handlers.list_env,
        }

        # Filter by policy
        if self.policy:
            allowed = self.policy.get_allowed_tools()
            for name, handler in all_handlers.items():
                if name in allowed:
                    self._handlers[name] = handler
        else:
            # No policy = default to WORKSPACE level
            from sunwell.tools.types import TRUST_LEVEL_TOOLS, ToolTrust
            default_allowed = TRUST_LEVEL_TOOLS[ToolTrust.WORKSPACE]
            for name, handler in all_handlers.items():
                if name in default_allowed:
                    self._handlers[name] = handler

        # Register web search tools if handler provided and policy allows
        if self.web_search_handler:
            allowed = self.policy.get_allowed_tools() if self.policy else set()
            if "web_search" in allowed:
                self._handlers["web_search"] = self.web_search_handler.web_search
            if "web_fetch" in allowed:
                self._handlers["web_fetch"] = self.web_search_handler.web_fetch

    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a custom tool handler.

        Use this to add skill-derived tools or custom extensions.
        """
        self._handlers[name] = handler

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        return list(self._handlers.keys())

    def get_tool_definitions(self) -> tuple[Tool, ...]:
        """Get full Tool definitions for available tools (for native tool calling).

        Returns Tool objects with name, description, and JSON Schema parameters.
        Use this when passing tools to model.generate(tools=...) for reliable
        tool calling instead of text-based prompts.
        """
        from sunwell.tools.builtins import ALL_BUILTIN_TOOLS

        available_names = self._handlers.keys()

        return tuple(
            tool for name, tool in ALL_BUILTIN_TOOLS.items()
            if name in available_names
        )

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

        # Check rate limits
        if not self._rate_limits.check_tool_call():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Rate limit exceeded. Please wait before making more tool calls.",
            )

        # Find handler
        handler = self._handlers.get(tool_call.name)
        if not handler:
            available = ", ".join(self._handlers.keys())
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Unknown tool: {tool_call.name}. Available: {available}",
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

        # Execute handler
        try:
            output = await handler(tool_call.arguments)
            elapsed_ms = int((time.monotonic() - start) * 1000)

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
            from sunwell.self import Self
            from sunwell.self.types import ExecutionEvent

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
        path = self._resolved_workspace / path_str

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
