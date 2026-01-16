# RFC-024: Expanded Tools & Context References

| Field | Value |
|-------|-------|
| **RFC** | 024 |
| **Title** | Expanded Tools, Context References, and Smart Defaults |
| **Status** | Draft |
| **Created** | 2026-01-16 |
| **Updated** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-012 (Tool Calling) |
| **Implements** | `src/sunwell/tools/`, `src/sunwell/context/` |

---

## Abstract

This RFC proposes three improvements to Sunwell's tool system:

1. **Expanded Tools** — Add git operations and restricted environment access
2. **Context References** — `@file`, `@dir`, `@git:staged` syntax for referencing context
3. **Smart Defaults** — Auto-detect workspace, suggest (not force) trust levels, reduce friction

The goal: **Reduce friction while maintaining security** — workspace detection should "just work" but trust escalation requires explicit opt-in.

---

## Motivation

### Problem 1: Missing Essential Tools

Current tools are too limited for real development work:

```bash
# Can't do this:
sunwell "what changed in the last 3 commits?"     # No git_log
sunwell "show me the diff for auth.py"            # No git_diff
sunwell "who wrote this function?"                # No git_blame
```

Developers need git integration. Without it, Sunwell can't help with:
- Code review (needs diff)
- Understanding history (needs log)
- Debugging regressions (needs blame)

### Problem 2: No Way to Reference Context

Users want to say:

```bash
sunwell "review @file"                    # Current file
sunwell "explain @selection"              # Selected text
sunwell "what changed in @git:staged"     # Staged changes
sunwell "summarize @dir"                  # Current directory
```

But there's no syntax for this. Users have to manually copy-paste paths.

### Problem 3: Too Much Friction

Current UX requires explicit flags:

```bash
# Too verbose:
sunwell run --workspace /path/to/repo "review auth.py"

# Should be:
sunwell "review auth.py"
```

Sunwell should auto-detect:
- Is this a git repo? → Use repo root as workspace
- Is there a `.sunwell/` config? → Use those settings
- What's the cwd? → Use as fallback workspace

---

## Architecture

### Part 1: Expanded Tool Set

#### New Git Tools

```python
GIT_TOOLS: dict[str, Tool] = {
    # ==========================================================================
    # Read Operations (READ_ONLY trust level)
    # ==========================================================================
    
    "git_status": Tool(
        name="git_status",
        description="Show working tree status: modified, staged, untracked files.",
        parameters={
            "type": "object",
            "properties": {
                "short": {
                    "type": "boolean",
                    "description": "Use short format output",
                    "default": False,
                },
            },
        },
    ),
    
    "git_diff": Tool(
        name="git_diff",
        description="Show changes between commits, working tree, or staged area.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to diff (optional)",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged changes (--cached)",
                    "default": False,
                },
                "commit": {
                    "type": "string",
                    "description": "Compare against specific commit (e.g., HEAD~3)",
                },
            },
        },
    ),
    
    "git_log": Tool(
        name="git_log",
        description="Show commit history.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Show history for specific file/directory",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of commits to show",
                    "default": 10,
                },
                "oneline": {
                    "type": "boolean",
                    "description": "Use one-line format",
                    "default": True,
                },
                "since": {
                    "type": "string",
                    "description": "Show commits since date (e.g., '1 week ago')",
                },
            },
        },
    ),
    
    "git_blame": Tool(
        name="git_blame",
        description="Show what revision and author last modified each line of a file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File to blame",
                },
                "lines": {
                    "type": "string",
                    "description": "Line range (e.g., '10,20')",
                },
            },
            "required": ["path"],
        },
    ),
    
    "git_show": Tool(
        name="git_show",
        description="Show commit details and diff.",
        parameters={
            "type": "object",
            "properties": {
                "commit": {
                    "type": "string",
                    "description": "Commit to show (default: HEAD)",
                    "default": "HEAD",
                },
                "path": {
                    "type": "string",
                    "description": "Show only changes to specific file",
                },
            },
        },
    ),
    
    # ==========================================================================
    # Staging Operations (WORKSPACE trust level)
    # ==========================================================================
    
    "git_add": Tool(
        name="git_add",
        description="Stage files for commit. Safe operation - doesn't modify history.",
        parameters={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to stage",
                },
                "all": {
                    "type": "boolean",
                    "description": "Stage all changes",
                    "default": False,
                },
            },
        },
    ),
    
    "git_restore": Tool(
        name="git_restore",
        description="Restore working tree files or unstage files.",
        parameters={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to restore",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Unstage files (--staged)",
                    "default": False,
                },
                "source": {
                    "type": "string",
                    "description": "Restore from specific commit",
                },
            },
            "required": ["paths"],
        },
    ),
    
    # ==========================================================================
    # Write Operations (SHELL trust level - modifies history/branches)
    # ==========================================================================
    
    "git_commit": Tool(
        name="git_commit",
        description="Create a commit with staged changes. Modifies repository history.",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "amend": {
                    "type": "boolean",
                    "description": "Amend previous commit (rewrites history)",
                    "default": False,
                },
            },
            "required": ["message"],
        },
    ),
    
    "git_branch": Tool(
        name="git_branch",
        description="List, create, or delete branches.",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Branch name to create (omit to list)",
                },
                "delete": {
                    "type": "boolean",
                    "description": "Delete the branch",
                    "default": False,
                },
                "force": {
                    "type": "boolean",
                    "description": "Force delete even if unmerged (-D)",
                    "default": False,
                },
            },
        },
    ),
    
    "git_checkout": Tool(
        name="git_checkout",
        description="Switch branches or restore files.",
        parameters={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Branch name or commit to checkout",
                },
                "create": {
                    "type": "boolean",
                    "description": "Create new branch (-b)",
                    "default": False,
                },
            },
            "required": ["target"],
        },
    ),
    
    "git_stash": Tool(
        name="git_stash",
        description="Stash or restore uncommitted changes.",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["push", "pop", "list", "drop", "apply"],
                    "description": "Stash action",
                    "default": "push",
                },
                "message": {
                    "type": "string",
                    "description": "Stash message (for push)",
                },
                "index": {
                    "type": "integer",
                    "description": "Stash index for pop/drop/apply (default: 0)",
                },
            },
        },
    ),
    
    "git_reset": Tool(
        name="git_reset",
        description="Reset current HEAD to specified state. Can modify history.",
        parameters={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Commit to reset to (default: HEAD)",
                    "default": "HEAD",
                },
                "mode": {
                    "type": "string",
                    "enum": ["soft", "mixed", "hard"],
                    "description": "Reset mode: soft (keep staged), mixed (unstage), hard (discard all)",
                    "default": "mixed",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific paths to reset (unstage only)",
                },
            },
        },
    ),
    
    "git_merge": Tool(
        name="git_merge",
        description="Merge another branch into current branch.",
        parameters={
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to merge",
                },
                "no_ff": {
                    "type": "boolean",
                    "description": "Create merge commit even for fast-forward",
                    "default": False,
                },
                "message": {
                    "type": "string",
                    "description": "Custom merge commit message",
                },
            },
            "required": ["branch"],
        },
    ),
}
```

