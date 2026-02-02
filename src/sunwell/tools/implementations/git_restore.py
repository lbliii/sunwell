"""Git restore tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_restore",
    simple_description="Restore files or unstage",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_restore to discard changes or unstage files. Use staged=true to unstage.",
)
class GitRestoreTool(BaseTool):
    """Restore files or unstage."""

    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to restore",
            },
            "staged": {
                "type": "boolean",
                "description": "Unstage files (--staged)",
                "default": False,
            },
            "source": {
                "type": "string",
                "description": "Restore from specific commit",
            },
        },
        "required": ["paths"],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        paths = arguments.get("paths")
        if not paths:
            raise ValueError("paths is required for git_restore")

        staged = arguments.get("staged", False)
        source = arguments.get("source")

        for p in paths:
            self.resolve_path(p)  # Validate paths are within workspace

        cmd = ["git", "restore"]

        if staged:
            cmd.append("--staged")

        if source:
            cmd.extend(["--source", source])

        cmd.extend(["--"] + paths)

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        action = "unstaged" if staged else "restored"
        return f"✓ {len(paths)} file(s) {action}"
