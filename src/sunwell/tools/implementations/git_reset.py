"""Git reset tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_reset",
    simple_description="Reset HEAD to specified state",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_reset to unstage files (with paths) or reset HEAD (with mode). Mode: soft, mixed, hard.",
)
class GitResetTool(BaseTool):
    """Reset HEAD to specified state."""

    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Commit to reset to",
                "default": "HEAD",
            },
            "mode": {
                "type": "string",
                "enum": ["soft", "mixed", "hard"],
                "description": "Reset mode",
                "default": "mixed",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paths to unstage (overrides target/mode)",
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

        target = arguments.get("target", "HEAD")
        mode = arguments.get("mode", "mixed")
        paths = arguments.get("paths")

        if paths:
            for p in paths:
                self.resolve_path(p)  # Validate paths are within workspace
            cmd = ["git", "reset", "HEAD", "--"] + paths
        else:
            cmd = ["git", "reset", f"--{mode}", target]

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        if paths:
            return f"✓ Unstaged {len(paths)} file(s)"
        return f"✓ Reset to {target} ({mode})"