#### Restricted Environment Tools

**Security Principle**: Environment variables can contain secrets. We use an allowlist approach.

```python
# Safe environment variables that don't contain secrets
ENV_ALLOWLIST: frozenset[str] = frozenset({
    # System info
    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL",
    "PWD", "OLDPWD", "HOSTNAME", "LOGNAME",
    # Editor/display
    "EDITOR", "VISUAL", "PAGER", "DISPLAY", "COLORTERM",
    # Development (non-secret)
    "VIRTUAL_ENV", "CONDA_DEFAULT_ENV", "CONDA_PREFIX",
    "NVM_DIR", "GOPATH", "CARGO_HOME", "RUSTUP_HOME",
    "PYTHONPATH", "NODE_PATH", "GEM_HOME",
    # XDG
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
})

# Patterns that indicate secrets - NEVER expose these
ENV_BLOCKLIST_PATTERNS: tuple[str, ...] = (
    "*_KEY", "*_SECRET", "*_TOKEN", "*_PASSWORD", "*_CREDENTIAL*",
    "*_API_KEY", "*API_KEY*", "AWS_*", "GITHUB_*", "OPENAI_*",
    "ANTHROPIC_*", "AZURE_*", "GCP_*", "GOOGLE_*",
    "*_PRIVATE_*", "*_AUTH*", "*DATABASE_URL*", "*CONNECTION_STRING*",
)


ENV_TOOLS: dict[str, Tool] = {
    "get_env": Tool(
        name="get_env",
        description=(
            "Get environment variable value. "
            "Only safe, non-secret variables are accessible (PATH, HOME, EDITOR, etc.). "
            "Secret variables (API keys, tokens, passwords) are blocked for security."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Environment variable name (must be in allowlist)",
                },
            },
            "required": ["name"],
        },
    ),
    
    "list_env": Tool(
        name="list_env",
        description="List available (non-secret) environment variables.",
        parameters={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Optional prefix filter (e.g., 'XDG_')",
                },
            },
        },
    ),
}
```

**Handler implementation with security**:

```python
import fnmatch


def _is_env_blocked(name: str) -> bool:
    """Check if an environment variable name matches blocked patterns."""
    name_upper = name.upper()
    for pattern in ENV_BLOCKLIST_PATTERNS:
        if fnmatch.fnmatch(name_upper, pattern):
            return True
    return False


async def get_env(self, args: dict) -> str:
    """Get environment variable with security restrictions."""
    name = args["name"]
    
    # Check blocklist first (secrets)
    if _is_env_blocked(name):
        return f"[BLOCKED] Environment variable '{name}' may contain secrets and cannot be accessed."
    
    # Check allowlist
    if name not in ENV_ALLOWLIST:
        return (
            f"[NOT ALLOWED] Environment variable '{name}' is not in the allowlist. "
            f"Use list_env to see available variables."
        )
    
    value = os.environ.get(name)
    if value is None:
        return f"[NOT SET] Environment variable '{name}' is not set."
    
    return value


async def list_env(self, args: dict) -> str:
    """List available environment variables."""
    filter_prefix = args.get("filter", "").upper()
    
    available = []
    for name in sorted(ENV_ALLOWLIST):
        if filter_prefix and not name.startswith(filter_prefix):
            continue
        value = os.environ.get(name)
        if value:
            # Truncate long values
            display = value if len(value) <= 50 else f"{value[:47]}..."
            available.append(f"{name}={display}")
    
    if not available:
        return "No matching environment variables found."
    
    return "\n".join(available)
```

