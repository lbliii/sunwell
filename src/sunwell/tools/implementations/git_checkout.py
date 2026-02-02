"""Git checkout tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_checkout",
    simple_description="Switch branches or create new branch",
    trust_level=ToolTrust.WORKSPACE,
    essential=False,
    usage_guidance="Use git_checkout to switch branches. Use create=true to create a new branch.",
)
class GitCheckoutTool(BaseTool):
    """Switch branches or create new branch."""

    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Branch name or commit to checkout",
            },
            "create": {
                "type": "boolean",
                "description": "Create new branch (-b)",
                "default": False,
            },
        },
        "required": ["target"],
    }

    def is_available(self) -> bool:
        """Only available in git repositories."""
        return (self.project.root / ".git").exists()

    async def execute(self, arguments: dict) -> str:
        if not (self.project.root / ".git").exists():
            raise ValueError("Not a git repository (no .git directory found)")

        target = arguments.get("target")
        if not target:
            raise ValueError("target is required for git_checkout")

        create = arguments.get("create", False)

        cmd = ["git", "checkout"]
        if create:
            cmd.append("-b")
        cmd.append(target)

        result = subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        output = result.stderr.strip() or result.stdout.strip()
        return f"✓ {output}" if output else f"✓ Switched to '{target}'"
