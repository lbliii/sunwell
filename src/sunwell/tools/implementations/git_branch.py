"""Git branch tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_branch",
    simple_description="List, create, or delete branches",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_branch to manage branches. Without name, lists branches. With name, creates. With delete=true, deletes.",
)
class GitBranchTool(BaseTool):
    """List, create, or delete branches."""

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Branch name (omit to list branches)",
            },
            "delete": {
                "type": "boolean",
                "description": "Delete the branch",
                "default": False,
            },
            "force": {
                "type": "boolean",
                "description": "Force delete (-D instead of -d)",
                "default": False,
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

        name = arguments.get("name")
        delete = arguments.get("delete", False)
        force = arguments.get("force", False)

        if not name:
            result = subprocess.run(
                ["git", "branch", "-vv"],
                cwd=self.project.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            return result.stdout.strip() or "No branches"

        if delete:
            flag = "-D" if force else "-d"
            cmd = ["git", "branch", flag, name]
        else:
            cmd = ["git", "branch", name]

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        if delete:
            return f"✓ Branch '{name}' deleted"
        return f"✓ Branch '{name}' created"
