"""Git blame tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_blame",
    simple_description="Show git blame for a file",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use git_blame to see who last modified each line. Use lines='10,20' to limit range.",
)
class GitBlameTool(BaseTool):
    """Show git blame for a file."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to blame",
            },
            "lines": {
                "type": "string",
                "description": "Line range (e.g., '10,20' for lines 10-20)",
            },
        },
        "required": ["path"],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        path = arguments.get("path")
        if not path:
            raise ValueError("path is required for git_blame")

        self.resolve_path(path)  # Validate path is within workspace

        cmd = ["git", "blame", path]

        if lines := arguments.get("lines"):
            cmd.extend(["-L", lines])

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
