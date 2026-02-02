"""Git stash tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_stash",
    simple_description="Stash operations (push, pop, apply, drop, list)",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_stash to temporarily store changes. Actions: push, pop, apply, drop, list.",
)
class GitStashTool(BaseTool):
    """Stash operations."""

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["push", "pop", "apply", "drop", "list"],
                "description": "Stash action to perform",
                "default": "push",
            },
            "message": {
                "type": "string",
                "description": "Message for push action",
            },
            "index": {
                "type": "integer",
                "description": "Stash index for pop/apply/drop",
                "default": 0,
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

        action = arguments.get("action", "push")
        message = arguments.get("message")
        index = arguments.get("index", 0)

        if action == "push":
            cmd = ["git", "stash", "push"]
            if message:
                cmd.extend(["-m", message])
        elif action == "pop":
            cmd = ["git", "stash", "pop", f"stash@{{{index}}}"]
        elif action == "apply":
            cmd = ["git", "stash", "apply", f"stash@{{{index}}}"]
        elif action == "drop":
            cmd = ["git", "stash", "drop", f"stash@{{{index}}}"]
        elif action == "list":
            cmd = ["git", "stash", "list"]
        else:
            return f"Unknown stash action: {action}"

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        output = result.stdout.strip() or result.stderr.strip()
        if action == "list" and not output:
            return "No stashes"
        return output or f"✓ Stash {action} completed"
