"""Tool types and trust levels for RFC-012 tool calling."""


from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ToolTrust(Enum):
    """Trust levels control tool availability.

    Each level includes all tools from the previous levels.
    This extends TrustLevel from RFC-011 with tool-specific granularity.
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

    @classmethod
    def from_string(cls, value: str) -> ToolTrust:
        """Parse trust level from string."""
        return cls(value.lower())

    def includes(self, other: ToolTrust) -> bool:
        """Check if this trust level includes another.

        Higher trust levels include all tools from lower levels.
        """
        order = [ToolTrust.DISCOVERY, ToolTrust.READ_ONLY, ToolTrust.WORKSPACE, ToolTrust.SHELL, ToolTrust.FULL]
        return order.index(self) >= order.index(other)


# =============================================================================
# Tool Groups and Profiles (Agentic Infrastructure Upgrade)
# =============================================================================


TOOL_GROUPS: dict[str, frozenset[str]] = {
    "group:discovery": frozenset(["list_files", "search_files", "find_files"]),
    "group:read": frozenset(["read_file", "search_code"]),
    "group:write": frozenset(["write_file", "edit_file", "patch_file"]),
    "group:file_management": frozenset(["delete_file", "rename_file", "copy_file"]),
    "group:undo": frozenset(["undo_file", "list_backups", "restore_file"]),
    "group:shell": frozenset(["run_command"]),
    "group:git": frozenset(["git_status", "git_diff", "git_log", "git_commit", "git_add", "git_restore"]),
    "group:memory": frozenset(["memory_search", "memory_get"]),
    "group:web": frozenset(["web_search", "web_fetch"]),
    "group:expertise": frozenset(["get_expertise", "verify_against_expertise", "list_expertise_areas"]),
}
"""Tool groups for logical grouping. Use in allowed_tools or also_allow."""


class ToolProfile(Enum):
    """Named tool profiles that compose groups.

    Profiles provide semantic presets for common use cases.
    Each profile maps to a set of tool groups.
    """

    MINIMAL = "minimal"
    """Discovery only - list_files, search_files."""

    READ_ONLY = "read_only"
    """Discovery + read - safe for exploration."""

    CODING = "coding"
    """Read + write + shell + git - standard development."""

    RESEARCH = "research"
    """Read + memory + web - information gathering."""

    FULL = "full"
    """All tools - unrestricted."""


# Profile to groups mapping
PROFILE_GROUPS: dict[ToolProfile, tuple[str, ...]] = {
    ToolProfile.MINIMAL: ("group:discovery",),
    ToolProfile.READ_ONLY: ("group:discovery", "group:read"),
    ToolProfile.CODING: ("group:discovery", "group:read", "group:write", "group:shell", "group:git"),
    ToolProfile.RESEARCH: ("group:discovery", "group:read", "group:memory", "group:web", "group:expertise"),
    ToolProfile.FULL: tuple(TOOL_GROUPS.keys()),
}


def expand_tool_groups(tools: frozenset[str] | tuple[str, ...]) -> frozenset[str]:
    """Expand tool group references to individual tools.

    Args:
        tools: Set of tool names and/or group references (e.g., "group:read")

    Returns:
        Expanded set with groups replaced by their member tools
    """
    expanded: set[str] = set()
    for tool in tools:
        if tool in TOOL_GROUPS:
            expanded.update(TOOL_GROUPS[tool])
        else:
            expanded.add(tool)
    return frozenset(expanded)


def get_profile_tools(profile: ToolProfile) -> frozenset[str]:
    """Get all tools for a profile.

    Args:
        profile: The tool profile

    Returns:
        Set of all tool names in the profile
    """
    groups = PROFILE_GROUPS.get(profile, ())
    return expand_tool_groups(frozenset(groups))


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result from executing a tool."""

    tool_call_id: str
    success: bool
    output: str
    artifacts: tuple[str, ...] = ()  # Files created/modified (as strings for JSON serialization)
    execution_time_ms: int = 0


@dataclass(slots=True)
class ToolRateLimits:
    """Per-session rate limits to prevent abuse."""

    max_tool_calls_per_minute: int = 60
    max_file_writes_per_minute: int = 30  # Increased for multi-file generation
    max_shell_commands_per_minute: int = 10
    max_bytes_written_per_session: int = 50_000_000  # 50MB

    # Tracking
    _tool_calls: list[datetime] = field(default_factory=list, init=False)
    _file_writes: list[datetime] = field(default_factory=list, init=False)
    _shell_commands: list[datetime] = field(default_factory=list, init=False)
    _bytes_written: int = field(default=0, init=False)

    def _prune_old_entries(self, entries: list[datetime], window_seconds: int = 60) -> list[datetime]:
        """Remove entries older than the window."""
        cutoff = datetime.now()
        return [e for e in entries if (cutoff - e).total_seconds() < window_seconds]

    def check_tool_call(self) -> bool:
        """Check if a tool call is allowed. Returns True if allowed."""
        self._tool_calls = self._prune_old_entries(self._tool_calls)
        if len(self._tool_calls) >= self.max_tool_calls_per_minute:
            return False
        self._tool_calls.append(datetime.now())
        return True

    def check_file_write(self, bytes_count: int) -> bool:
        """Check if a file write is allowed. Returns True if allowed."""
        self._file_writes = self._prune_old_entries(self._file_writes)

        # Check rate
        if len(self._file_writes) >= self.max_file_writes_per_minute:
            return False

        # Check total bytes
        if self._bytes_written + bytes_count > self.max_bytes_written_per_session:
            return False

        self._file_writes.append(datetime.now())
        self._bytes_written += bytes_count
        return True

    def check_shell_command(self) -> bool:
        """Check if a shell command is allowed. Returns True if allowed."""
        self._shell_commands = self._prune_old_entries(self._shell_commands)
        if len(self._shell_commands) >= self.max_shell_commands_per_minute:
            return False
        self._shell_commands.append(datetime.now())
        return True


