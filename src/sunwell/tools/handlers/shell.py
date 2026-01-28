"""Shell operation handlers."""


import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.tools.handlers.base import BaseHandler

if TYPE_CHECKING:
    from sunwell.planning.skills.sandbox import ScriptSandbox

logger = logging.getLogger(__name__)

# Environment variable to disable sandbox (escape hatch for power users)
SANDBOX_DISABLED_ENV = "SUNWELL_UNSAFE_SHELL"


def _is_sandbox_disabled() -> bool:
    """Check if sandbox is explicitly disabled via environment variable."""
    return os.environ.get(SANDBOX_DISABLED_ENV, "").lower() in ("1", "true", "yes")


def _create_default_sandbox(workspace: Path) -> ScriptSandbox | None:
    """Create a default sandbox for shell command execution.

    Returns None if sandbox creation fails (logs warning) or if sandbox
    is explicitly disabled via SUNWELL_UNSAFE_SHELL=1.
    """
    if _is_sandbox_disabled():
        logger.warning(
            "Shell sandbox disabled via %s environment variable. "
            "Commands will run unsandboxed.",
            SANDBOX_DISABLED_ENV,
        )
        return None

    try:
        from sunwell.planning.skills.sandbox import ScriptSandbox

        return ScriptSandbox(
            timeout_seconds=300,  # 5 minute max
            allow_network=False,
            read_paths=(workspace,),  # Allow reading from workspace
            write_paths=(workspace,),  # Allow writing to workspace
        )
    except ImportError:
        logger.warning(
            "ScriptSandbox not available. Shell commands will run unsandboxed. "
            "Install sandbox dependencies for safer execution."
        )
        return None
    except Exception as e:
        logger.warning(
            "Failed to create sandbox: %s. Shell commands will run unsandboxed.",
            e,
        )
        return None


class ShellHandlers(BaseHandler):
    """Shell operation handlers.

    By default, creates a sandbox for shell command execution to limit
    potential damage from malicious or buggy commands. The sandbox restricts:
    - Network access
    - Writing outside the workspace
    - Execution time (5 minute timeout)

    To disable the sandbox (not recommended), set SUNWELL_UNSAFE_SHELL=1
    """

    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(workspace, **kwargs)

        # Create default sandbox if none provided (unless disabled)
        if sandbox is None:
            self.sandbox = _create_default_sandbox(workspace)
            self._sandbox_is_default = True
        else:
            self.sandbox = sandbox
            self._sandbox_is_default = False

    async def run_command(self, args: dict) -> str:
        """Run shell command in sandbox.

        If sandbox is available, commands run in a restricted environment.
        Otherwise, commands run directly via subprocess (less safe).
        """
        cwd = self._safe_path(args.get("cwd", "."))
        command = args["command"]
        timeout = min(args.get("timeout", 30), 300)

        if self.sandbox:
            from sunwell.planning.skills.types import Script

            script = Script(
                name="cmd.sh",
                content=f"#!/bin/bash\n{command}",
                language="bash",
            )

            result = await self.sandbox.execute(script)

            output_parts = [f"Exit code: {result.exit_code}"]
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout[:5000]}")
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr[:2000]}")
            if result.timed_out:
                output_parts.append("(command timed out)")

            return "\n".join(output_parts)

        # Fallback to direct subprocess (unsandboxed)
        logger.debug("Running command without sandbox: %s", command[:100])
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output_parts = [f"Exit code: {result.returncode}"]
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout[:5000]}")
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr[:2000]}")

            return "\n".join(output_parts)

        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Command failed: {e}"

    async def mkdir(self, args: dict) -> str:
        """Create a directory (and parent directories if needed)."""
        path = self._safe_path(args["path"])

        if path.exists():
            if path.is_dir():
                return f"Directory already exists: {args['path']}"
            else:
                raise ValueError(f"Path exists but is not a directory: {args['path']}")

        path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {args['path']}"
