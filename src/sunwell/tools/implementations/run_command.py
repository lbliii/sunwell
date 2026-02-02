"""Run command tool implementation."""

import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

if TYPE_CHECKING:
    from sunwell.planning.skills.sandbox import ScriptSandbox

logger = logging.getLogger(__name__)

# Environment variable to disable sandbox
SANDBOX_DISABLED_ENV = "SUNWELL_UNSAFE_SHELL"


@tool_metadata(
    name="run_command",
    simple_description="Run shell command in sandbox",
    trust_level=ToolTrust.SHELL,
    usage_guidance=(
        "Use run_command for build commands, tests, or inspection. "
        "Commands are sandboxed by default. "
        "Set cwd to change working directory. "
        "Default timeout is 30s, max is 300s."
    ),
)
class RunCommandTool(BaseTool):
    """Run a shell command in a sandboxed environment.

    Use for build commands, tests, or inspection.
    Commands that modify the filesystem may be restricted based on trust level.
    """

    parameters = {
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
    }

    def _create_sandbox(self) -> ScriptSandbox | None:
        """Create a sandbox for command execution."""
        if os.environ.get(SANDBOX_DISABLED_ENV, "").lower() in ("1", "true", "yes"):
            logger.warning(
                "Shell sandbox disabled via %s environment variable",
                SANDBOX_DISABLED_ENV,
            )
            return None

        try:
            from sunwell.planning.skills.sandbox import ScriptSandbox

            return ScriptSandbox(
                timeout_seconds=300,
                allow_network=False,
                read_paths=(self.project.root,),
                write_paths=(self.project.root,),
            )
        except ImportError:
            logger.warning("ScriptSandbox not available, running unsandboxed")
            return None
        except Exception as e:
            logger.warning("Failed to create sandbox: %s", e)
            return None

    async def execute(self, arguments: dict) -> str:
        """Execute shell command.

        Args:
            arguments: Must contain 'command', optional 'cwd' and 'timeout'

        Returns:
            Command output with exit code
        """
        command = arguments["command"]
        cwd_arg = arguments.get("cwd", ".")
        timeout = min(arguments.get("timeout", 30), 300)

        cwd = self.resolve_path(cwd_arg)

        sandbox = self._create_sandbox()

        if sandbox:
            from sunwell.planning.skills.types import Script

            script = Script(
                name="cmd.sh",
                content=f"#!/bin/bash\n{command}",
                language="bash",
            )

            result = await sandbox.execute(script)

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
