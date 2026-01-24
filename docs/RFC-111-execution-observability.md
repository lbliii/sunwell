# RFC-111: Execution Observability — Hooks, Attribution & Audit Trail

**Status**: 🚧 Draft  
**Author**: AI Assistant  
**Created**: 2026-01-23  
**Breaking**: No  
**Priority**: P1 — High Value, Low Risk  
**Inspired By**: Claude Agent SDK patterns (research-agent, email-agent demos)

---

## Summary

Add three observability primitives inspired by Anthropic's Claude Agent SDK:

1. **Tool Hooks** — Pre/post interceptors for all tool calls
2. **Hierarchical Attribution** — Track which task/phase spawned each tool call  
3. **JSONL Audit Trail** — Persistent, structured logs per session

These patterns enable debugging, compliance, security scanning, and operational visibility without modifying existing tools or event handlers.

---

## Problem Statement

### What's Missing

Sunwell's event system is excellent for real-time UI streaming (60+ event types, UI hints, factories). But:

| Need | Current State | Gap |
|------|--------------|-----|
| **Debug tool calls** | Must modify each tool | No central interception point |
| **Trace which task caused what** | `task_id` in events | No parent→child attribution chain |
| **Offline audit** | Events stream to UI | No persistent file per session |
| **Custom pre-execution checks** | Hardcoded in tools | No plugin architecture |

### Evidence from Claude SDK

The research-agent demo implements clean observability patterns:

```python
# Hooks intercept ALL tool calls without modifying tools
hooks = {
    'PreToolUse': [HookMatcher(matcher=None, hooks=[tracker.pre_tool_use_hook])],
    'PostToolUse': [HookMatcher(matcher=None, hooks=[tracker.post_tool_use_hook])]
}

# Attribution links tool calls to their spawning context
{"agent_id": "RESEARCHER-1", "tool_name": "WebSearch", "parent_tool_use_id": "task_123"}

# JSONL files enable offline analysis
logs/session_20260123/tool_calls.jsonl
```

---

## Solution

### 1. Tool Hooks API

#### Types

```python
# sunwell/tools/hooks.py

from dataclasses import dataclass
from typing import Any, Callable, Awaitable, Literal
from enum import Enum


class HookAction(Enum):
    """What to do after a hook runs."""
    CONTINUE = "continue"      # Proceed with execution
    SKIP = "skip"              # Skip this tool call (pre-hook only)
    ABORT = "abort"            # Abort entire task


@dataclass(frozen=True, slots=True)
class ToolUseContext:
    """Context passed to tool hooks."""
    
    tool_name: str
    """Name of the tool being called."""
    
    tool_input: dict[str, Any]
    """Input parameters to the tool."""
    
    tool_use_id: str
    """Unique ID for this tool invocation."""
    
    task_id: str | None
    """ID of the task that initiated this call."""
    
    parent_tool_use_id: str | None
    """ID of parent tool call if nested (e.g., subagent spawn)."""
    
    phase: str | None
    """Execution phase: 'planning', 'execution', 'validation', 'fix'."""


@dataclass(frozen=True, slots=True)
class PreHookResult:
    """Result from a pre-tool-use hook."""
    
    action: HookAction = HookAction.CONTINUE
    """Whether to continue, skip, or abort."""
    
    modified_input: dict[str, Any] | None = None
    """Optional modified input to pass to tool."""
    
    metadata: dict[str, Any] | None = None
    """Optional metadata to attach to tool call record."""


@dataclass(frozen=True, slots=True)
class PostHookResult:
    """Result from a post-tool-use hook."""
    
    action: HookAction = HookAction.CONTINUE
    """Whether to continue or abort."""
    
    modified_output: Any | None = None
    """Optional modified output to return."""
    
    metadata: dict[str, Any] | None = None
    """Optional metadata to attach to tool call record."""


# Hook function signatures
PreToolHook = Callable[[ToolUseContext], Awaitable[PreHookResult]]
PostToolHook = Callable[[ToolUseContext, Any], Awaitable[PostHookResult]]


@dataclass
class HookMatcher:
    """Matches tool calls to hooks."""
    
    pattern: str | None = None
    """Tool name pattern (glob). None = match all."""
    
    phases: tuple[str, ...] | None = None
    """Only match these phases. None = all phases."""
    
    pre_hooks: tuple[PreToolHook, ...] = ()
    """Hooks to run before tool execution."""
    
    post_hooks: tuple[PostToolHook, ...] = ()
    """Hooks to run after tool execution."""
    
    def matches(self, ctx: ToolUseContext) -> bool:
        """Check if this matcher applies to the context."""
        if self.pattern is not None:
            import fnmatch
            if not fnmatch.fnmatch(ctx.tool_name, self.pattern):
                return False
        if self.phases is not None and ctx.phase not in self.phases:
            return False
        return True


@dataclass
class HookRegistry:
    """Registry of tool hooks."""
    
    matchers: list[HookMatcher] = field(default_factory=list)
    
    def register(self, matcher: HookMatcher) -> None:
        """Register a hook matcher."""
        self.matchers.append(matcher)
    
    def get_pre_hooks(self, ctx: ToolUseContext) -> list[PreToolHook]:
        """Get all pre-hooks that match the context."""
        hooks = []
        for matcher in self.matchers:
            if matcher.matches(ctx):
                hooks.extend(matcher.pre_hooks)
        return hooks
    
    def get_post_hooks(self, ctx: ToolUseContext) -> list[PostToolHook]:
        """Get all post-hooks that match the context."""
        hooks = []
        for matcher in self.matchers:
            if matcher.matches(ctx):
                hooks.extend(matcher.post_hooks)
        return hooks
```

