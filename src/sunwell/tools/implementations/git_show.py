"""Git show tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_show",
    simple_description="Show commit details",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use git_show to see details of a specific commit. Defaults to HEAD.",
)
class GitShowTool(BaseTool):
    """Show commit details."""

    parameters = {
        "type": "object",
        "properties": {
            "commit": {
                "type": "string",
                "description": "Commit to show (defaults to HEAD)",
                "default": "HEAD",
            },
            "path": {
                "type": "string",
                "description": "Limit to specific file path",
            },
        },
        "required": [],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        commit = arguments.get("commit", "HEAD")

        cmd = ["git", "show", commit, "--stat"]

        if path := arguments.get("path"):
            self.resolve_path(path)  # Validate path is within workspace
            cmd.extend(["--", path])

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        output = result.stdout.strip()
        if len(output) > 30000:
            output = output[:30000] + "\n... (truncated)"

        return output
