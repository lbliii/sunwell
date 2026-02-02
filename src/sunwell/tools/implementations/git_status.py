"""Git status tool implementation."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_status",
    simple_description="Show working tree status",
    trust_level=ToolTrust.READ_ONLY,
    usage_guidance=(
        "Shows modified, staged, and untracked files. "
        "Use --short for compact output. "
        "Only works in git repositories."
    ),
)
class GitStatusTool(BaseTool):
    """Show working tree status: modified, staged, untracked files."""

    parameters = {
        "type": "object",
        "properties": {
            "short": {
                "type": "boolean",
                "description": "Use short format output",
                "default": False,
            },
        },
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        """Get git status.

        Args:
            arguments: Optional 'short' boolean

        Returns:
            Git status output

        Raises:
            ValueError: If not a git repository
        """
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        short = arguments.get("short", False)

        cmd = ["git", "status"]
        if short:
            cmd.append("--short")

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip() or "Working tree clean"