#### Integration with Tool Executor

```python
# sunwell/tools/executor.py (modifications)

class ToolExecutor:
    """Unified tool executor with hook support."""
    
    def __init__(
        self,
        tools: dict[str, Tool],
        hook_registry: HookRegistry | None = None,
    ):
        self.tools = tools
        self.hooks = hook_registry or HookRegistry()
    
    async def execute(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        task_id: str | None = None,
        parent_tool_use_id: str | None = None,
        phase: str | None = None,
    ) -> Any:
        """Execute a tool with hook interception."""
        
        tool_use_id = generate_tool_use_id()
        
        ctx = ToolUseContext(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
            task_id=task_id,
            parent_tool_use_id=parent_tool_use_id,
            phase=phase,
        )
        
        # Run pre-hooks
        final_input = tool_input
        for hook in self.hooks.get_pre_hooks(ctx):
            result = await hook(ctx)
            if result.action == HookAction.SKIP:
                return None  # Skip this tool call
            if result.action == HookAction.ABORT:
                raise HookAbortError(f"Pre-hook aborted tool call: {tool_name}")
            if result.modified_input is not None:
                final_input = result.modified_input
        
        # Execute tool
        tool = self.tools[tool_name]
        output = await tool.execute(final_input)
        
        # Run post-hooks
        final_output = output
        for hook in self.hooks.get_post_hooks(ctx):
            result = await hook(ctx, final_output)
            if result.action == HookAction.ABORT:
                raise HookAbortError(f"Post-hook aborted after tool call: {tool_name}")
            if result.modified_output is not None:
                final_output = result.modified_output
        
        return final_output
```

---

### 2. Hierarchical Attribution

Add `parent_tool_use_id` to track nested execution contexts:

```python
# sunwell/adaptive/events.py (additions)

@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """Complete record of a tool call with attribution."""
    
    tool_use_id: str
    """Unique ID for this invocation."""
    
    tool_name: str
    """Name of the tool."""
    
    tool_input: dict[str, Any]
    """Input parameters."""
    
    task_id: str | None
    """Task that initiated this call."""
    
    parent_tool_use_id: str | None
    """Parent tool call ID for nested execution."""
    
    phase: str | None
    """Execution phase."""
    
    timestamp: float
    """Unix timestamp."""
    
    # Filled after execution
    output: Any | None = None
    """Tool output (may be truncated for large outputs)."""
    
    duration_ms: int | None = None
    """Execution duration in milliseconds."""
    
    error: str | None = None
    """Error message if failed."""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata from hooks."""
```