#### Updated Trust Levels

```python
class ToolTrust(Enum):
    """Trust levels control tool availability.
    
    Security principle: Higher trust must be explicitly requested.
    Default remains WORKSPACE for safety.
    """
    
    DISCOVERY = "discovery"   # list_files, search_files
    READ_ONLY = "read_only"   # + read_file, git read operations
    WORKSPACE = "workspace"   # + write_file, git_add, git_restore (DEFAULT)
    SHELL = "shell"           # + run_command, git write operations
    FULL = "full"             # + web_search, web_fetch, get_env


# Updated tool assignments
TRUST_LEVEL_TOOLS: dict[ToolTrust, frozenset[str]] = {
    ToolTrust.DISCOVERY: frozenset({
        "list_files", "search_files",
    }),
    
    ToolTrust.READ_ONLY: frozenset({
        "list_files", "search_files", "read_file",
        # Git read operations - safe, no side effects
        "git_status", "git_diff", "git_log", "git_blame", "git_show",
    }),
    
    ToolTrust.WORKSPACE: frozenset({
        "list_files", "search_files", "read_file", "write_file",
        "git_status", "git_diff", "git_log", "git_blame", "git_show",
        # Staging operations - reversible, don't modify history
        "git_add", "git_restore",
    }),
    
    ToolTrust.SHELL: frozenset({
        "list_files", "search_files", "read_file", "write_file", "run_command",
        "git_status", "git_diff", "git_log", "git_blame", "git_show",
        "git_add", "git_restore",
        # History-modifying operations - require explicit trust
        "git_commit", "git_branch", "git_checkout", "git_stash", 
        "git_reset", "git_merge",
    }),
    
    ToolTrust.FULL: frozenset({
        # All previous tools
        "list_files", "search_files", "read_file", "write_file", "run_command",
        "git_status", "git_diff", "git_log", "git_blame", "git_show",
        "git_add", "git_restore",
        "git_commit", "git_branch", "git_checkout", "git_stash",
        "git_reset", "git_merge",
        # Network access
        "web_search", "web_fetch",
        # Restricted environment access (allowlist enforced)
        "get_env", "list_env",
    }),
}
```

---

### Part 2: Context Reference Syntax

#### `@` Reference Grammar

```
reference     := "@" ref_type (":" ref_modifier)?
ref_type      := "file" | "dir" | "selection" | "clipboard" | "git" | "env"
ref_modifier  := identifier | path

Examples:
  @file              → currently focused file (from IDE context)
  @file:auth.py      → specific file
  @dir               → current directory listing
  @dir:src/          → specific directory listing
  @selection         → selected text (from IDE)
  @clipboard         → clipboard contents
  @git               → git status summary
  @git:staged        → staged changes diff
  @git:HEAD          → current commit diff
  @git:HEAD~3        → last 3 commits
  @git:branch        → current branch name
  @env:PATH          → environment variable (allowlist only)
```

#### Context Size Limits

Large content can bloat prompts and exceed context limits. We implement tiered handling:

```python
# Context size thresholds
MAX_INLINE_CHARS = 500       # Inline directly in prompt
MAX_CONTEXT_CHARS = 8192     # Include as separate context block
MAX_TOTAL_CONTEXT = 32768    # Total context budget per request


@dataclass
class ResolvedContext:
    """Result of resolving a context reference."""
    
    ref: ContextReference
    content: str
    truncated: bool = False
    original_size: int = 0
    
    @property
    def summary(self) -> str:
        """Short summary for inline use."""
        if self.truncated:
            return f"[{self.ref.raw}: {self.original_size:,} chars, truncated to {len(self.content):,}]"
        return f"[{self.ref.raw}: {len(self.content):,} chars]"
```

#### Context Parser and Resolver

