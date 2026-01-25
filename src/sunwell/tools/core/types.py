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
    """Tool execution policy from lens or global config."""

    trust_level: ToolTrust = ToolTrust.WORKSPACE

    # Explicit tool allowlist (optional, defaults to all at trust_level)
    allowed_tools: frozenset[str] | None = None

    # Additional blocked patterns (merged with defaults)
    blocked_paths: frozenset[str] = frozenset()

    # For SHELL trust level - command allowlist
    command_allowlist: frozenset[str] | None = None

    # Rate limits (override defaults)
    rate_limits: ToolRateLimits | None = None

    def get_allowed_tools(self) -> frozenset[str]:
        """Get the set of allowed tools based on policy."""
        if self.allowed_tools is not None:
            return self.allowed_tools
        # Local import to break circular dependency with constants.py
        from sunwell.tools.core.constants import TRUST_LEVEL_TOOLS

        return TRUST_LEVEL_TOOLS.get(self.trust_level, frozenset())

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a specific tool is allowed."""
        allowed = self.get_allowed_tools()
        return tool_name in allowed