#### Attribution Tracking

```python
# sunwell/tools/attribution.py

from contextvars import ContextVar
from dataclasses import dataclass, field


# Context variable for current execution context
_current_context: ContextVar[ExecutionContext | None] = ContextVar(
    "execution_context", default=None
)


@dataclass
class ExecutionContext:
    """Tracks current execution context for attribution."""
    
    task_id: str | None = None
    """Current task ID."""
    
    tool_use_id: str | None = None
    """Current tool use ID (for nested calls)."""
    
    phase: str | None = None
    """Current phase."""
    
    depth: int = 0
    """Nesting depth."""


def get_current_context() -> ExecutionContext | None:
    """Get current execution context."""
    return _current_context.get()


def set_context(ctx: ExecutionContext) -> None:
    """Set execution context."""
    _current_context.set(ctx)


class AttributionScope:
    """Context manager for tracking execution attribution."""
    
    def __init__(
        self,
        task_id: str | None = None,
        tool_use_id: str | None = None,
        phase: str | None = None,
    ):
        self.task_id = task_id
        self.tool_use_id = tool_use_id
        self.phase = phase
        self.previous: ExecutionContext | None = None
    
    def __enter__(self) -> ExecutionContext:
        self.previous = get_current_context()
        
        # Inherit from parent context
        parent_tool_use_id = None
        depth = 0
        if self.previous:
            parent_tool_use_id = self.previous.tool_use_id
            depth = self.previous.depth + 1
        
        ctx = ExecutionContext(
            task_id=self.task_id or (self.previous.task_id if self.previous else None),
            tool_use_id=self.tool_use_id,
            phase=self.phase or (self.previous.phase if self.previous else None),
            depth=depth,
        )
        set_context(ctx)
        return ctx
    
    def __exit__(self, *args) -> None:
        set_context(self.previous)
```

---

### 3. JSONL Audit Trail

Persistent, structured logs for every session:

```python
# sunwell/audit/trail.py

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditTrail:
    """JSONL audit trail for a session.
    
    Writes structured events to a JSONL file for offline analysis,
    debugging, and compliance.
    
    Output: .sunwell/audit/{session_id}/events.jsonl
    """
    
    def __init__(
        self,
        session_id: str,
        base_dir: Path | None = None,
    ):
        self.session_id = session_id
        self.base_dir = base_dir or Path(".sunwell/audit")
        self.session_dir = self.base_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self.events_file = self.session_dir / "events.jsonl"
        self.tool_calls_file = self.session_dir / "tool_calls.jsonl"
        
        self._events_handle = open(self.events_file, "a", encoding="utf-8")
        self._tools_handle = open(self.tool_calls_file, "a", encoding="utf-8")
        
        # Write session start marker
        self._write_event({
            "event": "session_start",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        })
    
    def log_event(self, event: AgentEvent) -> None:
        """Log an agent event."""
        self._write_event({
            "event": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp,
        })
    
    def log_tool_call(self, record: ToolCallRecord) -> None:
        """Log a tool call record."""
        self._write_tool({
            "event": "tool_call",
            "tool_use_id": record.tool_use_id,
            "tool_name": record.tool_name,
            "task_id": record.task_id,
            "parent_tool_use_id": record.parent_tool_use_id,
            "phase": record.phase,
            "timestamp": record.timestamp,
            "input_preview": _truncate(str(record.tool_input), 500),
            "output_preview": _truncate(str(record.output), 500) if record.output else None,
            "duration_ms": record.duration_ms,
            "error": record.error,
            "metadata": record.metadata,
        })
    
    def log_tool_start(self, ctx: ToolUseContext) -> None:
        """Log tool call start (from pre-hook)."""
        self._write_tool({
            "event": "tool_call_start",
            "tool_use_id": ctx.tool_use_id,
            "tool_name": ctx.tool_name,
            "task_id": ctx.task_id,
            "parent_tool_use_id": ctx.parent_tool_use_id,
            "phase": ctx.phase,
            "timestamp": datetime.now().isoformat(),
            "input_preview": _truncate(str(ctx.tool_input), 500),
        })
    
    def log_tool_complete(
        self,
        ctx: ToolUseContext,
        output: Any,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """Log tool call completion (from post-hook)."""
        self._write_tool({
            "event": "tool_call_complete",
            "tool_use_id": ctx.tool_use_id,
            "tool_name": ctx.tool_name,
            "success": error is None,
            "duration_ms": duration_ms,
            "output_preview": _truncate(str(output), 500) if output else None,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
    
    def close(self) -> None:
        """Close the audit trail."""
        self._write_event({
            "event": "session_end",
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
        })
        self._events_handle.close()
        self._tools_handle.close()
    
    def _write_event(self, data: dict[str, Any]) -> None:
        self._events_handle.write(json.dumps(data) + "\n")
        self._events_handle.flush()
    
    def _write_tool(self, data: dict[str, Any]) -> None:
        self._tools_handle.write(json.dumps(data) + "\n")
        self._tools_handle.flush()


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis."""
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."
```