```python
@dataclass
class ContextReference:
    """Parsed @ reference."""
    
    ref_type: str           # file, dir, git, etc.
    modifier: str | None    # Optional modifier after :
    raw: str                # Original text (@file:auth.py)

    @classmethod
    def parse(cls, text: str) -> list[ContextReference]:
        """Extract all @ references from text."""
        # Match @word or @word:modifier (modifier can include paths with /)
        pattern = r'@(\w+)(?::([^\s]+))?'
        refs = []
        for match in re.finditer(pattern, text):
            refs.append(cls(
                ref_type=match.group(1),
                modifier=match.group(2),
                raw=match.group(0),
            ))
        return refs


class ContextResolver:
    """Resolves @ references to actual content with size management."""
    
    def __init__(
        self,
        workspace_root: Path,
        ide_context: IDEContext | None = None,
        max_inline: int = MAX_INLINE_CHARS,
        max_context: int = MAX_CONTEXT_CHARS,
    ):
        self.workspace = workspace_root
        self.ide = ide_context
        self.max_inline = max_inline
        self.max_context = max_context
    
    async def resolve(self, ref: ContextReference) -> ResolvedContext:
        """Resolve a reference to its content with size limits."""
        
        try:
            content = await self._fetch_content(ref)
        except Exception as e:
            return ResolvedContext(
                ref=ref,
                content=f"[Error resolving {ref.raw}: {e}]",
            )
        
        original_size = len(content)
        truncated = False
        
        # Apply size limits
        if len(content) > self.max_context:
            content = content[:self.max_context]
            truncated = True
        
        return ResolvedContext(
            ref=ref,
            content=content,
            truncated=truncated,
            original_size=original_size,
        )
    
    async def _fetch_content(self, ref: ContextReference) -> str:
        """Fetch raw content for a reference."""
        
        if ref.ref_type == "file":
            return await self._resolve_file(ref.modifier)
        
        elif ref.ref_type == "dir":
            return await self._resolve_dir(ref.modifier)
        
        elif ref.ref_type == "git":
            return await self._resolve_git(ref.modifier)
        
        elif ref.ref_type == "selection":
            return self._resolve_selection()
        
        elif ref.ref_type == "clipboard":
            return await self._read_clipboard()
        
        elif ref.ref_type == "env":
            return self._resolve_env(ref.modifier)
        
        raise ValueError(f"Unknown reference type: {ref.ref_type}")
    
    async def _resolve_file(self, path: str | None) -> str:
        """Resolve @file or @file:path."""
        if path:
            target = self.workspace / path
        else:
            # Use IDE focused file if available
            if self.ide and self.ide.focused_file:
                target = Path(self.ide.focused_file)
            else:
                raise ValueError(
                    "No file specified and no IDE context available. "
                    "Use @file:path/to/file.py to specify a file, or "
                    "provide IDE context via --ide-context or SUNWELL_IDE_CONTEXT."
                )
        
        if not target.exists():
            raise FileNotFoundError(f"File not found: {target}")
        
        # Security: ensure within workspace
        try:
            target.resolve().relative_to(self.workspace.resolve())
        except ValueError:
            raise PermissionError(f"Path escapes workspace: {target}")
        
        return target.read_text(encoding="utf-8", errors="replace")
    
    async def _resolve_dir(self, path: str | None) -> str:
        """Resolve @dir or @dir:path to directory listing."""
        target = self.workspace / (path or ".")
        
        if not target.is_dir():
            raise ValueError(f"Not a directory: {target}")
        
        files = []
        for f in sorted(target.iterdir()):
            if f.name.startswith("."):
                continue  # Skip hidden files
            suffix = "/" if f.is_dir() else ""
            files.append(f"{f.name}{suffix}")
        
        return "\n".join(files[:100]) or "(empty directory)"
    
    async def _resolve_git(self, modifier: str | None) -> str:
        """Resolve @git references."""
        import subprocess
        
        if modifier is None or modifier == "status":
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, cwd=self.workspace
            )
            return result.stdout or "Working tree clean"
        
        elif modifier == "staged":
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, text=True, cwd=self.workspace
            )
            return result.stdout or "Nothing staged"
        
        elif modifier == "branch":
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=self.workspace
            )
            return result.stdout.strip() or "(detached HEAD)"
        
        elif modifier.startswith("HEAD"):
            # @git:HEAD or @git:HEAD~3
            result = subprocess.run(
                ["git", "log", modifier, "-1", "--format=%H %s"],
                capture_output=True, text=True, cwd=self.workspace
            )
            if result.returncode != 0:
                raise ValueError(f"Invalid git reference: {modifier}")
            return result.stdout.strip()
        
        raise ValueError(f"Unknown git modifier: {modifier}")
    
    def _resolve_selection(self) -> str:
        """Resolve @selection from IDE context."""
        if not self.ide:
            raise ValueError(
                "No IDE context available for @selection. "
                "Provide context via --ide-context or SUNWELL_IDE_CONTEXT env var. "
                "See 'IDE Context Bridge' section for integration details."
            )
        
        if not self.ide.selection:
            raise ValueError(
                "No text selected in IDE. "
                "Select text in your editor before using @selection."
            )
        
        return self.ide.selection
    
    def _resolve_env(self, name: str | None) -> str:
        """Resolve @env:NAME with security restrictions."""
        if not name:
            raise ValueError("Environment variable name required: @env:NAME")
        
        # Check blocklist
        if _is_env_blocked(name):
            raise PermissionError(
                f"Environment variable '{name}' may contain secrets and cannot be accessed."
            )
        
        # Check allowlist
        if name not in ENV_ALLOWLIST:
            raise PermissionError(
                f"Environment variable '{name}' is not in the allowlist. "
                f"Only safe, non-secret variables are accessible."
            )
        
        value = os.environ.get(name)
        if value is None:
            return f"(not set)"
        
        return value
```

#### Integration with Routing

```python
@dataclass
class ExpandedTask:
    """Task with expanded context references."""
    
    original: str
    expanded: str
    context_blocks: list[ResolvedContext]
    total_context_chars: int


async def preprocess_task(
    task: str, 
    resolver: ContextResolver,
    max_total_context: int = MAX_TOTAL_CONTEXT,
) -> ExpandedTask:
    """Expand @ references in task before routing."""
    
    refs = ContextReference.parse(task)
    
    if not refs:
        return ExpandedTask(
            original=task,
            expanded=task,
            context_blocks=[],
            total_context_chars=0,
        )
    
    # Resolve each reference
    resolved = []
    for ref in refs:
        ctx = await resolver.resolve(ref)
        resolved.append(ctx)
    
    # Build expanded task with inline/context split
    expanded = task
    context_blocks = []
    total_chars = 0
    
    for ctx in resolved:
        if len(ctx.content) <= resolver.max_inline:
            # Small content: inline directly
            expanded = expanded.replace(ctx.ref.raw, ctx.content)
        else:
            # Large content: reference inline, full content as context block
            expanded = expanded.replace(ctx.ref.raw, ctx.summary)
            context_blocks.append(ctx)
            total_chars += len(ctx.content)
    
    # Check total context budget
    if total_chars > max_total_context:
        # Truncate oldest/largest contexts to fit
        context_blocks = _fit_context_budget(context_blocks, max_total_context)
        total_chars = sum(len(c.content) for c in context_blocks)
    
    return ExpandedTask(
        original=task,
        expanded=expanded,
        context_blocks=context_blocks,
        total_context_chars=total_chars,
    )
```

