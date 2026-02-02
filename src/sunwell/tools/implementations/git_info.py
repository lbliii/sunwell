"""Git info tool."""

import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="git_info",
    simple_description="Get git repository information",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance="Use git_info to get an overview of the repository including remotes, current branch, recent commits, and status.",
)
class GitInfoTool(BaseTool):
    """Get git repository information."""

    parameters = {
        "type": "object",
        "properties": {
            "include_status": {
                "type": "boolean",
                "description": "Include working tree status",
                "default": True,
            },
            "commit_count": {
                "type": "integer",
                "description": "Number of recent commits to show",
                "default": 5,
            },
        },
        "required": [],
    }

    def _run_git(self, cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
        """Run a git command."""
        return subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    async def execute(self, arguments: dict) -> str:
        include_status = arguments.get("include_status", True)
        commit_count = min(arguments.get("commit_count", 5), 20)

        git_dir = self.project.root / ".git"
        if not git_dir.exists():
            return "Not a git repository (no .git directory found)"

        info_parts = []

        try:
            result = self._run_git(["git", "remote", "-v"])
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Remotes:**\n{result.stdout.strip()}")
        except Exception:
            pass

        try:
            result = self._run_git(["git", "branch", "--show-current"])
            if result.returncode == 0:
                branch = result.stdout.strip() or "(detached HEAD)"
                info_parts.append(f"**Branch:** {branch}")
        except Exception:
            pass

        try:
            result = self._run_git(["git", "log", f"-{commit_count}", "--oneline"])
            if result.returncode == 0 and result.stdout.strip():
                info_parts.append(f"**Recent commits:**\n{result.stdout.strip()}")
        except Exception:
            pass

        if include_status:
            try:
                result = self._run_git(["git", "status", "--short"])
                if result.returncode == 0:
                    status = result.stdout.strip() or "(clean working tree)"
                    info_parts.append(f"**Status:**\n{status}")
            except Exception:
                pass

        return "\n\n".join(info_parts) if info_parts else "Could not retrieve git information"
