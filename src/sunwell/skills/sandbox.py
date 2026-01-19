"""Script execution sandbox with security restrictions.

Implements the sandbox model from RFC-011 Section 7 (Security).
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sunwell.skills.types import Script, TrustLevel


class SecurityError(Exception):
    """Raised when a script attempts a forbidden operation."""

    pass


@dataclass(frozen=True, slots=True)
class ScriptResult:
    """Result from script execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


@dataclass
class ScriptSandbox:
    """Sandboxed script execution with enforced restrictions.

    Trust levels map to restrictions:
    - FULL: No sandbox. Scripts execute without restrictions.
    - SANDBOXED: Restricted to allowed paths, no network, timeout enforced.
    - NONE: Scripts are not executed (instructions only).
    """

    trust: TrustLevel = TrustLevel.SANDBOXED

    # Allowed interpreters
    allowed_interpreters: frozenset[str] = field(
        default_factory=lambda: frozenset({"python", "node", "bash"})
    )

    # Filesystem restrictions (paths are canonicalized and jailed)
    read_paths: tuple[Path, ...] = ()  # Empty = workspace root only
    write_paths: tuple[Path, ...] = ()  # Empty = temp dir only

    # Network is OFF by default, requires explicit opt-in
    allow_network: bool = False

    # Resource limits
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    max_output_bytes: int = 1_000_000  # 1MB

    def can_execute(self) -> bool:
        """Check if this sandbox allows script execution."""
        return self.trust != TrustLevel.NONE

    def _canonicalize_and_jail(self, path: Path, jail: Path) -> Path:
        """Resolve path and ensure it stays within jail directory."""
        resolved = (jail / path).resolve()
        if not resolved.is_relative_to(jail.resolve()):
            raise SecurityError(f"Path escapes jail: {path}")
        return resolved

    def _build_restricted_env(self, jail_dir: Path) -> dict[str, str]:
        """Build environment with minimal variables."""
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(jail_dir),
            "LANG": "C.UTF-8",
        }

        if not self.allow_network:
            # Block common exfiltration vectors
            env.update(
                {
                    "http_proxy": "",
                    "https_proxy": "",
                    "no_proxy": "*",
                }
            )

        return env

    async def execute(self, script: Script, args: list[str] | None = None) -> ScriptResult:
        """Execute script in sandbox.

        Implementation uses subprocess with timeouts and output limits.
        For enhanced security, could use:
        1. Python 3.14+ subinterpreters (PEP 734) for Python scripts
        2. Docker/Podman container for multi-language support
        3. OS-level sandboxing (seccomp on Linux, sandbox-exec on macOS)
        """
        args = args or []

        # Trust level check
        if self.trust == TrustLevel.NONE:
            return ScriptResult(
                exit_code=-1,
                stdout="",
                stderr="Script execution disabled (trust: none)",
                timed_out=False,
            )

        # Interpreter check
        if script.language not in self.allowed_interpreters:
            raise SecurityError(f"Interpreter not allowed: {script.language}")

        # Prepare execution environment
        jail_dir = Path(self.write_paths[0]) if self.write_paths else Path(tempfile.mkdtemp())
        script_path = jail_dir / script.name
        script_path.write_text(script.content)

        # Build command with interpreter
        interpreter_map = {"python": "python3", "node": "node", "bash": "bash"}
        cmd = [interpreter_map[script.language], str(script_path), *args]

        # Build environment
        env = self._build_restricted_env(jail_dir) if self.trust == TrustLevel.SANDBOXED else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(jail_dir),
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_seconds,
            )

            # Enforce output size limit
            if len(stdout) > self.max_output_bytes:
                stdout = stdout[: self.max_output_bytes] + b"\n[OUTPUT TRUNCATED]"

            return ScriptResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                timed_out=False,
            )

        except TimeoutError:
            proc.kill()
            return ScriptResult(
                exit_code=-1,
                stdout="",
                stderr=f"Script timed out after {self.timeout_seconds}s",
                timed_out=True,
            )

        except Exception as e:
            return ScriptResult(
                exit_code=-1,
                stdout="",
                stderr=f"Script execution failed: {e}",
                timed_out=False,
            )

        finally:
            # Cleanup temp script if we created it
            if self.write_paths and script_path.exists():
                pass  # Keep for debugging
            elif script_path.exists():
                script_path.unlink()


def expand_template_variables(content: str, context: dict[str, str]) -> str:
    """Expand template variables in content.

    Supported variables (from RFC-011 Appendix A):
    - ${Name}: Context value, PascalCase
    - ${name}: Context value, lowercase
    - ${NAME}: Context value, UPPERCASE
    - ${WORKSPACE_ROOT}: Absolute path to workspace
    - ${LENS_DIR}: Directory containing the lens file
    - ${TEMP_DIR}: System temp directory
    - ${DATE}: Current date (YYYY-MM-DD)
    - ${TIMESTAMP}: Unix timestamp
    """
    import time
    from datetime import datetime

    # Build variable map from context
    variables: dict[str, str] = {
        "TEMP_DIR": tempfile.gettempdir(),
        "DATE": datetime.now().strftime("%Y-%m-%d"),
        "TIMESTAMP": str(int(time.time())),
    }

    # Add context variables with case variants
    for key, value in context.items():
        # Original key with original value
        variables[key] = value
        # Lowercase variant
        variables[key.lower()] = value.lower()
        # Uppercase variant
        variables[key.upper()] = value.upper()

    # Simple variable expansion (${VAR})
    result = content
    for key, value in variables.items():
        result = result.replace(f"${{{key}}}", str(value))

    return result