---

### Part 3: Smart Defaults

#### Extending Existing WorkspaceDetector

Rather than creating a new class, we extend the existing `WorkspaceDetector` in `src/sunwell/workspace/detector.py`:

```python
# src/sunwell/workspace/detector.py

from dataclasses import dataclass, field
from pathlib import Path
from sunwell.tools.types import ToolTrust


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    """Extended workspace configuration with trust suggestions."""
    
    root: Path
    """Root directory of the workspace."""
    
    is_git: bool
    """Whether this is a git repository."""
    
    name: str
    """Name of the workspace (directory name)."""
    
    ignore_patterns: tuple[str, ...]
    """Patterns to ignore when scanning files."""
    
    # New fields for RFC-024
    suggested_trust: ToolTrust = ToolTrust.WORKSPACE
    """Suggested trust level based on detection. NOT automatically applied."""
    
    has_sunwell_config: bool = False
    """Whether .sunwell/config.yaml exists."""
    
    config_trust: ToolTrust | None = None
    """Trust level from .sunwell/config.yaml if present."""
    
    subprojects: tuple[Path, ...] = ()
    """Detected subproject roots in monorepo."""
    
    current_subproject: Path | None = None
    """Which subproject cwd is in (if any)."""


class WorkspaceDetector:
    """Detects workspace root and configuration.
    
    Extended for RFC-024 with:
    - .sunwell/config.yaml support
    - Trust level suggestions (not auto-applied)
    - Monorepo subproject detection
    """
    
    DEFAULT_IGNORE = (
        ".git", ".venv", "venv", "__pycache__", "node_modules",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc", "*.pyo",
        ".DS_Store", "*.egg-info", "dist", "build", ".tox", ".coverage", "htmlcov",
    )
    
    PROJECT_MARKERS = (
        "pyproject.toml", "setup.py", "setup.cfg",  # Python
        "package.json", "package-lock.json",         # Node.js
        "Cargo.toml", "Cargo.lock",                  # Rust
        "go.mod", "go.sum",                          # Go
        "pom.xml", "build.gradle", "build.gradle.kts",  # JVM
        "Makefile", "CMakeLists.txt",                # C/C++
        "Gemfile", "*.gemspec",                      # Ruby
        "composer.json",                             # PHP
    )
    
    def detect(self, start_path: Path | None = None) -> WorkspaceConfig:
        """Detect workspace from starting path.
        
        Detection order:
        1. Check for .sunwell/config.yaml (explicit configuration)
        2. Check for git repository root
        3. Check for project markers (pyproject.toml, package.json, etc.)
        4. Fall back to current directory
        
        Security note: Trust levels are SUGGESTED, not automatically applied.
        Users must explicitly opt in via --trust or .sunwell/config.yaml.
        
        Args:
            start_path: Path to start detection from. Defaults to cwd.
            
        Returns:
            WorkspaceConfig with detected settings and suggestions.
        """
        start = Path(start_path) if start_path else Path.cwd()
        start = start.resolve()
        
        # 1. Look for .sunwell/ config (explicit user configuration)
        sunwell_root = self._find_sunwell_config(start)
        if sunwell_root:
            return self._load_sunwell_config(sunwell_root, start)
        
        # 2. Look for git root
        git_root = self._find_git_root(start)
        if git_root:
            subprojects = self._detect_subprojects(git_root)
            current_sub = self._find_current_subproject(start, subprojects)
            
            return WorkspaceConfig(
                root=git_root,
                is_git=True,
                name=git_root.name,
                ignore_patterns=self._load_gitignore(git_root),
                # SUGGEST read_only for git repos - safe default
                # Users can opt into workspace/shell via --trust
                suggested_trust=ToolTrust.READ_ONLY,
                subprojects=tuple(subprojects),
                current_subproject=current_sub,
            )
        
        # 3. Look for project markers
        project_root = self._find_project_root(start)
        if project_root:
            return WorkspaceConfig(
                root=project_root,
                is_git=False,
                name=project_root.name,
                ignore_patterns=self.DEFAULT_IGNORE,
                suggested_trust=ToolTrust.READ_ONLY,
            )
        
        # 4. Fall back to cwd - most conservative
        return WorkspaceConfig(
            root=start if start.is_dir() else start.parent,
            is_git=False,
            name=start.name,
            ignore_patterns=self.DEFAULT_IGNORE,
            suggested_trust=ToolTrust.DISCOVERY,  # Unknown location = very conservative
        )
    
    def _find_sunwell_config(self, start: Path) -> Path | None:
        """Walk up looking for .sunwell/ directory."""
        current = start
        while current != current.parent:
            if (current / ".sunwell").is_dir():
                return current
            current = current.parent
        return None
    
    def _load_sunwell_config(self, root: Path, cwd: Path) -> WorkspaceConfig:
        """Load configuration from .sunwell/config.yaml."""
        import yaml
        
        config_path = root / ".sunwell" / "config.yaml"
        config = {}
        
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        
        # Parse trust level from config
        config_trust = None
        trust_str = config.get("trust_level")
        if trust_str:
            try:
                config_trust = ToolTrust.from_string(trust_str)
            except ValueError:
                pass  # Invalid trust level in config, ignore
        
        # Check for git
        is_git = (root / ".git").exists()
        
        return WorkspaceConfig(
            root=root,
            is_git=is_git,
            name=root.name,
            ignore_patterns=tuple(config.get("ignore", self.DEFAULT_IGNORE)),
            has_sunwell_config=True,
            config_trust=config_trust,
            # If config specifies trust, suggest that; otherwise suggest workspace
            suggested_trust=config_trust or ToolTrust.WORKSPACE,
            subprojects=tuple(self._detect_subprojects(root)) if is_git else (),
            current_subproject=self._find_current_subproject(
                cwd, self._detect_subprojects(root)
            ) if is_git else None,
        )
    
    def _find_git_root(self, path: Path) -> Path | None:
        """Find git repository root."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def _find_project_root(self, start: Path) -> Path | None:
        """Walk up looking for project markers."""
        current = start
        while current != current.parent:
            for marker in self.PROJECT_MARKERS:
                if "*" in marker:
                    # Glob pattern
                    if list(current.glob(marker)):
                        return current
                elif (current / marker).exists():
                    return current
            current = current.parent
        return None
    
    def _detect_subprojects(self, root: Path) -> list[Path]:
        """Find project roots within a monorepo."""
        subprojects = set()
        
        # Skip these directories entirely
        skip_dirs = {".git", "node_modules", "vendor", ".venv", "venv", 
                     "__pycache__", "dist", "build", ".tox"}
        
        for marker in self.PROJECT_MARKERS:
            if "*" in marker:
                continue  # Skip glob patterns for performance
            
            for match in root.rglob(marker):
                # Check if any parent is in skip list
                if any(skip in match.parts for skip in skip_dirs):
                    continue
                
                # Don't include the root itself
                if match.parent != root:
                    subprojects.add(match.parent)
        
        return sorted(subprojects)
    
    def _find_current_subproject(
        self, cwd: Path, subprojects: list[Path]
    ) -> Path | None:
        """Find which subproject cwd is inside."""
        cwd = cwd.resolve()
        for sub in sorted(subprojects, key=lambda p: len(p.parts), reverse=True):
            try:
                cwd.relative_to(sub)
                return sub
            except ValueError:
                continue
        return None
    
    def _load_gitignore(self, root: Path) -> tuple[str, ...]:
        """Load ignore patterns from .gitignore."""
        patterns = list(self.DEFAULT_IGNORE)
        gitignore = root / ".gitignore"
        if gitignore.exists():
            with open(gitignore) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        return tuple(patterns)
```

