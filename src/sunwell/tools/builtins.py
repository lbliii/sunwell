"""Built-in core tools for RFC-012 tool calling.

These are standard tools that don't require skill definitions.
Extended for RFC-024 with git operations and environment access.
"""

from sunwell.models.protocol import Tool


# =============================================================================
# Core Tool Definitions
# =============================================================================

CORE_TOOLS: dict[str, Tool] = {
    # File Operations
    "read_file": Tool(
        name="read_file",
        description="Read contents of a file. Returns the file content wrapped in code fences.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
            },
            "required": ["path"],
        },
    ),
    
    "write_file": Tool(
        name="write_file",
        description="Write content to a file. Creates parent directories if needed. Overwrites existing files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    ),
    
    "list_files": Tool(
        name="list_files",
        description="List files in a directory. Returns file paths relative to workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to workspace (default: current directory)",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (default: all files)",
                    "default": "*",
                },
            },
        },
    ),
    
    # Search
    "search_files": Tool(
        name="search_files",
        description="Search for a text pattern in files using ripgrep (falls back to grep). Returns matching lines with file:line references.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                    "default": ".",
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern to filter which files to search (default: all files)",
                    "default": "**/*",
                },
            },
            "required": ["pattern"],
        },
    ),
    
    # Shell (sandboxed)
    "run_command": Tool(
        name="run_command",
        description="Run a shell command in a sandboxed environment. Use for build commands, tests, or inspection. Commands that modify the filesystem may be restricted based on trust level.",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command (default: workspace root)",
                    "default": ".",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30, max: 300)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    ),
    
    # Directory Operations
    "mkdir": Tool(
        name="mkdir",
        description="Create a directory. Creates parent directories if needed (like mkdir -p).",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to create, relative to workspace root",
                },
            },
            "required": ["path"],
        },
    ),
    
    # Git Repository Initialization
    "git_init": Tool(
        name="git_init",
        description="Initialize a new git repository. Creates the directory if it doesn't exist.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to initialize (default: current directory)",
                    "default": ".",
                },
            },
        },
    ),
    
    # Web Search (requires FULL trust level + API key)
    "web_search": Tool(
        name="web_search",
        description="Search the web for current information. Returns relevant snippets and URLs. Use when you need up-to-date information not available in local files.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5, max: 10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    
    "web_fetch": Tool(
        name="web_fetch",
        description="Fetch and extract content from a single web page URL. Returns the page title, main content, and links found.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                },
            },
            "required": ["url"],
        },
    ),
    
    # Git Information (read-only, safe at workspace level)
    "git_info": Tool(
        name="git_info",
        description="Get information about the current git repository: remote URLs, current branch, recent commits, and status.",
        parameters={
            "type": "object",
            "properties": {
                "include_status": {
                    "type": "boolean",
                    "description": "Include working directory status (default: true)",
                    "default": True,
                },
                "commit_count": {
                    "type": "integer",
                    "description": "Number of recent commits to show (default: 5)",
                    "default": 5,
                },
            },
        },
    ),
}


# =============================================================================
# Git Tools (RFC-024)
# =============================================================================

GIT_TOOLS: dict[str, Tool] = {
    # --------------------------------------------------------------------------
    # Read Operations (READ_ONLY trust level)
    # --------------------------------------------------------------------------
    
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
    
    # --------------------------------------------------------------------------
    # Staging Operations (WORKSPACE trust level)
    # --------------------------------------------------------------------------
    
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
    
    # --------------------------------------------------------------------------
    # Write Operations (SHELL trust level - modifies history/branches)
    # --------------------------------------------------------------------------
    
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


# =============================================================================
# Environment Tools (RFC-024)
# =============================================================================

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


# =============================================================================
# Expertise Tools (RFC-027: Self-Directed Expertise Retrieval)
# =============================================================================

EXPERTISE_TOOLS: dict[str, Tool] = {
    "get_expertise": Tool(
        name="get_expertise",
        description=(
            "Retrieve relevant heuristics and best practices for a topic. "
            "Use this BEFORE starting complex tasks to get domain-specific guidance. "
            "Returns heuristics with 'always' patterns (things to do) and 'never' patterns (things to avoid)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "The topic or area you need guidance on. "
                        "Be specific: 'error handling in async Python' is better than 'Python'."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of relevant heuristics to retrieve (default: 5, max: 10)",
                    "default": 5,
                },
            },
            "required": ["topic"],
        },
    ),
    
    "verify_against_expertise": Tool(
        name="verify_against_expertise",
        description=(
            "Verify code or content against retrieved heuristics. "
            "Use this BEFORE finalizing your response to check for violations. "
            "Returns a list of violations found and suggestions for improvement."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code or content to verify against expertise",
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional: specific areas to check (e.g., ['error_handling', 'type_safety']). "
                        "If not provided, checks against all retrieved heuristics."
                    ),
                },
            },
            "required": ["code"],
        },
    ),
    
    "list_expertise_areas": Tool(
        name="list_expertise_areas",
        description=(
            "List available heuristic categories in the current lens. "
            "Use this to discover what guidance is available before requesting specific expertise."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
}


def get_tools_for_trust_level(trust_level: str) -> tuple[Tool, ...]:
    """Get tools available at a given trust level.
    
    Args:
        trust_level: One of 'discovery', 'read_only', 'workspace', 'shell', 'full'
        
    Returns:
        Tuple of Tool objects available at that trust level
    """
    from sunwell.tools.types import ToolTrust, TRUST_LEVEL_TOOLS
    
    level = ToolTrust.from_string(trust_level)
    allowed_names = TRUST_LEVEL_TOOLS.get(level, frozenset())
    
    # Combine all tool dictionaries
    all_tools = {**CORE_TOOLS, **GIT_TOOLS, **ENV_TOOLS}
    
    return tuple(
        tool for name, tool in all_tools.items()
        if name in allowed_names
    )


def get_all_tools() -> dict[str, Tool]:
    """Get all available tools (for documentation or inspection).
    
    Returns:
        Dict of all tool definitions
    """
    return {**CORE_TOOLS, **GIT_TOOLS, **ENV_TOOLS, **EXPERTISE_TOOLS}
