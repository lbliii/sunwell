"""Git add tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_add",
    simple_description="Stage files for commit",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_add to stage files before committing. Use all=true to stage all changes.",
)
class GitAddTool(BaseTool):
    """Stage files for commit."""

    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage",
            },
            "all": {
                "type": "boolean",
                "description": "Stage all changes (-A)",
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

        paths = arguments.get("paths", [])
        add_all = arguments.get("all", False)

        if add_all:
            cmd = ["git", "add", "-A"]
        elif paths:
            for p in paths:
                self.resolve_path(p)  # Validate paths are within workspace
            cmd = ["git", "add", "--"] + paths
        else:
            return "No files specified. Use 'paths' or 'all: true'"

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        status_result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        return f"✓ Files staged\n{status_result.stdout.strip()}"
