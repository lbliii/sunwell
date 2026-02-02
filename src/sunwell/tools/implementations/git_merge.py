"""Git merge tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_merge",
    simple_description="Merge branch into current",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_merge to merge a branch into the current branch. Handle conflicts manually if they occur.",
)
class GitMergeTool(BaseTool):
    """Merge branch."""

    parameters = {
        "type": "object",
        "properties": {
            "branch": {
                "type": "string",
                "description": "Branch to merge",
            },
            "no_ff": {
                "type": "boolean",
                "description": "Create merge commit even for fast-forward",
                "default": False,
            },
            "message": {
                "type": "string",
                "description": "Merge commit message",
            },
        },
        "required": ["branch"],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        branch = arguments.get("branch")
        if not branch:
            raise ValueError("branch is required for git_merge")

        no_ff = arguments.get("no_ff", False)
        message = arguments.get("message")

        cmd = ["git", "merge", branch]
        if no_ff:
            cmd.append("--no-ff")
        if message:
            cmd.extend(["-m", message])

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                return f"Merge conflicts:\n{result.stdout}\n\nResolve conflicts and commit."
            return f"Error: {result.stderr}"

        return result.stdout.strip() or f"✓ Merged '{branch}'"
