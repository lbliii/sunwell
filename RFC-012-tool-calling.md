# RFC-012: Arming Sunwell with Lightweight Tool Calling

**Status:** Draft  
**Author:** Sunwell Contributors  
**Created:** 2026-01-15  
**Updated:** 2026-01-15  
**Related:** [RFC-011: Skills](./RFC-011-lenses-with-skills.md)

---

## Summary

Add native tool/function calling support to Sunwell, enabling skills to be executed as **real tools** rather than just instructions. No servers required - tools execute locally within Sunwell's process.

**Key insight:** Skills already define *what* to do. Tool calling lets the LLM *request* execution and *see results*.

**Scope:** This RFC extends RFC-011's skill execution with LLM-driven tool calling. It reuses RFC-011's `ScriptSandbox` for security and `SkillExecutor` for skill-based tool handlers.

---

## Motivation

### Current State: Skills as Instructions

Today, Sunwell skills are "soft" - they provide instructions to the LLM:

```yaml
skills:
  - name: save-document
    instructions: |
      To save content:
      1. Output: SAVE: path/to/file.md
      2. Include content below
```

**Problems:**
- LLM must format output correctly (unreliable)
- LLM can't see if operation succeeded
- No multi-turn tool use (can't chain: read → modify → write)
- Parsing output is fragile

### Proposed: Skills as Callable Tools

With tool calling, skills become executable:

```
User: "Save this as README.md"
     │
     ▼
┌─────────────────────────────────────┐
│ LLM decides to call tool            │
│ tool_calls: [{                      │
│   name: "save-document",            │
│   arguments: {                      │
│     path: "README.md",              │
│     content: "# My Project\n..."    │
│   }                                 │
│ }]                                  │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ Sunwell executes tool LOCALLY       │
│ Path("README.md").write_text(...)   │
│ Returns: "✓ Saved README.md (342b)" │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ LLM sees result, can continue       │
│ "I've saved README.md. Want me to   │
│  also create a LICENSE file?"       │
└─────────────────────────────────────┘
```

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RuntimeEngine                                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │ IntentClassifier│    │ ToolExecutor    │    │ ScriptSandbox           │  │
│  │ (existing)      │    │ (NEW - this RFC)│◄───│ (RFC-011 - reused)      │  │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────────────┘  │
│           │                      │                                           │
│           ▼                      ▼                                           │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │ ModelProtocol   │◄───│ CoreToolHandlers│    │ SkillExecutor           │  │
│  │ (extended)      │    │ (NEW - builtins)│    │ (RFC-011 - skill tools) │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**ToolExecutor vs SkillExecutor**:
- `ToolExecutor`: Dispatches tool calls to handlers, manages tool loop
- `SkillExecutor` (RFC-011): Executes skill-derived tools with lens validation
- `CoreToolHandlers`: Implements built-in tools (read_file, write_file, etc.)

### 1. Extended Model Protocol

Add tools and multi-turn message support to `ModelProtocol`. This version introduces a `text` property to facilitate a smooth migration from the existing `content: str` implementation.

```python
# src/sunwell/models/protocol.py

from typing import Literal, Union


@dataclass(frozen=True, slots=True)
class Message:
    """A conversation message for multi-turn interactions."""
    
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    
    # For assistant messages with tool calls
    tool_calls: tuple["ToolCall", ...] = ()
    
    # For tool result messages
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable tool the LLM can invoke."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    
    @classmethod
    def from_skill(cls, skill: "Skill") -> "Tool":
        """Convert a Sunwell skill to a tool definition."""
        return cls(
            name=skill.name,
            description=skill.description,
            parameters=skill.parameters_schema or {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task to perform with this skill",
                    }
                },
                "required": ["task"],
            },
        )


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation requested by the LLM."""
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Result from model generation.
    
    Migration note: `content` is now `Optional[str]`. 
    Use the `.text` property for backward compatibility.
    """
    content: str | None  # Text response (None when tool_calls present)
    model: str
    tool_calls: tuple[ToolCall, ...] = ()  # Tool requests
    usage: TokenUsage | None = None
    finish_reason: str | None = None
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if this result contains tool calls."""
        return len(self.tool_calls) > 0
    
    @property
    def text(self) -> str:
        """Get content as string, defaulting to empty string.
        
        Recommended for all existing code using result.content.
        """
        return self.content or ""


@runtime_checkable
class ModelProtocol(Protocol):
    """Protocol for LLM providers."""

    async def generate(
        self,
        prompt: Union[str, tuple[Message, ...]],
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: Union[Literal["auto", "none", "required"], str, dict] | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response.
        
        Args:
            prompt: Either a single string prompt, or a tuple of Messages
                    for multi-turn conversations.
            tools: Available tools the model can call.
            tool_choice: "auto", "none", "required", tool name, or provider-specific dict.
            options: Generation options (temperature, etc.)
        """
        ...
```

### 2. Tool Execution Engine

New component to dispatch tool calls. Reuses RFC-011's `ScriptSandbox` for security:

```python
# src/sunwell/tools/executor.py

from sunwell.skills.sandbox import ScriptSandbox  # RFC-011
from sunwell.skills.executor import SkillExecutor  # RFC-011


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result from executing a tool."""
    tool_call_id: str
    success: bool
    output: str
    artifacts: tuple[Path, ...] = ()  # Files created/modified
    execution_time_ms: int = 0


ToolHandler = Callable[[dict], Awaitable[str]]


@dataclass
class ToolExecutor:
    """Execute tool calls locally.
    
    This is a dispatcher that routes tool calls to appropriate handlers:
    - Built-in tools → CoreToolHandlers
    - Skill-derived tools → SkillExecutor (RFC-011)
    - Learned tools → LearnedToolHandler
    """
    
    workspace: Path
    sandbox: ScriptSandbox  # Reuse from RFC-011
    skill_executor: SkillExecutor | None = None  # For skill-derived tools
    
    # Handler registry
    _handlers: dict[str, ToolHandler] = field(default_factory=dict)
    _core_handlers: CoreToolHandlers | None = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        # Initialize core tool handlers
        self._core_handlers = CoreToolHandlers(self.workspace, self.sandbox)
        
        # Register built-in tools
        self._handlers.update({
            "read_file": self._core_handlers.read_file,
            "write_file": self._core_handlers.write_file,
            "list_files": self._core_handlers.list_files,
            "search_files": self._core_handlers.search_files,
            "run_command": self._core_handlers.run_command,
        })
    
    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a custom tool handler."""
        self._handlers[name] = handler
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        start = time.monotonic()
        
        handler = self._handlers.get(tool_call.name)
        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Unknown tool: {tool_call.name}",
            )
        
        try:
            output = await handler(tool_call.arguments)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                output=output,
                execution_time_ms=elapsed_ms,
            )
        except PermissionError as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Permission denied: {e}",
            )
        except FileNotFoundError as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output=f"Not found: {e}",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="Tool execution timed out",
            )
        except Exception as e:
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
            parallel: If True, execute concurrently (use with caution)
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
```

### 3. Built-in Core Tools

Standard tools that don't require skill definitions:

```python
# src/sunwell/tools/builtins.py

CORE_TOOLS = {
    # File Operations
    "read_file": Tool(
        name="read_file",
        description="Read contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace"},
            },
            "required": ["path"],
        },
    ),
    
    "write_file": Tool(
        name="write_file",
        description="Write content to a file (creates parent dirs)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    ),
    
    "list_files": Tool(
        name="list_files",
        description="List files in a directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "pattern": {"type": "string", "default": "*"},
            },
        },
    ),
    
    # Search
    "search_files": Tool(
        name="search_files",
        description="Search for text pattern in files",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "glob": {"type": "string", "default": "**/*"},
            },
            "required": ["pattern"],
        },
    ),
    
    # Shell (sandboxed)
    "run_command": Tool(
        name="run_command",
        description="Run a shell command (sandboxed, read-only by default)",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "."},
            },
            "required": ["command"],
        },
    ),
}
```

### 4. Tool Handlers (Local Execution)

```python
# src/sunwell/tools/handlers.py

import fnmatch
from pathlib import Path


# Default blocked patterns (can be extended via config)
DEFAULT_BLOCKED_PATTERNS = frozenset({
    ".env",
    ".env.*",
    "**/.git/**",
    "**/.git",
    "**/node_modules/**",
    "**/__pycache__/**",
    "*.pem",
    "*.key",
    "**/secrets/**",
    "**/.ssh/**",
})


class PathSecurityError(PermissionError):
    """Raised when a path access is blocked for security reasons."""
    pass


class CoreToolHandlers:
    """Handlers for built-in tools. Execute locally, no servers.
    
    Security: All path operations use _safe_path() which:
    1. Resolves to absolute path
    2. Ensures path stays within workspace (jail)
    3. Checks against blocked patterns
    """
    
    def __init__(
        self, 
        workspace: Path, 
        sandbox: ScriptSandbox,
        blocked_patterns: frozenset[str] = DEFAULT_BLOCKED_PATTERNS,
    ):
        self.workspace = workspace.resolve()
        self.sandbox = sandbox
        self.blocked_patterns = blocked_patterns
    
    def _safe_path(self, user_path: str, *, allow_write: bool = False) -> Path:
        """Canonicalize path and enforce security restrictions.
        
        Args:
            user_path: User-provided path (may be relative or absolute)
            allow_write: If True, path must not match write-protected patterns
            
        Returns:
            Resolved absolute path within workspace
            
        Raises:
            PathSecurityError: If path escapes workspace or matches blocked pattern
        """
        # Resolve path relative to workspace
        requested = (self.workspace / user_path).resolve()
        
        # SECURITY: Ensure path is within workspace (prevent traversal)
        try:
            requested.relative_to(self.workspace)
        except ValueError:
            raise PathSecurityError(
                f"Path escapes workspace: {user_path} → {requested}"
            )
        
        # SECURITY: Check against blocked patterns
        relative_str = str(requested.relative_to(self.workspace))
        for pattern in self.blocked_patterns:
            if fnmatch.fnmatch(relative_str, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
            if fnmatch.fnmatch(requested.name, pattern):
                raise PathSecurityError(f"Access blocked by pattern '{pattern}': {user_path}")
        
        return requested
    
    async def read_file(self, args: dict) -> str:
        """Read file contents. Respects blocked patterns."""
        path = self._safe_path(args["path"])
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {args['path']}")
        if not path.is_file():
            raise ValueError(f"Not a file: {args['path']}")
        
        # Size limit to prevent memory issues
        size = path.stat().st_size
        if size > 1_000_000:  # 1MB limit
            return f"File too large ({size:,} bytes). Use search_files to find specific content."
        
        content = path.read_text(encoding="utf-8", errors="replace")
        return f"```\n{content}\n```\n({len(content):,} bytes)"
    
    async def write_file(self, args: dict) -> str:
        """Write file contents. Creates parent directories."""
        path = self._safe_path(args["path"], allow_write=True)
        
        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)
        
        content = args["content"]
        path.write_text(content, encoding="utf-8")
        
        return f"✓ Wrote {args['path']} ({len(content):,} bytes)"
    
    async def list_files(self, args: dict) -> str:
        """List files in directory. Respects blocked patterns."""
        path = self._safe_path(args.get("path", "."))
        pattern = args.get("pattern", "*")
        
        if not path.is_dir():
            raise ValueError(f"Not a directory: {args.get('path', '.')}")
        
        files = []
        for f in sorted(path.glob(pattern)):
            try:
                # Filter out blocked paths
                self._safe_path(str(f.relative_to(self.workspace)))
                files.append(str(f.relative_to(self.workspace)))
            except PathSecurityError:
                continue  # Skip blocked files silently
        
        return "\n".join(files[:100]) or "(no matching files)"
    
    async def search_files(self, args: dict) -> str:
        """Search for pattern in files using ripgrep."""
        search_path = self._safe_path(args.get("path", "."))
        pattern = args["pattern"]
        
        # Prefer ripgrep, fallback to grep
        import shutil
        import subprocess
        
        rg_path = shutil.which("rg")
        if rg_path:
            cmd = [rg_path, "-n", "--max-filesize", "1M", pattern, "."]
        else:
            cmd = ["grep", "-rn", pattern, "."]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=search_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout[:10_000]  # Limit output size
            if result.returncode == 0:
                return output or "No matches found"
            elif result.returncode == 1:
                return "No matches found"
            else:
                return f"Search error: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return "Search timed out after 30s"
    
    async def run_command(self, args: dict) -> str:
        """Run shell command in sandbox (RFC-011 ScriptSandbox)."""
        cwd = self._safe_path(args.get("cwd", "."))
        
        result = await self.sandbox.execute(
            command=args["command"],
            cwd=str(cwd),
            timeout=args.get("timeout", 30),
        )
        
        output_parts = [f"Exit code: {result.exit_code}"]
        if result.stdout:
            output_parts.append(f"stdout:\n{result.stdout[:5000]}")
        if result.stderr:
            output_parts.append(f"stderr:\n{result.stderr[:2000]}")
        if result.timed_out:
            output_parts.append("(command timed out)")
        
        return "\n".join(output_parts)
```

### 5. Skill-to-Tool Conversion

Skills automatically become tools:

```python
# src/sunwell/skills/types.py

@dataclass
class Skill:
    name: str
    description: str
    # ... existing fields ...
    
    # NEW: Parameters schema for tool calling
    parameters_schema: dict | None = None
    
    def to_tool(self) -> Tool:
        """Convert this skill to a callable tool."""
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema or {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What to accomplish with this skill",
                    },
                },
                "required": ["task"],
            },
        )
```

```yaml
# In lens file - skill with parameters
skills:
  - name: create-api-docs
    description: Generate API documentation from source code
    parameters:
      type: object
      properties:
        source_file:
          type: string
          description: Path to source file to document
        output_file:
          type: string
          description: Where to write documentation
        format:
          type: string
          enum: [markdown, rst, html]
          default: markdown
      required: [source_file]
```

### 6. Tool-Aware Runtime

Update `RuntimeEngine` for tool loop:

```python
# src/sunwell/runtime/engine.py

from sunwell.models.protocol import Message, Tool, ToolCall, GenerateResult
from sunwell.tools.executor import ToolExecutor, ToolResult
from sunwell.tools.builtins import CORE_TOOLS


@dataclass(frozen=True, slots=True)
class ToolAwareResult:
    """Result from tool-aware execution."""
    
    content: str
    tool_history: tuple[tuple[ToolCall, ToolResult], ...] = ()
    total_tool_calls: int = 0
    truncated: bool = False  # True if max_tool_calls reached
    token_usage: TokenUsage | None = None


class RuntimeEngine:
    # ... existing fields ...
    tool_executor: ToolExecutor | None = None
    
    async def execute_with_tools(
        self,
        prompt: str,
        *,
        lens: Lens | None = None,
        max_tool_calls: int = 10,
        allowed_tools: set[str] | None = None,  # None = all tools
        options: GenerateOptions | None = None,
    ) -> ToolAwareResult:
        """Execute with automatic tool calling loop.
        
        Args:
            prompt: User request
            lens: Optional lens for skill-derived tools
            max_tool_calls: Safety limit on iterations
            allowed_tools: Restrict to specific tools (None = all)
            options: Generation options
        """
        if not self.tool_executor:
            raise RuntimeError("ToolExecutor not configured")
        
        # Collect available tools
        tools: list[Tool] = []
        
        # Add core tools (optionally filtered)
        for name, tool in CORE_TOOLS.items():
            if allowed_tools is None or name in allowed_tools:
                tools.append(tool)
        
        # Add skill-derived tools from lens
        if lens:
            for skill in lens.skills:
                if skill.parameters_schema:
                    tool = skill.to_tool()
                    if allowed_tools is None or tool.name in allowed_tools:
                        tools.append(tool)
        
        # Build initial message history
        messages: list[Message] = [
            Message(role="user", content=prompt)
        ]
        
        tool_history: list[tuple[ToolCall, ToolResult]] = []
        total_calls = 0
        
        for iteration in range(max_tool_calls):
            # Generate with tools available
            result = await self.model.generate(
                tuple(messages),
                tools=tuple(tools),
                tool_choice="auto",
                options=options,
            )
            
            # If no tool calls, we're done
            if not result.has_tool_calls:
                return ToolAwareResult(
                    content=result.text,
                    tool_history=tuple(tool_history),
                    total_tool_calls=total_calls,
                    token_usage=result.usage,
                )
            
            # Execute tool calls
            for tool_call in result.tool_calls:
                total_calls += 1
                tool_result = await self.tool_executor.execute(tool_call)
                tool_history.append((tool_call, tool_result))
            
            # Add assistant message with tool calls
            messages.append(Message(
                role="assistant",
                content=result.content,
                tool_calls=result.tool_calls,
            ))
            
            # Add tool result messages
            for tool_call, tool_result in tool_history[-len(result.tool_calls):]:
                messages.append(Message(
                    role="tool",
                    content=tool_result.output,
                    tool_call_id=tool_call.id,
                ))
        
        # Max iterations reached - generate final response without tools
        final_result = await self.model.generate(
            tuple(messages),
            tools=None,  # No tools for final response
            options=options,
        )
        
        return ToolAwareResult(
            content=final_result.text or "Maximum tool calls reached without completion.",
            tool_history=tuple(tool_history),
            total_tool_calls=total_calls,
            truncated=True,
            token_usage=final_result.usage,
        )
```

### 7. CLI Integration

```bash
# Enable tools in apply
sunwell apply lens.lens "Create docs for src/api.py" --tools

# Enable specific tools only
sunwell apply lens.lens "..." --tools read_file,write_file

# Disable tools (instruction-only mode)
sunwell apply lens.lens "..." --no-tools

# Chat with tools
sunwell chat --tools

# Dry-run: show tool calls without executing
sunwell apply lens.lens "..." --tools --dry-run

# Set trust level
sunwell apply lens.lens "..." --tools --trust workspace
```

### 8. Streaming with Tools

Tool calls interrupt streaming. The runtime handles this gracefully:

```python
# src/sunwell/runtime/engine.py

async def execute_stream_with_tools(
    self,
    prompt: str,
    *,
    lens: Lens | None = None,
    max_tool_calls: int = 10,
    options: GenerateOptions | None = None,
) -> AsyncIterator[StreamEvent]:
    """Stream execution with tool support.
    
    Yields StreamEvent objects:
    - TextEvent: Streamed text chunk
    - ToolCallEvent: Tool is being called (pause stream)
    - ToolResultEvent: Tool result (resume stream)
    - DoneEvent: Stream complete
    """
    messages: list[Message] = [Message(role="user", content=prompt)]
    tools = self._collect_tools(lens)
    tool_count = 0
    
    while tool_count < max_tool_calls:
        # Stream response
        accumulated_text = ""
        tool_calls: list[ToolCall] = []
        
        async for chunk in self.model.generate_stream(
            tuple(messages),
            tools=tuple(tools),
            options=options,
        ):
            if isinstance(chunk, str):
                accumulated_text += chunk
                yield TextEvent(text=chunk)
            elif isinstance(chunk, ToolCall):
                tool_calls.append(chunk)
        
        # If no tool calls, we're done
        if not tool_calls:
            yield DoneEvent(total_tool_calls=tool_count)
            return
        
        # Execute tool calls (stream pauses here)
        for tool_call in tool_calls:
            tool_count += 1
            yield ToolCallEvent(tool_call=tool_call)
            
            result = await self.tool_executor.execute(tool_call)
            yield ToolResultEvent(tool_call=tool_call, result=result)
            
            # Update message history
            messages.append(Message(
                role="assistant",
                content=accumulated_text,
                tool_calls=(tool_call,),
            ))
            messages.append(Message(
                role="tool",
                content=result.output,
                tool_call_id=tool_call.id,
            ))
        
        # Continue streaming with updated context
    
    yield DoneEvent(total_tool_calls=tool_count, truncated=True)


@dataclass
class TextEvent:
    text: str

@dataclass  
class ToolCallEvent:
    tool_call: ToolCall

@dataclass
class ToolResultEvent:
    tool_call: ToolCall
    result: ToolResult

@dataclass
class DoneEvent:
    total_tool_calls: int
    truncated: bool = False
```

**CLI streaming output:**

```
$ sunwell chat --tools --stream

You: Read config.yaml and summarize it
Assistant: I'll read the config file for you.

[Tool Call] read_file(path="config.yaml")
[Executing...]
[Result] ✓ Read 45 lines

The config file contains:▌  ← Streaming resumes
- Database settings (PostgreSQL on localhost)
- API keys section (redacted)
- Feature flags for beta features
...
```

---

## Provider Implementations

### OpenAI

```python
# src/sunwell/models/openai.py

class OpenAIModel:
    async def generate(
        self,
        prompt: str,
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: str | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {"model": self.model_id, "messages": messages}
        
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            kwargs["tool_choice"] = tool_choice or "auto"
        
        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        
        tool_calls = ()
        if message.tool_calls:
            tool_calls = tuple(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in message.tool_calls
            )
        
        return GenerateResult(
            content=message.content,
            tool_calls=tool_calls,
            model=response.model,
        )
```

### Anthropic

```python
# src/sunwell/models/anthropic.py

class AnthropicModel:
    async def generate(
        self,
        prompt: str,
        *,
        tools: tuple[Tool, ...] | None = None,
        tool_choice: str | None = None,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        kwargs = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": options.max_tokens if options else 4096,
        }
        
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]
        
        response = await self.client.messages.create(**kwargs)
        
        content = None
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))
        
        return GenerateResult(
            content=content,
            tool_calls=tuple(tool_calls),
            model=response.model,
        )
```

---

## Security Model

This section extends RFC-011's security model. Tool execution reuses `ScriptSandbox` from RFC-011 for shell commands.

### Security Layers

```
┌───────────────────────────────────────────────────────────────────┐
│  Layer 1: Tool Policy (lens/config)                               │
│  - Which tools are enabled                                        │
│  - Maximum trust level                                            │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│  Layer 2: Path Security (CoreToolHandlers._safe_path)             │
│  - Workspace jail (prevents ../../../etc/passwd)                  │
│  - Blocked pattern matching (.env, .git, secrets)                 │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│  Layer 3: Execution Sandbox (RFC-011 ScriptSandbox)               │
│  - Process isolation for run_command                              │
│  - Timeout enforcement                                            │
│  - Resource limits                                                │
└───────────────────────────────────────────────────────────────────┘
```

### Tool Trust Levels

Trust levels control which tools are exposed to the LLM. This extends the existing `TrustLevel` from RFC-011.

```python
# src/sunwell/tools/types.py

from enum import Enum

class ToolTrust(Enum):
    """Trust levels control tool availability.
    
    Each level includes all tools from the previous levels.
    """
    
    # Only informational tools: list_files, search_files
    # read_file is NOT included here as it could expose secrets
    DISCOVERY = "discovery"      
    
    # discovery + read_file (restricted by blocked patterns)
    READ_ONLY = "read_only"      
    
    # read_only + write_file (workspace jail enforced)
    WORKSPACE = "workspace"      
    
    # workspace + run_command (isolated in ScriptSandbox)
    SHELL = "shell"              
    
    # shell + learned tools + network access
    FULL = "full"                
```

### Default Restrictions

| Trust Level | Allowed Built-in Tools | Restrictions |
|:---|:---|:---|
| **DISCOVERY** | `list_files`, `search_files` | Workspace only, 1MB limit |
| **READ_ONLY** | + `read_file` | Blocked patterns apply |
| **WORKSPACE** | + `write_file` | No overwriting of blocked files |
| **SHELL** | + `run_command` | isolated sandbox, 30s timeout |
| **FULL** | + `learn_api` | Network allowed (opt-in) |

### Path Security Implementation

All file operations go through `_safe_path()` which enforces the "Jail and Block" policy:

```python
# src/sunwell/tools/handlers.py

def _safe_path(self, user_path: str, *, write: bool = False) -> Path:
    """Canonicalize path and enforce security.
    
    1. Resolve: (workspace / user_path).resolve()
    2. Jail check: resolved.relative_to(workspace) — raises if escapes
    3. Pattern check: fnmatch against blocked_patterns — raises if matches
    4. Write check: if write=True, ensures path is not read-only in config
    """
```

**Blocked by default:**
- `.env`, `.env.*` — secrets
- `**/.git/**` — repository internals
- `**/node_modules/**` — large dependency trees
- `*.pem`, `*.key` — certificates
- `**/secrets/**`, `**/.ssh/**` — sensitive directories

### Rate Limiting

```python
@dataclass
class ToolRateLimits:
    """Per-session rate limits to prevent abuse."""
    
    max_tool_calls_per_minute: int = 30
    max_file_writes_per_minute: int = 10
    max_shell_commands_per_minute: int = 5
    max_bytes_written_per_session: int = 10_000_000  # 10MB
```

### Configuration

```yaml
# In lens or global config (~/.sunwell/config.yaml)
tool_policy:
  trust_level: workspace  # Maximum trust level for this lens
  
  # Explicit tool allowlist (optional, defaults to all at trust_level)
  allowed_tools:
    - read_file
    - write_file
    - list_files
    - search_files
  
  # Additional blocked patterns (merged with defaults)
  blocked_paths:
    - "**/*.secret"
    - "**/credentials/**"
  
  # For SHELL trust level
  command_allowlist:
    - "ls"
    - "cat"
    - "grep"
    - "python -m pytest"
    - "npm test"
  
  # Rate limits (override defaults)
  rate_limits:
    max_file_writes_per_minute: 5
```

### Audit Logging

Tool executions are logged for debugging and security review:

```python
@dataclass
class ToolAuditEntry:
    """Audit log entry for tool execution."""
    
    timestamp: datetime
    tool_name: str
    arguments: dict  # Sanitized (no content for write_file)
    success: bool
    execution_time_ms: int
    error: str | None = None


# Stored in: .sunwell/audit/tools-{date}.jsonl
```

---

## Implementation Plan

### Phase 1: Protocol Extension (Week 1)

- [ ] Add `Message`, `Tool`, `ToolCall`, `ToolResult` types to `protocol.py`
- [ ] Extend `GenerateResult` with `tool_calls` and `has_tool_calls` property
- [ ] Update `ModelProtocol.generate()` to accept `str | tuple[Message, ...]`
- [ ] Add migration notes for `content: str` → `content: str | None`

**Exit criteria:** Protocol compiles, existing tests pass with `result.text` helper.

### Phase 2: Provider Support (Week 2)

- [ ] Implement tools in `OpenAIModel` (function calling format)
- [ ] Implement tools in `AnthropicModel` (tool_use blocks)
- [ ] Add `MockModel` with configurable tool responses for tests
- [ ] Handle provider-specific tool_choice mappings

**Exit criteria:** All providers pass tool calling integration tests.

### Phase 3: Core Tools & Security (Week 3)

- [ ] Create `CoreToolHandlers` with `_safe_path()` security
- [ ] Implement `read_file`, `write_file`, `list_files`, `search_files`
- [ ] Implement `run_command` using RFC-011 `ScriptSandbox`
- [ ] Add `PathSecurityError` and blocked pattern enforcement
- [ ] Unit tests for path traversal prevention

**Exit criteria:** Security tests verify jail enforcement, blocked patterns work.

### Phase 4: Tool Executor & Runtime (Week 4)

- [ ] Create `ToolExecutor` dispatcher class
- [ ] Implement `execute_with_tools()` in `RuntimeEngine`
- [ ] Add streaming support (`execute_stream_with_tools`)
- [ ] Implement rate limiting (`ToolRateLimits`)
- [ ] Add audit logging to `.sunwell/audit/`

**Exit criteria:** Full tool loop works with max_tool_calls limit.

### Phase 5: CLI & Skill Integration (Week 5)

- [ ] Add `--tools`, `--no-tools`, `--dry-run` flags to CLI
- [ ] Add `--trust` flag for trust level control
- [ ] Add `parameters_schema` to `Skill` type
- [ ] Implement `Skill.to_tool()` conversion
- [ ] Wire skill-derived tools into `ToolExecutor`
- [ ] Add lens-level `tool_policy` configuration

**Exit criteria:** `sunwell apply --tools` works end-to-end.

### Phase 6: UniTool (Future - Week 6+)

> **Prerequisite:** Web search provider integration

- [ ] Implement `WebSearchProvider` protocol
- [ ] Add SerpAPI/Brave Search adapters
- [ ] Implement `APILearner` class
- [ ] Create `ToolStore` for persistent learned tools
- [ ] Add domain allowlist and rate limits
- [ ] User approval flow for auth credentials

**Exit criteria:** Can learn and reuse a simple public API (e.g., PokeAPI).

---

## Testing Strategy

### Unit Tests

```python
# tests/test_tools.py

class TestPathSecurity:
    """Verify path traversal prevention."""
    
    def test_safe_path_allows_workspace_files(self, handlers):
        path = handlers._safe_path("src/main.py")
        assert path.is_relative_to(handlers.workspace)
    
    def test_safe_path_blocks_traversal(self, handlers):
        with pytest.raises(PathSecurityError):
            handlers._safe_path("../../../etc/passwd")
    
    def test_safe_path_blocks_dotenv(self, handlers):
        with pytest.raises(PathSecurityError):
            handlers._safe_path(".env")
    
    def test_safe_path_blocks_git(self, handlers):
        with pytest.raises(PathSecurityError):
            handlers._safe_path(".git/config")


class TestToolExecutor:
    """Verify tool execution and error handling."""
    
    async def test_execute_unknown_tool(self, executor):
        result = await executor.execute(ToolCall(
            id="1", name="nonexistent", arguments={}
        ))
        assert not result.success
        assert "Unknown tool" in result.output
    
    async def test_execute_timeout(self, executor):
        # Requires mock that simulates timeout
        result = await executor.execute(ToolCall(
            id="1", name="slow_tool", arguments={}
        ))
        assert not result.success
        assert "timed out" in result.output
```

### Integration Tests

```python
# tests/test_tool_loop.py

class TestToolLoop:
    """End-to-end tool calling tests."""
    
    async def test_read_modify_write_chain(self, engine, tmp_workspace):
        """Test multi-turn: read file → modify → write back."""
        # Setup
        (tmp_workspace / "input.txt").write_text("hello")
        
        result = await engine.execute_with_tools(
            "Read input.txt, uppercase it, save as output.txt"
        )
        
        assert (tmp_workspace / "output.txt").exists()
        assert (tmp_workspace / "output.txt").read_text() == "HELLO"
        assert result.total_tool_calls == 2  # read + write
    
    async def test_max_tool_calls_limit(self, engine):
        """Verify iteration limit prevents infinite loops."""
        result = await engine.execute_with_tools(
            "Keep reading random files forever",
            max_tool_calls=3,
        )
        
        assert result.truncated
        assert result.total_tool_calls == 3
```

### Mock Model for Testing

```python
# src/sunwell/models/mock.py

class MockModelWithTools:
    """Mock model with configurable tool call responses."""
    
    def __init__(self, responses: list[GenerateResult]):
        self.responses = responses
        self.call_count = 0
    
    async def generate(
        self,
        prompt: str | tuple[Message, ...],
        *,
        tools: tuple[Tool, ...] | None = None,
        **kwargs,
    ) -> GenerateResult:
        result = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return result


# Usage in tests:
mock = MockModelWithTools([
    GenerateResult(
        content=None,
        model="mock",
        tool_calls=(ToolCall(id="1", name="read_file", arguments={"path": "x.txt"}),),
    ),
    GenerateResult(content="Done!", model="mock"),
])
```

---

## Comparison: Tools vs MCP

| Aspect | This Proposal (Tools) | MCP |
|--------|----------------------|-----|
| **Servers** | None - local execution | Required |
| **Latency** | Minimal - in-process | Network overhead |
| **Discovery** | Static (defined in code/lens) | Dynamic (`tools/list`) |
| **Ecosystem** | Build your own | Pre-built servers |
| **Complexity** | Low | High |
| **Use Case** | Core operations | External services |

**Recommendation:** Start with tools. Add MCP later if external service integration is needed.

---

## Example Session

```
$ sunwell chat --tools

You: Read src/api.py and create documentation for it
Assistant: I'll read the file first to understand its structure.

[Tool Call] read_file(path="src/api.py")
[Tool Result] ✓ Read 234 lines

```python
"""API module for user management."""

def get_user(user_id: str) -> User:
    """Get user by ID..."""
...
```

Now I'll create the documentation.

[Tool Call] write_file(path="docs/api-reference.md", content="# API Reference

## get_user
...")
[Tool Result] ✓ Wrote docs/api-reference.md (1,842 bytes)

I've created the API documentation at `docs/api-reference.md`. It includes:
- Function signatures with types
- Parameter descriptions
- Usage examples
- Source references

Would you like me to add anything else?
```

---

## Tool Learning: The UniTool (Phase 6 - Future)

> **Note:** This section describes a future capability. It requires network access and web search, which are not part of the core tool implementation (Phases 1-5). Implement this after core tools are stable.

A meta-tool that **discovers and saves new tools** from natural language requests.

### Concept

```
User: "Get a pikachu from the online pokedex"
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  UNITOOL: learn_api                                         │
│                                                             │
│  1. DISCOVER: Search for "pokedex API" → finds pokeapi.co   │
│  2. EXPLORE: Fetch docs, find endpoints                     │
│  3. TEST: Try GET /api/v2/pokemon/pikachu                   │
│  4. VERIFY: Got valid JSON response                         │
│  5. SAVE: Create reusable tool definition                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  NEW TOOL SAVED: get_pokemon                                │
│                                                             │
│  name: get_pokemon                                          │
│  description: Fetch Pokemon data from PokeAPI               │
│  base_url: https://pokeapi.co/api/v2                        │
│  endpoints:                                                 │
│    - path: /pokemon/{name}                                  │
│      method: GET                                            │
│      params: {name: string}                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
Next time: "Get a charizard" → uses saved tool instantly
```

### The UniTool: `learn_api`

```python
# src/sunwell/tools/unitool.py

LEARN_API_TOOL = Tool(
    name="learn_api",
    description="""
    Learn how to interact with an unknown API and save it as a reusable tool.
    
    Use this when asked to interact with a service you don't have a tool for.
    The tool will:
    1. Search for API documentation
    2. Discover endpoints and authentication
    3. Test the API with a sample request
    4. Save a working tool definition for future use
    """,
    parameters={
        "type": "object",
        "properties": {
            "service_description": {
                "type": "string",
                "description": "What service to learn (e.g., 'pokedex API', 'weather service')",
            },
            "example_task": {
                "type": "string",
                "description": "A concrete example of what to do (e.g., 'get pikachu data')",
            },
            "hints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional hints like known URL or auth method",
            },
        },
        "required": ["service_description", "example_task"],
    },
)


@dataclass
class LearnedTool:
    """A tool learned from API discovery."""
    
    name: str
    description: str
    base_url: str
    endpoints: list[Endpoint]
    auth: AuthConfig | None = None
    learned_at: datetime = field(default_factory=datetime.now)
    success_count: int = 0
    
    def to_tool(self) -> Tool:
        """Convert to callable Tool."""
        # Generate parameters from endpoints
        properties = {}
        required = []
        
        for ep in self.endpoints:
            for param in ep.params:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.required:
                    required.append(param.name)
        
        return Tool(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
        )


@dataclass
class Endpoint:
    path: str  # e.g., "/pokemon/{name}"
    method: str = "GET"
    params: list[Param] = field(default_factory=list)
    response_schema: dict | None = None
```

### Learning Process

```python
class APILearner:
    """Discovers and learns new API tools."""
    
    def __init__(self, model: ModelProtocol, tool_store: ToolStore):
        self.model = model
        self.tool_store = tool_store
    
    async def learn(
        self,
        service_description: str,
        example_task: str,
        hints: list[str] | None = None,
    ) -> LearnedTool:
        """Learn a new API tool through discovery and testing."""
        
        # Step 1: DISCOVER - Search for the API
        search_results = await self._search_for_api(service_description)
        
        # Step 2: EXPLORE - Read documentation, find endpoints
        api_info = await self._explore_api(search_results, example_task)
        
        # Step 3: TEST - Try the API with the example task
        test_result = await self._test_api(api_info, example_task)
        
        if not test_result.success:
            # Try alternative approaches
            api_info = await self._refine_approach(api_info, test_result.error)
            test_result = await self._test_api(api_info, example_task)
        
        if not test_result.success:
            raise ToolLearningError(f"Could not learn API: {test_result.error}")
        
        # Step 4: SAVE - Create and store the tool
        learned_tool = LearnedTool(
            name=self._generate_tool_name(service_description),
            description=f"Interact with {service_description}",
            base_url=api_info.base_url,
            endpoints=api_info.endpoints,
            auth=api_info.auth,
        )
        
        # Save to tool store for future use
        self.tool_store.save(learned_tool)
        
        return learned_tool
    
    async def _search_for_api(self, service: str) -> list[SearchResult]:
        """Search web for API documentation.
        
        Requires: WebSearchProvider (injected dependency)
        Options:
        - SerpAPI (requires SERPAPI_KEY)
        - Brave Search API (requires BRAVE_API_KEY)
        - DuckDuckGo (no key, rate limited)
        - User-provided search function
        """
        if not self.web_search:
            raise ToolLearningError(
                "Web search not configured. Set SERPAPI_KEY or BRAVE_API_KEY, "
                "or provide a custom web_search function."
            )
        
        queries = [
            f"{service} API documentation",
            f"{service} REST API",
            f"{service} developer docs",
        ]
        results = []
        for q in queries:
            results.extend(await self.web_search(q))
        return results
    
    async def _explore_api(
        self, 
        search_results: list[SearchResult],
        example_task: str,
    ) -> APIInfo:
        """Use LLM to read docs and extract API structure."""
        
        # Fetch top documentation pages
        docs_content = []
        for result in search_results[:3]:
            content = await self.fetch_page(result.url)
            docs_content.append(content)
        
        # Ask LLM to extract API info
        prompt = f"""
        Based on this API documentation, extract:
        1. Base URL
        2. Relevant endpoints for: {example_task}
        3. Required authentication (if any)
        4. Request/response format
        
        Documentation:
        {docs_content}
        """
        
        response = await self.model.generate(prompt)
        return self._parse_api_info(response.content)
    
    async def _test_api(self, api_info: APIInfo, task: str) -> TestResult:
        """Actually call the API to verify it works."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            for endpoint in api_info.endpoints:
                url = f"{api_info.base_url}{endpoint.path}"
                
                try:
                    response = await client.request(
                        method=endpoint.method,
                        url=url,
                        headers=api_info.auth.headers if api_info.auth else {},
                        timeout=10,
                    )
                    
                    if response.is_success:
                        return TestResult(
                            success=True,
                            response=response.json(),
                            endpoint=endpoint,
                        )
                except Exception as e:
                    continue
        
        return TestResult(success=False, error="All endpoints failed")
```

### Tool Store

```python
# src/sunwell/tools/store.py

class ToolStore:
    """Persistent storage for learned tools."""
    
    def __init__(self, path: Path = Path(".sunwell/learned_tools")):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
    
    def save(self, tool: LearnedTool) -> None:
        """Save learned tool to disk."""
        tool_file = self.path / f"{tool.name}.yaml"
        tool_file.write_text(yaml.dump(tool.to_dict()))
    
    def load_all(self) -> list[LearnedTool]:
        """Load all learned tools."""
        tools = []
        for f in self.path.glob("*.yaml"):
            data = yaml.safe_load(f.read_text())
            tools.append(LearnedTool.from_dict(data))
        return tools
    
    def get(self, name: str) -> LearnedTool | None:
        """Get a specific learned tool."""
        tool_file = self.path / f"{name}.yaml"
        if tool_file.exists():
            return LearnedTool.from_dict(yaml.safe_load(tool_file.read_text()))
        return None
```

### Example: Learning the Pokemon API

```yaml
# .sunwell/learned_tools/get_pokemon.yaml
# Auto-generated by learn_api tool

name: get_pokemon
description: Fetch Pokemon data from PokeAPI
base_url: https://pokeapi.co/api/v2
learned_at: 2026-01-15T14:30:00Z
success_count: 1

endpoints:
  - path: /pokemon/{name}
    method: GET
    params:
      - name: name
        type: string
        description: Pokemon name (lowercase)
        required: true
    response_example:
      id: 25
      name: pikachu
      height: 4
      weight: 60
      types:
        - type:
            name: electric

  - path: /pokemon/{id}
    method: GET
    params:
      - name: id
        type: integer
        description: Pokemon ID number
        required: true
```

### Session Example

```
$ sunwell chat --tools

You: Get me a pikachu from the online pokedex

[No existing tool found for "pokedex"]
[Tool Call] learn_api(
    service="pokemon/pokedex API",
    example_task="get pikachu data"
)

🔍 Searching for API...
   Found: pokeapi.co

📖 Reading documentation...
   Base URL: https://pokeapi.co/api/v2
   Endpoint: GET /pokemon/{name}
   Auth: None required

🧪 Testing API...
   GET https://pokeapi.co/api/v2/pokemon/pikachu
   ✓ Success (200 OK)

💾 Saving tool: get_pokemon
   Stored in .sunwell/learned_tools/get_pokemon.yaml

[Tool Result] Learned new tool: get_pokemon

Now using the learned tool:

[Tool Call] get_pokemon(name="pikachu")
[Tool Result]
{
  "name": "pikachu",
  "id": 25,
  "types": ["electric"],
  "height": 4,
  "weight": 60,
  "abilities": ["static", "lightning-rod"]
}

Here's Pikachu! It's an Electric-type Pokemon (#25).
- Height: 0.4m
- Weight: 6.0kg
- Abilities: Static, Lightning Rod

You: Now get me charizard

[Tool Call] get_pokemon(name="charizard")  # Reuses learned tool!
[Tool Result] {...}

Charizard (#6) is a Fire/Flying type...
```

### Safety & Limits

```python
@dataclass
class LearnLimits:
    """Safety limits for API learning."""
    
    # Only learn from allowlisted domains initially
    allowed_domains: set[str] = field(default_factory=lambda: {
        "api.github.com",
        "pokeapi.co",
        "api.openweathermap.org",
        "api.coindesk.com",
        # User can add more
    })
    
    # Rate limits
    max_requests_per_learn: int = 10
    max_learn_attempts_per_hour: int = 5
    
    # No auth secrets in learned tools (prompt user)
    require_user_approval_for_auth: bool = True
```

---

## Future: MCP Bridge (Optional)

If external service integration is needed later, add MCP as a **transport layer**:

```python
# Future: MCP client wraps remote tools as local Tool objects
class MCPBridge:
    """Bridge MCP servers to Sunwell tool system."""
    
    async def discover_tools(self, server_url: str) -> list[Tool]:
        """Fetch tools from MCP server, convert to Tool objects."""
        response = await self.client.get(f"{server_url}/tools/list")
        return [Tool.from_mcp(t) for t in response["tools"]]
```

This keeps core tools local (fast) while allowing MCP for external services (Gmail, Slack, DBs).

---

## Migration Guide

### Protocol Changes

The `GenerateResult.content` field changes from `str` to `str | None`:

```python
# BEFORE (current code)
result = await model.generate(prompt)
output = result.content  # Always str

# AFTER (with tools)
result = await model.generate(prompt, tools=tools)
output = result.content  # May be None if tool_calls present

# MIGRATION OPTIONS:

# Option 1: Use .text property (recommended)
output = result.text  # Returns content or ""

# Option 2: Explicit check
if result.has_tool_calls:
    # Handle tool calls
else:
    output = result.content  # Safe, no tool calls means content exists

# Option 3: Default (simple cases)
output = result.content or ""
```

### Existing Code Compatibility

Code that doesn't use tools continues to work unchanged:

```python
# This still works - no tools means content is always present
result = await model.generate(prompt)  # tools=None (default)
assert result.content is not None  # Guaranteed when no tools
```

### Runtime Engine Changes

`RuntimeEngine.execute()` behavior is unchanged. New method `execute_with_tools()` adds tool support:

```python
# Existing (unchanged)
result = await engine.execute(prompt)  # No tools

# New (opt-in)
result = await engine.execute_with_tools(prompt)  # With tools
```

---

## Chat Commands

In-chat command syntax for invoking skills and system functions directly from the terminal.

### Syntax: `::command`

**Why double-colon?**

| Syntax | Risk | Example False Positive |
|--------|------|------------------------|
| `/cmd` | High | "good/bad", "/usr/bin", "yes/no" |
| `!cmd` | High | Bash history expansion |
| `@cmd` | Medium | Bash arrays, email-like text |
| `::cmd` | **Very low** | Almost never in natural English |

`::` is visually distinct, easy to type, and virtually never appears in casual conversation or paths.

### Core Commands

```
::help              Show available commands
::skills            List skills from current lens
::lens              Show current lens info
::lens <name>       Switch to different lens
::focus <scope>     Narrow context (code, docs, tests)
::context           Show current headspace context
::save <path>       Save last output to file
::clear             Clear conversation history
::exit              Exit chat session
```

### Parsing Implementation

```python
import re
from dataclasses import dataclass

@dataclass
class ParsedInput:
    command: str | None  # None if regular message
    args: str
    raw: str

def parse_input(text: str) -> ParsedInput:
    """Parse user input for ::commands."""
    text = text.strip()
    
    if text.startswith("::"):
        # Match ::word with optional arguments
        match = re.match(r'^::([a-zA-Z][\w-]*)\s*(.*)', text)
        if match:
            return ParsedInput(
                command=match.group(1).lower(),
                args=match.group(2),
                raw=text,
            )
    
    return ParsedInput(command=None, args="", raw=text)

# Examples:
# "::save notes.md"  → ParsedInput(command="save", args="notes.md", ...)
# "::help"           → ParsedInput(command="help", args="", ...)
# "hello world"      → ParsedInput(command=None, args="", raw="hello world")
# "good/bad choice"  → ParsedInput(command=None, ...)  # No false positive
```

### Terminal Highlighting (ANSI)

Commands are highlighted in the terminal for visual distinction:

```python
def highlight_commands(text: str) -> str:
    """Highlight ::commands with ANSI colors."""
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    
    pattern = r'(^|(?<=\s))(::[\w-]+)'
    return re.sub(pattern, rf'\1{BOLD}{CYAN}\2{RESET}', text)
```

**Visual result:**

```
┌─────────────────────────────────────────────────┐
│ You: Can you analyze this code?                 │
│                                                 │
│ Sunwell: I see a few issues with the auth...    │
│                                                 │
│ You: ::save analysis.md                         │  ← highlighted cyan
│                                                 │
│ Sunwell: ✓ Saved to analysis.md (1.2 KB)        │
└─────────────────────────────────────────────────┘
```

### IDE Syntax Highlighting

For `.lens` files and markdown preview, a TextMate injection grammar:

**`syntaxes/sunwell-commands.json`:**

```json
{
  "scopeName": "source.sunwell.injection",
  "injectionSelector": "L:text.html.markdown, L:source.yaml",
  "patterns": [
    {
      "name": "keyword.control.command.sunwell",
      "match": "::[a-zA-Z][\\w-]*",
      "comment": "Sunwell chat commands like ::save, ::help"
    }
  ]
}
```

**VS Code extension contribution:**

```json
{
  "contributes": {
    "grammars": [
      {
        "scopeName": "source.sunwell.injection",
        "path": "./syntaxes/sunwell-commands.json",
        "injectTo": ["text.html.markdown", "source.yaml", "source.sunwell"]
      }
    ]
  }
}
```

### Command Handler Architecture

```python
from typing import Callable, Awaitable

CommandHandler = Callable[[str, "ChatSession"], Awaitable[str | None]]

class CommandRegistry:
    """Registry for ::command handlers."""
    
    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
    
    def register(self, name: str) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a command handler."""
        def decorator(fn: CommandHandler) -> CommandHandler:
            self._handlers[name] = fn
            return fn
        return decorator
    
    async def execute(self, command: str, args: str, session: "ChatSession") -> str | None:
        """Execute a command, return response or None."""
        handler = self._handlers.get(command)
        if handler:
            return await handler(args, session)
        return f"Unknown command: ::{command}. Try ::help"

# Usage
commands = CommandRegistry()

@commands.register("help")
async def cmd_help(args: str, session: "ChatSession") -> str:
    """Show available commands."""
    return """Available commands:
  ::help          Show this help
  ::skills        List available skills
  ::lens          Show/switch lens
  ::save <path>   Save last output
  ::clear         Clear history
  ::exit          Exit session"""

@commands.register("save")
async def cmd_save(args: str, session: "ChatSession") -> str:
    """Save last assistant output to file."""
    if not args:
        return "Usage: ::save <path>"
    path = Path(args)
    if session.last_response:
        path.write_text(session.last_response)
        return f"✓ Saved to {path} ({len(session.last_response)} bytes)"
    return "No output to save"

@commands.register("skills")
async def cmd_skills(args: str, session: "ChatSession") -> str:
    """List skills from current lens."""
    skills = session.lens.skills if session.lens else []
    if not skills:
        return "No skills loaded"
    lines = ["Available skills:"]
    for s in skills:
        lines.append(f"  {s.name}: {s.description}")
    return "\n".join(lines)
```

### Integration with Chat Loop

```python
async def chat_loop(session: ChatSession, commands: CommandRegistry):
    """Main chat loop with command support."""
    while True:
        user_input = await session.prompt("You: ")
        parsed = parse_input(user_input)
        
        if parsed.command:
            # Handle ::command
            if parsed.command == "exit":
                break
            result = await commands.execute(parsed.command, parsed.args, session)
            if result:
                print(highlight_commands(result))
        else:
            # Regular conversation - send to LLM
            response = await session.send(parsed.raw)
            print(f"Sunwell: {response}")
```

### Future: Skill Invocation via Commands

Commands can also invoke skills directly:

```
::run audit-code        # Invoke audit-code skill
::run draft-api --out api.md  # Skill with arguments
```

This bridges the gap between chat commands and the skill system.

---

## Tool Execution Semantics

To ensure reliability and predictability, tool execution follows these semantics:

1. **Sequential by Default**: Tools are executed in the order requested by the LLM. While `execute_batch` supports `parallel=True`, it should be used exclusively for read-only or independent operations.
2. **Atomic Writes**: `write_file` implementation should use a "write-to-temp-then-rename" strategy to prevent partial writes if execution is interrupted.
3. **Implicit Tool Choice**: When a lens is active, Sunwell will automatically enable relevant tools based on the current context, unless explicitly overridden by `--no-tools`.

---

## Open Questions & Decisions

1. **Parallel tool execution:** 
   - **Decision:** Default to sequential. Add a `@tool(parallel=True)` decorator for tools that are verified as thread-safe and side-effect free.
   
2. **Tool result caching:** 
   - **Decision:** No caching for Phase 1. File contents can change between turns. If performance becomes an issue, implement `ETag`-based caching for `read_file`.

3. **Streaming tool calls:** 
   - **Decision:** Wait for the complete tool call (all arguments) before starting execution. Streaming tool *results* back to the model is supported.

4. **Provider tool_choice divergence:** 
   - **Decision:** The `ModelProtocol` accepts a `dict` for `tool_choice` to allow passing through provider-specific configurations while supporting `"auto"` as the cross-provider default.

---

## References

- [RFC-011: Skills](./RFC-011-lenses-with-skills.md) — `ScriptSandbox`, `SkillExecutor` definitions
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use](https://docs.anthropic.com/en/docs/tool-use)
- [MCP Specification](https://modelcontextprotocol.io/) — Future bridge target

## Migration Strategy

### 1. Update Protocol Usage

All code currently accessing `GenerateResult.content` should switch to `GenerateResult.text` or handle the `None` case explicitly.

```python
# Old code
result = await model.generate(prompt)
print(result.content.upper())

# New code (backward compatible)
result = await model.generate(prompt)
print(result.text.upper())

# New code (tool-aware)
result = await model.generate(prompt, tools=my_tools)
if result.has_tool_calls:
    # handle tool calls
    pass
else:
    print(result.text.upper())
```

### 2. Sandbox Updates

RFC-011's `ScriptSandbox` remains the source of truth for execution. RFC-012's `ToolExecutor` wraps this to provide the tool calling interface. No changes are required to existing lens definitions unless opting into the new `parameters_schema` for skills.

---

## Changelog

| Date | Change |
|:---|:---|
| 2026-01-15 | Initial draft |
| 2026-01-15 | Added `Message` type for multi-turn conversations |
| 2026-01-15 | Added architecture diagram clarifying ToolExecutor vs SkillExecutor |
| 2026-01-15 | Added path security with `_safe_path()` and blocked patterns |
| 2026-01-15 | Added streaming with tools section |
| 2026-01-15 | Moved UniTool to Phase 6 (future), clarified web search dependency |
| 2026-01-15 | Added Testing Strategy section with unit/integration tests |
| 2026-01-15 | Added rate limiting and audit logging to security model |
| 2026-01-15 | **Refinement**: Consolidated Trust Levels and added DISCOVERY level |
| 2026-01-15 | **Refinement**: Resolved open questions on parallel execution and tool choice |
| 2026-01-15 | **Refinement**: Added explicit Migration Strategy section |
| 2026-01-15 | Added Chat Commands section with `::` syntax |

