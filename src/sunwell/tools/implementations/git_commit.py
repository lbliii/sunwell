"""Git commit tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_commit",
    simple_description="Create a git commit",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_commit to commit staged changes. Stage files first with git_add.",
)
class GitCommitTool(BaseTool):
    """Create a commit."""

    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message",
            },
            "amend": {
                "type": "boolean",
                "description": "Amend the previous commit",
                "default": False,
            },
        },
        "required": ["message"],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        message = arguments.get("message")
        if not message:
            raise ValueError("message is required for git_commit")

        amend = arguments.get("amend", False)

        cmd = ["git", "commit", "-m", message]
        if amend:
            cmd.append("--amend")

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip()