#### Trust Level Policy: Conservative by Default

**Security principle**: Trust escalation requires explicit user action.

```python
# Default trust level - WORKSPACE is a good balance
DEFAULT_TRUST = ToolTrust.WORKSPACE

# Trust resolution order:
# 1. Explicit --trust flag (highest priority)
# 2. .sunwell/config.yaml trust_level
# 3. DEFAULT_TRUST (WORKSPACE)
#
# NOTE: suggested_trust from detection is informational only
# It does NOT automatically apply - users must opt in


def resolve_trust_level(
    explicit_trust: str | None,
    config: WorkspaceConfig,
) -> ToolTrust:
    """Resolve trust level with explicit > config > default precedence.
    
    Security: We NEVER auto-escalate based on detection alone.
    """
    # 1. Explicit flag takes precedence
    if explicit_trust:
        return ToolTrust.from_string(explicit_trust)
    
    # 2. Config file trust (user explicitly configured)
    if config.config_trust:
        return config.config_trust
    
    # 3. Default
    return DEFAULT_TRUST
```

#### CLI Changes

```python
@click.command()
@click.argument("task", nargs=-1)
@click.option(
    "--trust", 
    type=click.Choice(["discovery", "read_only", "workspace", "shell", "full"]),
    default=None,  # None = use config or default
    help="Tool trust level. Default: workspace (or from .sunwell/config.yaml)"
)
@click.option(
    "--workspace", "-w", 
    type=click.Path(exists=True),
    default=None,  # None = auto-detect
    help="Workspace root. Auto-detected if not specified."
)
@click.option(
    "--show-detection",
    is_flag=True,
    help="Show workspace detection results and suggested trust level."
)
def run(task, trust, workspace, show_detection):
    """Run a task with Sunwell.
    
    Workspace is auto-detected from git root or project markers.
    Trust level defaults to 'workspace' unless configured in .sunwell/config.yaml.
    
    Examples:
    
        # Auto-detect workspace, use default trust
        sunwell "review auth.py"
        
        # Explicit trust for git operations
        sunwell "commit these changes" --trust shell
        
        # Show what was detected
        sunwell "explain @file" --show-detection
    """
    # Auto-detect workspace
    detector = WorkspaceDetector()
    config = detector.detect(Path(workspace) if workspace else None)
    
    if show_detection:
        click.echo(f"Workspace: {config.root}")
        click.echo(f"Git repo: {config.is_git}")
        click.echo(f"Suggested trust: {config.suggested_trust.value}")
        if config.config_trust:
            click.echo(f"Config trust: {config.config_trust.value}")
        if config.subprojects:
            click.echo(f"Subprojects: {len(config.subprojects)}")
        click.echo()
    
    # Resolve trust level (explicit > config > default)
    trust_level = resolve_trust_level(trust, config)
    
    # ... rest of execution
```

