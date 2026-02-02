"""Search files tool implementation."""

import shutil
import subprocess

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="search_files",
    simple_description="Search for text patterns in files",
    trust_level=ToolTrust.DISCOVERY,
    essential=True,
    usage_guidance=(
        "Use search_files to find code by content. "
        "Supports regex patterns. "
        "Use the glob parameter to filter file types (e.g., '**/*.py')."
    ),
)
class SearchFilesTool(BaseTool):
    """Search for a text pattern in files using ripgrep.

    Falls back to grep if ripgrep is not available.
    Returns matching lines with file:line references.
    """

    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)",
                "default": ".",
            },
            "glob": {
                "type": "string",
                "description": "File glob pattern to filter which files to search (default: all files)",
                "default": "**/*",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, arguments: dict) -> str:
        """Search for pattern in files.

        Args:
            arguments: Must contain 'pattern', optional 'path' and 'glob'

        Returns:
            Search results with file:line:content format
        """
        search_path = self.resolve_path(arguments.get("path", "."))
        pattern = arguments["pattern"]
        glob_pattern = arguments.get("glob", "**/*")

        # Try ripgrep first, fall back to grep
        rg_path = shutil.which("rg")
        if rg_path:
            cmd = [
                rg_path,
                "-n",  # Line numbers
                "--max-filesize",
                "1M",  # Skip large files
                "--glob",
                glob_pattern,
                pattern,
                ".",
            ]
        else:
            cmd = ["grep", "-rn", pattern, "."]

        try:
            result = subprocess.run(
                cmd,
                cwd=search_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout[:10_000]  # Limit output size

            if result.returncode == 0:
                lines = output.strip().split("\n")
                if output:
                    return f"Found {len(lines)} matches:\n{output}"
                return "No matches found"
            elif result.returncode == 1:
                return "No matches found"
            else:
                return f"Search error: {result.stderr[:500]}"

        except subprocess.TimeoutExpired:
            return "Search timed out after 30s"
        except FileNotFoundError:
            return "Search tools (rg, grep) not available"