#### Built-in Audit Hook

```python
# sunwell/audit/hooks.py

from time import time

from sunwell.audit.trail import AuditTrail
from sunwell.tools.hooks import (
    ToolUseContext,
    PreHookResult,
    PostHookResult,
    HookAction,
)


class AuditHook:
    """Pre-built hook that logs all tool calls to audit trail."""
    
    def __init__(self, audit_trail: AuditTrail):
        self.trail = audit_trail
        self._start_times: dict[str, float] = {}
    
    async def pre_hook(self, ctx: ToolUseContext) -> PreHookResult:
        """Log tool call start."""
        self._start_times[ctx.tool_use_id] = time()
        self.trail.log_tool_start(ctx)
        return PreHookResult(action=HookAction.CONTINUE)
    
    async def post_hook(self, ctx: ToolUseContext, output: Any) -> PostHookResult:
        """Log tool call completion."""
        start = self._start_times.pop(ctx.tool_use_id, time())
        duration_ms = int((time() - start) * 1000)
        
        error = None
        if isinstance(output, Exception):
            error = str(output)
        
        self.trail.log_tool_complete(ctx, output, duration_ms, error)
        return PostHookResult(action=HookAction.CONTINUE)
```

---

### Integration with AdaptiveAgent

```python
# sunwell/adaptive/agent.py (modifications)

@dataclass
class AdaptiveAgent:
    # ... existing fields ...
    
    # RFC-111: Observability
    hook_registry: HookRegistry = field(default_factory=HookRegistry)
    """Tool hook registry."""
    
    audit_trail: AuditTrail | None = None
    """Optional JSONL audit trail."""
    
    enable_audit: bool = False
    """Whether to enable audit logging."""
    
    async def run(self, goal: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with observability."""
        
        # Setup audit trail if enabled
        if self.enable_audit:
            session_id = f"session_{int(time())}"
            self.audit_trail = AuditTrail(session_id)
            
            # Register audit hooks
            audit_hook = AuditHook(self.audit_trail)
            self.hook_registry.register(HookMatcher(
                pattern=None,  # All tools
                pre_hooks=(audit_hook.pre_hook,),
                post_hooks=(audit_hook.post_hook,),
            ))
        
        try:
            async for event in self._run_internal(goal):
                # Log event to audit trail
                if self.audit_trail:
                    self.audit_trail.log_event(event)
                yield event
        finally:
            if self.audit_trail:
                self.audit_trail.close()
```

---

## Example Use Cases

### 1. Security Scanning Hook

```python
async def security_pre_hook(ctx: ToolUseContext) -> PreHookResult:
    """Scan tool inputs for security violations."""
    if ctx.tool_name == "shell":
        command = ctx.tool_input.get("command", "")
        if "rm -rf" in command or "sudo" in command:
            return PreHookResult(
                action=HookAction.ABORT,
                metadata={"violation": "dangerous_command"},
            )
    return PreHookResult(action=HookAction.CONTINUE)

# Register
hook_registry.register(HookMatcher(
    pattern="shell",
    pre_hooks=(security_pre_hook,),
))
```

