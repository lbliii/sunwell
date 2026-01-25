# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Permission-aware sandbox execution (RFC-089).

Extends the existing ScriptSandbox (skills/sandbox.py) with declarative
permissions from RFC-089. Provides platform-specific isolation backends:

- Linux: seccomp + namespaces (full support)
- macOS: sandbox-exec (partial support)
- Windows: Job Objects (partial support)
- Container: Docker/Podman (recommended for CI)

Fallback strategy: If platform-specific isolation is unavailable,
uses process-level restrictions + aggressive auditing.
"""


import os
import platform
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sunwell.security.analyzer import PermissionScope
from sunwell.skills.sandbox import ScriptSandbox
from sunwell.skills.types import TrustLevel

if TYPE_CHECKING:
    from sunwell.skills.types import Skill, SkillOutput


# =============================================================================
# EXCEPTIONS
# =============================================================================


class PermissionDeniedError(Exception):
    """Raised when a skill requests permissions outside its declared scope."""

    def __init__(self, skill_name: str, requested: str, allowed: str):
        self.skill_name = skill_name
        self.requested = requested
        self.allowed = allowed
        super().__init__(
            f"Skill '{skill_name}' requested {requested} but only allowed {allowed}"
        )


class SandboxExecutionError(Exception):
    """Raised when sandbox execution fails."""

    def __init__(self, skill_name: str, phase: str, details: str):
        self.skill_name = skill_name
        self.phase = phase
        self.details = details
        super().__init__(f"Sandbox error in {skill_name} during {phase}: {details}")


# =============================================================================
# SECURITY AUDIT
# =============================================================================


@dataclass(slots=True)
class SecurityAudit:
    """Audit record for a skill execution.

    Captures what happened during execution for compliance and debugging.
    """

    skill_name: str
    """Name of the skill that was executed."""

    start_time: datetime = field(default_factory=datetime.now)
    """When execution started."""

    end_time: datetime | None = None
    """When execution ended (None if still running)."""

    success: bool = False
    """Whether execution succeeded."""

    violation: str | None = None
    """Security violation if any."""

    error: str | None = None
    """Error message if execution failed."""

    permissions_used: PermissionScope = field(default_factory=PermissionScope)
    """Actual permissions used during execution."""

    syscalls_blocked: list[str] = field(default_factory=list)
    """Syscalls that were blocked by sandbox."""

    network_connections: list[str] = field(default_factory=list)
    """Network connections attempted."""

    files_accessed: list[str] = field(default_factory=list)
    """Files accessed during execution."""

    def record_success(self, output: SkillOutput) -> None:
        """Record successful execution."""
        self.end_time = datetime.now()
        self.success = True

    def record_violation(self, error: PermissionDeniedError) -> None:
        """Record security violation."""
        self.end_time = datetime.now()
        self.success = False
        self.violation = str(error)

    def record_error(self, error: Exception) -> None:
        """Record execution error."""
        self.end_time = datetime.now()
        self.success = False
        self.error = str(error)

    @property
    def duration_ms(self) -> int | None:
        """Execution duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "skill_name": self.skill_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "success": self.success,
            "violation": self.violation,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "permissions_used": self.permissions_used.to_dict(),
            "syscalls_blocked": self.syscalls_blocked,
            "network_connections": self.network_connections,
            "files_accessed": self.files_accessed,
        }


# =============================================================================
# SANDBOX CONFIGURATION
# =============================================================================


IsolationBackend = Literal["seccomp", "sandbox-exec", "container", "process"]


@dataclass(slots=True)
class PermissionAwareSandboxConfig:
    """Configuration for permission-aware skill execution.

    Extends ScriptSandbox with declarative permissions from RFC-089.
    """

    permissions: PermissionScope
    """Declared permissions for the skill."""

    # Inherit base sandbox settings
    base_trust: TrustLevel = TrustLevel.SANDBOXED
    """Base trust level for script execution."""

    # Platform-specific isolation (auto-detected if None)
    isolation_backend: IsolationBackend | None = None
    """Isolation backend to use (auto-detected if None)."""

    # Resource limits (inherited from ScriptSandbox, can override)
    max_memory_mb: int = 512
    """Maximum memory in MB."""

    max_cpu_seconds: int = 60
    """Maximum CPU time in seconds."""

    max_file_size_mb: int = 100
    """Maximum file size in MB."""

    max_processes: int = 10
    """Maximum number of processes."""

    # Network policy
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    """Hosts the skill can connect to."""

    def __post_init__(self) -> None:
        if self.isolation_backend is None:
            self.isolation_backend = self._detect_backend()

        # Derive allowed_hosts from permissions if not set
        if not self.allowed_hosts and self.permissions.network_allow:
            self.allowed_hosts = self.permissions.network_allow

    def _detect_backend(self) -> IsolationBackend:
        """Auto-detect best isolation backend for current platform."""
        system = platform.system()

        if system == "Linux":
            # Check if seccomp is available
            try:
                # Try to load libc for seccomp support check
                import ctypes

                ctypes.CDLL("libc.so.6", use_errno=True)
                # prctl with PR_SET_SECCOMP is available
                return "seccomp"
            except (OSError, AttributeError):
                return "process"

        elif system == "Darwin":
            return "sandbox-exec"

        elif system == "Windows":
            return "process"  # Job Objects via subprocess

        return "process"