---

## Sunwell Configuration File

Users can create `.sunwell/config.yaml` to configure their workspace:

```yaml
# .sunwell/config.yaml

# Trust level for this workspace
# Options: discovery, read_only, workspace, shell, full
# Default if not specified: workspace
trust_level: workspace

# Additional paths to ignore (merged with defaults)
ignore:
  - "*.log"
  - "tmp/"
  - "coverage/"

# Tool-specific configuration
tools:
  # Rate limits (override defaults)
  rate_limits:
    max_tool_calls_per_minute: 50
    max_file_writes_per_minute: 20
  
  # Additional blocked patterns for file access
  blocked_paths:
    - "**/*.secret"
    - "**/credentials/**"
  
  # Shell command allowlist (for SHELL trust level)
  # If specified, only these commands are allowed
  command_allowlist:
    - "make *"
    - "pytest *"
    - "npm test"
    - "cargo build"
    - "cargo test"

# Context reference defaults
context:
  max_inline_chars: 500
  max_context_chars: 8192
```

---

## IDE Context Bridge

For IDE integrations (VS Code, Neovim, Cursor), provide a context bridge protocol:

```python
@dataclass
class IDEContext:
    """Context from IDE extension.
    
    Passed via:
    - Environment variable: SUNWELL_IDE_CONTEXT (path to JSON file)
    - CLI option: --ide-context <path>
    - Stdin pipe: echo '{"focused_file": "..."}' | sunwell ...
    """
    
    focused_file: str | None = None
    """Currently focused file path (absolute)."""
    
    selection: str | None = None
    """Selected text content."""
    
    cursor_position: tuple[int, int] | None = None
    """Cursor position as (line, column), 0-indexed."""
    
    open_files: list[str] = field(default_factory=list)
    """All open file paths."""
    
    visible_range: tuple[int, int] | None = None
    """Visible line range as (start, end)."""
    
    diagnostics: list[dict] | None = None
    """Linter errors/warnings from IDE."""
    
    workspace_folders: list[str] = field(default_factory=list)
    """Workspace folders from IDE (multi-root support)."""
    
    @classmethod
    def from_json(cls, data: dict) -> "IDEContext":
        """Parse from JSON (from IDE extension)."""
        return cls(
            focused_file=data.get("focused_file"),
            selection=data.get("selection"),
            cursor_position=tuple(data["cursor_position"]) if data.get("cursor_position") else None,
            open_files=data.get("open_files", []),
            visible_range=tuple(data["visible_range"]) if data.get("visible_range") else None,
            diagnostics=data.get("diagnostics"),
            workspace_folders=data.get("workspace_folders", []),
        )
    
    @classmethod
    def from_env(cls) -> "IDEContext | None":
        """Load from SUNWELL_IDE_CONTEXT environment variable."""
        import json
        
        path = os.environ.get("SUNWELL_IDE_CONTEXT")
        if not path:
            return None
        
        try:
            with open(path) as f:
                return cls.from_json(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
```

### VS Code Extension Protocol

For VS Code extensions, the context file should be written to a temp location:

```typescript
// VS Code extension example
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

function getSunwellContext(): object {
    const editor = vscode.window.activeTextEditor;
    
    return {
        focused_file: editor?.document.uri.fsPath,
        selection: editor?.document.getText(editor.selection),
        cursor_position: editor ? [editor.selection.active.line, editor.selection.active.character] : null,
        open_files: vscode.workspace.textDocuments.map(d => d.uri.fsPath),
        visible_range: editor ? [
            editor.visibleRanges[0]?.start.line,
            editor.visibleRanges[0]?.end.line
        ] : null,
        diagnostics: vscode.languages.getDiagnostics(editor?.document.uri).map(d => ({
            line: d.range.start.line,
            message: d.message,
            severity: d.severity,
        })),
        workspace_folders: vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath) || [],
    };
}

async function runSunwell(task: string) {
    const contextPath = path.join(os.tmpdir(), `sunwell-context-${process.pid}.json`);
    fs.writeFileSync(contextPath, JSON.stringify(getSunwellContext()));
    
    // Set env and run sunwell
    const terminal = vscode.window.createTerminal({
        name: 'Sunwell',
        env: { SUNWELL_IDE_CONTEXT: contextPath }
    });
    terminal.sendText(`sunwell "${task}"`);
    terminal.show();
}
```

---

## Mode Unification and Feature Parity

### Problem: Feature Gaps Across Commands

Current Sunwell has inconsistent feature availability:

