"""Shell operation handlers."""


import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.tools.handlers.base import BaseHandler

if TYPE_CHECKING:
    from sunwell.planning.skills.sandbox import ScriptSandbox


class ShellHandlers(BaseHandler):
    """Shell operation handlers."""

    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(workspace, **kwargs)
        self.sandbox = sandbox

    async def run_command(self, args: dict) -> str:
        """Run shell command in sandbox."""
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
