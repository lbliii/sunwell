"""Git diff tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_diff",
    simple_description="Show git diff",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use git_diff to see changes. Use staged=true for staged changes, or specify a commit to compare against.",
)
class GitDiffTool(BaseTool):
    """Show git diff."""

    parameters = {
        "type": "object",
        "properties": {
            "staged": {
                "type": "boolean",
                "description": "Show staged changes (--cached)",
                "default": False,
            },
            "commit": {
                "type": "string",
                "description": "Compare against specific commit",
            },
            "path": {
                "type": "string",
                "description": "Limit diff to specific file/directory",
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

        cmd = ["git", "diff"]

        if arguments.get("staged"):
            cmd.append("--cached")

        if commit := arguments.get("commit"):
            cmd.append(commit)

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
        if not output:
            return "No changes" if arguments.get("staged") else "No unstaged changes"

        if len(output) > 50000:
            output = output[:50000] + "\n... (truncated, diff too large)"

        return output