@dataclass(frozen=True, slots=True)
class ToolAuditEntry:
    """Audit log entry for tool execution."""

    timestamp: datetime
    tool_name: str
    arguments: dict  # Sanitized (no content for write_file)
    success: bool
    execution_time_ms: int
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


@dataclass(slots=True)
class ToolPolicy:
    """Tool execution policy from lens or global config.

    Resolution order for allowed tools:
    1. If profile is set, use profile's tools
    2. Else if allowed_tools is set, use that
    3. Else use trust_level's default tools

    Then apply also_allow (additive) and also_deny (subtractive).
    """

    trust_level: ToolTrust = ToolTrust.WORKSPACE

    # Named profile (takes precedence over allowed_tools if set)
    profile: ToolProfile | None = None
    """Named tool profile. If set, determines base tools before also_allow/also_deny."""

    # Explicit tool allowlist (optional, defaults to all at trust_level)
    allowed_tools: frozenset[str] | None = None

    # Additive/subtractive modifiers (applied after base resolution)
    also_allow: frozenset[str] = frozenset()
    """Additional tools to allow. Can include group references like 'group:git'."""

    also_deny: frozenset[str] = frozenset()
    """Tools to deny even if in base set. Applied after also_allow."""

    # Additional blocked patterns (merged with defaults)
    blocked_paths: frozenset[str] = frozenset()

    # For SHELL trust level - command allowlist
    command_allowlist: frozenset[str] | None = None

    # Rate limits (override defaults)
    rate_limits: ToolRateLimits | None = None

    def get_allowed_tools(self) -> frozenset[str]:
        """Get the set of allowed tools based on policy.

        Resolution:
        1. profile → profile tools (expanded from groups)
        2. allowed_tools → explicit set (expanded from groups)
        3. trust_level → default tools for level

        Then: (base | also_allow) - also_deny
        """
        # Determine base set
        if self.profile is not None:
            base = get_profile_tools(self.profile)
        elif self.allowed_tools is not None:
            base = expand_tool_groups(self.allowed_tools)
        else:
            # Local import to break circular dependency with constants.py
            from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS
            base = TRUST_LEVEL_TOOLS.get(self.trust_level, frozenset())

        # Apply modifiers
        expanded_allow = expand_tool_groups(self.also_allow) if self.also_allow else frozenset()
        expanded_deny = expand_tool_groups(self.also_deny) if self.also_deny else frozenset()

        return (base | expanded_allow) - expanded_deny

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a specific tool is allowed."""
        allowed = self.get_allowed_tools()
        return tool_name in allowed

    def with_profile(self, profile: ToolProfile) -> ToolPolicy:
        """Return a new policy with a different profile."""
        return ToolPolicy(
            trust_level=self.trust_level,
            profile=profile,
            allowed_tools=self.allowed_tools,
            also_allow=self.also_allow,
            also_deny=self.also_deny,
            blocked_paths=self.blocked_paths,
            command_allowlist=self.command_allowlist,
            rate_limits=self.rate_limits,
        )

    def with_also_allow(self, *tools: str) -> ToolPolicy:
        """Return a new policy with additional allowed tools."""
        return ToolPolicy(
            trust_level=self.trust_level,
            profile=self.profile,
            allowed_tools=self.allowed_tools,
            also_allow=self.also_allow | frozenset(tools),
            also_deny=self.also_deny,
            blocked_paths=self.blocked_paths,
            command_allowlist=self.command_allowlist,
            rate_limits=self.rate_limits,
        )

    def with_also_deny(self, *tools: str) -> ToolPolicy:
        """Return a new policy with additional denied tools."""
        return ToolPolicy(
            trust_level=self.trust_level,
            profile=self.profile,
            allowed_tools=self.allowed_tools,
            also_allow=self.also_allow,
            also_deny=self.also_deny | frozenset(tools),
            blocked_paths=self.blocked_paths,
            command_allowlist=self.command_allowlist,
            rate_limits=self.rate_limits,
        )
