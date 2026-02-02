"""Git init tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_init",
    simple_description="Initialize a new git repository",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_init to create a new git repository. Defaults to current workspace root.",
)
class GitInitTool(BaseTool):
    """Initialize a new git repository."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to initialize (defaults to workspace root)",
                "default": ".",
            },
        },
        "required": [],
    }

    async def execute(self, arguments: dict) -> str:
        path = arguments.get("path", ".")
        target = self.resolve_path(path)

        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.is_dir():
            raise ValueError(f"Path exists but is not a directory: {path}")

        if (target / ".git").exists():
            return f"Already a git repository: {path}"

        result = subprocess.run(
            ["git", "init"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip() or f"Initialized git repository in {path}"