### 2. Metrics Collection Hook

```python
class MetricsHook:
    def __init__(self):
        self.tool_durations: dict[str, list[float]] = defaultdict(list)
        self.tool_counts: dict[str, int] = defaultdict(int)
    
    async def post_hook(self, ctx: ToolUseContext, output: Any) -> PostHookResult:
        # Track metrics without modifying execution
        self.tool_counts[ctx.tool_name] += 1
        return PostHookResult(action=HookAction.CONTINUE)
```

### 3. Debug Tracing

```python
async def debug_hook(ctx: ToolUseContext) -> PreHookResult:
    """Print all tool calls for debugging."""
    print(f"[{ctx.phase}] {ctx.tool_name}({ctx.tool_input})")
    print(f"  task={ctx.task_id}, parent={ctx.parent_tool_use_id}")
    return PreHookResult(action=HookAction.CONTINUE)
```

### 4. Offline Analysis

```bash
# After a session, analyze tool usage
jq 'select(.event == "tool_call_complete") | {tool: .tool_name, duration: .duration_ms}' \
  .sunwell/audit/session_123/tool_calls.jsonl

# Find all failed tool calls
jq 'select(.success == false)' tool_calls.jsonl

# Trace execution path for a specific task
jq 'select(.task_id == "task_abc")' tool_calls.jsonl
```

---

## Files Changed

| File | Change |
|------|--------|
| `sunwell/tools/hooks.py` | **NEW** — Hook types and registry |
| `sunwell/tools/attribution.py` | **NEW** — Execution context tracking |
| `sunwell/tools/executor.py` | Add hook interception |
| `sunwell/audit/trail.py` | **NEW** — JSONL audit trail |
| `sunwell/audit/hooks.py` | **NEW** — Built-in audit hook |
| `sunwell/adaptive/agent.py` | Add `hook_registry`, `audit_trail`, `enable_audit` |
| `sunwell/adaptive/events.py` | Add `ToolCallRecord` |

---

## Rollout Plan

### Phase 1: Core Types (1 day)
- [ ] Add `sunwell/tools/hooks.py`
- [ ] Add `sunwell/tools/attribution.py`
- [ ] Add `ToolCallRecord` to events

### Phase 2: Integration (1 day)
- [ ] Modify `ToolExecutor` to support hooks
- [ ] Add `AttributionScope` usage in task execution
- [ ] Pass `parent_tool_use_id` through execution path

### Phase 3: Audit Trail (1 day)
- [ ] Add `sunwell/audit/trail.py`
- [ ] Add `sunwell/audit/hooks.py`
- [ ] Integrate with `AdaptiveAgent`

### Phase 4: CLI Flag (0.5 day)
- [ ] Add `--audit` flag to CLI
- [ ] Document audit trail format

---

## Alternatives Considered

### 1. Modify Each Tool

**Rejected**: Requires changing every tool, easy to miss, violates DRY.

### 2. Event-Only Logging

**Rejected**: Events stream to UI but aren't persisted. JSONL enables offline analysis, CI/CD integration, and compliance.

### 3. Database Instead of JSONL

**Rejected**: JSONL is:
- Human-readable (can `cat` the file)
- Git-friendly (can commit audit logs)
- Zero infrastructure (no DB setup)
- Compatible with standard tools (`jq`, `grep`)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Hook overhead | < 1ms per tool call |
| Audit file size | < 100KB per typical session |
| Debugging time reduction | 50% faster to trace issues |
| Zero breaking changes | All existing code works unchanged |

---

## References

- [Claude Agent SDK — Research Agent](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent)
- [Claude Agent SDK — Email Agent](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/email-agent)
- RFC-042: Adaptive Agent
- RFC-089: Security First Skills
- RFC-090: Plan Transparency