| Feature | `apply` | `ask` | `chat` | `exec` |
|---------|---------|-------|--------|--------|
| **Skills** | ✅ `--skill` | ❌ | ❌ **GAP** | ✅ |
| **Tools** | ⚠️ `--tools` | ❌ | ⚠️ `--tools` | ❌ |
| **Routing** | ⚠️ `--router-model` | ❌ | ⚠️ `--router-model` | ❌ |
| **Context refs** | ❌ | ❌ | ❌ | ❌ |

### Proposal: Enable Features by Default

```yaml
apply:
  tools: true              # Was: false
  attunement: true         # Was: --router-model required
  context_refs: true       # New

ask:
  tools: true              # Was: none
  attunement: true         # Was: none

chat:
  tools: true              # Was: --tools required ("Agent mode")
  skills: true             # NEW: /skill command
  attunement: true         # Was: --router-model required
```

### New Chat Slash Commands

| Command | Description |
|---------|-------------|
| `/skill [name] [task]` | Execute skill (list if no args) |
| `/skills` | List available skills |
| `/cast <spell>` | Execute spell (RFC-021) |
| `/spells` | List available spells |
| `/lens` | Show current lens info |
| `/trust <level>` | Change trust level |

### Cognitive Routing by Default

```python
def get_default_router(lenses: list[str]) -> CognitiveRouter:
    """Auto-detect router - no flags needed."""
    # Try tiny local models first
    for model in ["gemma3:1b", "phi-3-mini", "qwen2:0.5b"]:
        if is_model_available("ollama", model):
            return CognitiveRouter(router_model=OllamaModel(model), available_lenses=lenses)
    # Fallback: heuristic routing (no LLM)
    return CognitiveRouter(router_model=None, available_lenses=lenses)
```

---

## Summary of Changes

| Change | Before | After |
|--------|--------|-------|
| **Tools default** | Disabled (`--tools`) | Enabled |
| **Skills in chat** | ❌ | `/skill` command |
| **Attunement** | `--router-model` | Automatic |
| **Default trust** | `workspace` | `workspace` (unchanged - security preserved) |
| **Workspace detection** | Required `--workspace` | Auto-detect git/project root |
| **Git tools** | None (use `run_command`) | 12 dedicated git tools |
| **Context syntax** | None | `@file`, `@git:staged`, etc. |
| **Trust for git read** | N/A | `read_only` |
| **Trust for git staging** | N/A | `workspace` |
| **Trust for git commits** | N/A | `shell` (explicit opt-in) |
| **Environment access** | None | Allowlist-restricted `get_env` |
| **Context size** | N/A | 500 inline / 8KB context / 32KB total limits |

---

## Implementation Plan

### Phase 1: Git Tools (Week 1)
- Add git tool definitions to `builtins.py`
- Implement handlers in `handlers.py`
- Add to trust level mappings
- Unit tests for all git operations

### Phase 2: Context References (Week 2)
- Create `src/sunwell/context/` module
- Implement `ContextReference` parser
- Implement `ContextResolver` with size limits
- Integrate with routing
- Tests for context expansion

### Phase 3: Smart Defaults (Week 3)
- Extend `WorkspaceDetector` (not new class)
- Add `.sunwell/config.yaml` support
- Update CLI for auto-detection
- Add `--show-detection` flag
- Documentation for configuration

### Phase 4: IDE Bridge (Week 4)
- Define `IDEContext` protocol
- Add `--ide-context` CLI option
- Create VS Code extension skeleton
- Document integration protocol
- Example extensions for VS Code/Neovim

---

## Security Considerations

### Trust Level Security

| Trust Level | Can Access | Cannot Access |
|-------------|------------|---------------|
| `discovery` | File listings, search | File contents, any writes |
| `read_only` | + File contents, git status/diff/log | Writes, shell, commits |
| `workspace` | + File writes, git add/restore | Shell, commits, env vars |
| `shell` | + Shell commands, git commits | Web access, env vars |
| `full` | + Web access, allowlisted env vars | Blocked env vars (secrets) |

### Environment Variable Security

- **Allowlist approach**: Only explicitly safe variables accessible
- **Blocklist patterns**: Common secret patterns always blocked
- **No wildcard access**: Cannot enumerate all env vars

### Context Reference Security

- **Workspace jail**: `@file` cannot escape workspace
- **Size limits**: Prevent prompt injection via huge files
- **IDE context validation**: Paths validated before use

---

## Migration

**Breaking changes**: None. All changes are additive.

**Behavior changes**:
- Workspace now auto-detected (can still use `--workspace`)
- `.sunwell/config.yaml` respected if present

**Deprecations**: None.

---

## References

- RFC-012: Tool Calling
- RFC-020: Cognitive Router
- RFC-022: Tiered Attunement
- [Git Internals](https://git-scm.com/book/en/v2/Git-Internals)
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-16 | Initial draft |
| 2026-01-16 | **Security revision**: Keep `workspace` as default trust (not `shell`) |
| 2026-01-16 | **Security revision**: Add env var allowlist/blocklist for `get_env` |
| 2026-01-16 | Added `git_reset`, `git_merge`, `git_restore` tools |
| 2026-01-16 | Added context size limits (500/8KB/32KB thresholds) |
| 2026-01-16 | Extended existing `WorkspaceDetector` instead of new class |
| 2026-01-16 | Improved `@selection` error messages with setup instructions |
| 2026-01-16 | Added `.sunwell/config.yaml` specification |
| 2026-01-16 | Added monorepo subproject detection |
