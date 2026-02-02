"""Git log tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_log",
    simple_description="Show git commit log",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use git_log to see commit history. Use oneline=true for compact output, or path to filter by file.",
)
class GitLogTool(BaseTool):
    """Show git log."""

    parameters = {
        "type": "object",
        "properties": {
            "n": {
                "type": "integer",
                "description": "Number of commits to show",
                "default": 10,
            },
            "oneline": {
                "type": "boolean",
                "description": "Compact one-line format",
                "default": True,
            },
            "since": {
                "type": "string",
                "description": "Show commits since date (e.g., '2 weeks ago')",
            },
            "path": {
                "type": "string",
                "description": "Filter by file/directory path",
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

        n = min(arguments.get("n", 10), 100)
        oneline = arguments.get("oneline", True)

        cmd = ["git", "log", f"-{n}"]

        if oneline:
            cmd.append("--oneline")

        if since := arguments.get("since"):
            cmd.extend(["--since", since])

        if path := arguments.get("path"):
            self.resolve_path(path)  # Validate path is within workspace
            cmd.extend(["--", path])

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        return result.stdout.strip() or "No commits found"