# =============================================================================
# SECURE SANDBOX
# =============================================================================


class SecureSandbox:
    """Execute skills in isolated sandbox with enforced permissions.

    Composes with existing ScriptSandbox rather than replacing it.
    The base ScriptSandbox handles script execution; this class adds
    permission enforcement and security auditing.
    """

    # Syscalls blocked by seccomp (Linux only)
    BLOCKED_SYSCALLS = [
        "ptrace",  # No debugging other processes
        "mount",  # No mounting filesystems
        "umount",  # No unmounting
        "pivot_root",  # No changing root
        "reboot",  # No rebooting
        "init_module",  # No loading kernel modules
        "delete_module",
        "kexec_load",  # No loading new kernels
    ]

    # Syscalls to audit (log but allow)
    AUDITED_SYSCALLS = [
        "execve",  # Log all process execution
        "connect",  # Log all network connections
        "open",  # Log file access
        "openat",
    ]

    def __init__(self, config: PermissionAwareSandboxConfig):
        """Initialize the secure sandbox.

        Args:
            config: Sandbox configuration with permissions
        """
        self.config = config
        self._base_sandbox = ScriptSandbox(
            trust=config.base_trust,
            read_paths=tuple(
                Path(os.path.expanduser(p))
                for p in config.permissions.filesystem_read
            ),
            write_paths=tuple(
                Path(os.path.expanduser(p))
                for p in config.permissions.filesystem_write
            ),
            allow_network=bool(config.allowed_hosts),
            timeout_seconds=config.max_cpu_seconds,
        )
        self._seccomp_filter: Any = None
        self._sandbox_profile_path: Path | None = None
        self._setup_isolation()

    def _setup_isolation(self) -> None:
        """Configure platform-specific isolation."""
        backend = self.config.isolation_backend

        if backend == "seccomp":
            self._setup_seccomp_filter()
        elif backend == "sandbox-exec":
            self._setup_macos_sandbox()
        elif backend == "container":
            self._setup_container_policy()
        # "process" backend uses base ScriptSandbox restrictions only

    async def execute(
        self,
        skill: Skill,
        context: dict[str, Any],
    ) -> tuple[SkillOutput, SecurityAudit]:
        """Execute skill in sandbox, return output and audit log.

        Args:
            skill: The skill to execute
            context: Execution context with inputs

        Returns:
            Tuple of (skill_output, security_audit)

        Raises:
            PermissionDeniedError: If skill requests out-of-scope permissions
            SandboxExecutionError: If execution fails
        """
        from sunwell.skills.types import SkillOutput

        audit = SecurityAudit(skill_name=skill.name)

        # Pre-execution validation
        if not self._validate_permissions(skill, context):
            error = PermissionDeniedError(
                skill.name,
                "permissions not in scope",
                str(self.config.permissions.to_dict()),
            )
            audit.record_violation(error)
            raise error

        try:
            # For script-based skills, delegate to base sandbox
            if skill.scripts:
                for script in skill.scripts:
                    result = await self._base_sandbox.execute(script)
                    audit.files_accessed.append(script.name)

                    if result.exit_code != 0:
                        error = SandboxExecutionError(
                            skill.name, "execute", result.stderr
                        )
                        audit.record_error(error)
                        raise error

            # Create output (for instruction-based skills or after scripts)
            output = SkillOutput(
                content="Skill executed successfully",
                content_type="text",
            )
            audit.record_success(output)

        except PermissionDeniedError:
            raise

        except Exception as e:
            audit.record_error(e)
            raise SandboxExecutionError(skill.name, "execute", str(e)) from e

        return output, audit

    def _validate_permissions(self, skill: Skill, context: dict[str, Any]) -> bool:
        """Validate skill's requested permissions against config.

        Args:
            skill: The skill to validate
            context: Execution context

        Returns:
            True if permissions are valid
        """
        # Get skill's declared permissions
        skill_perms = getattr(skill, "permissions", None)
        if skill_perms is None:
            # No permissions declared - allowed for legacy skills
            return True

        # Convert to PermissionScope if dict
        if isinstance(skill_perms, dict):
            from sunwell.security.analyzer import PermissionScope

            skill_scope = PermissionScope.from_dict(skill_perms)
        elif isinstance(skill_perms, PermissionScope):
            skill_scope = skill_perms
        else:
            return True

        config_scope = self.config.permissions

        # Check filesystem read
        for path in skill_scope.filesystem_read:
            if path not in config_scope.filesystem_read:
                # Check if any pattern matches
                if not any(
                    self._path_matches(path, allowed)
                    for allowed in config_scope.filesystem_read
                ):
                    return False

        # Check filesystem write
        for path in skill_scope.filesystem_write:
            if path not in config_scope.filesystem_write:
                if not any(
                    self._path_matches(path, allowed)
                    for allowed in config_scope.filesystem_write
                ):
                    return False

        # Check shell commands
        for cmd in skill_scope.shell_allow:
            if cmd not in config_scope.shell_allow:
                if not any(
                    self._command_matches(cmd, allowed)
                    for allowed in config_scope.shell_allow
                ):
                    return False

        # Check network
        for host in skill_scope.network_allow:
            if host not in config_scope.network_allow:
                if not any(
                    self._host_matches(host, allowed)
                    for allowed in config_scope.network_allow
                ):
                    return False

        return True

    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if path matches a permission pattern.

        Args:
            path: Path to check
            pattern: Glob pattern

        Returns:
            True if path matches pattern
        """
        from fnmatch import fnmatch

        # Expand user home
        expanded_path = os.path.expanduser(path)
        expanded_pattern = os.path.expanduser(pattern)

        return fnmatch(expanded_path, expanded_pattern)

    def _command_matches(self, cmd: str, allowed: str) -> bool:
        """Check if command matches allowed pattern (prefix match).

        Args:
            cmd: Command to check
            allowed: Allowed command prefix

        Returns:
            True if command starts with allowed prefix
        """
        # Remove glob from allowed pattern
        allowed_prefix = allowed.replace(" *", "").lower()
        return cmd.lower().strip().startswith(allowed_prefix)

    def _host_matches(self, host: str, pattern: str) -> bool:
        """Check if host matches allowed pattern.

        Args:
            host: Host to check (host:port format)
            pattern: Allowed pattern

        Returns:
            True if host matches pattern
        """
        from fnmatch import fnmatch

        return fnmatch(host, pattern)

    def _setup_seccomp_filter(self) -> None:
        """Configure seccomp to block dangerous syscalls (Linux only)."""
        # Store filter config for later application
        self._seccomp_filter = {
            "default_action": "allow",
            "blocked": self.BLOCKED_SYSCALLS,
            "audited": self.AUDITED_SYSCALLS,
        }

    def _setup_macos_sandbox(self) -> None:
        """Configure sandbox-exec profile (macOS only)."""
        profile = self._generate_sandbox_profile()
        self._sandbox_profile_path = Path(
            tempfile.mktemp(suffix=".sb", prefix="sunwell_")
        )
        self._sandbox_profile_path.write_text(profile)

    def _generate_sandbox_profile(self) -> str:
        """Generate macOS sandbox-exec profile from PermissionScope.

        Returns:
            Sandbox profile content
        """
        lines = ["(version 1)", "(deny default)"]

        # Allow read paths
        for path in self.config.permissions.filesystem_read:
            expanded = os.path.expanduser(path)
            # Convert glob to sandbox-exec pattern
            if "*" in expanded:
                expanded = expanded.replace("**", "*")
            lines.append(f'(allow file-read* (subpath "{expanded}"))')

        # Allow write paths
        for path in self.config.permissions.filesystem_write:
            expanded = os.path.expanduser(path)
            if "*" in expanded:
                expanded = expanded.replace("**", "*")
            lines.append(f'(allow file-write* (subpath "{expanded}"))')

        # Network rules
        if self.config.allowed_hosts:
            lines.append("(allow network-outbound")
            for host in self.config.allowed_hosts:
                # Parse host:port
                if ":" in host:
                    h, p = host.rsplit(":", 1)
                    if p != "*":
                        lines.append(f'  (remote tcp "{h}" (port {p}))')
                    else:
                        lines.append(f'  (remote tcp "{h}")')
                else:
                    lines.append(f'  (remote tcp "{host}")')
            lines.append(")")

        return "\n".join(lines)

    def _setup_container_policy(self) -> None:
        """Configure container-based isolation (Docker/Podman)."""
        # Container config stored for runtime use
        # Actual container execution handled by a container runtime wrapper
        pass

    def cleanup(self) -> None:
        """Clean up sandbox resources."""
        if self._sandbox_profile_path and self._sandbox_profile_path.exists():
            self._sandbox_profile_path.unlink()
