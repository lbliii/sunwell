"""List files tool implementation."""

import fnmatch

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.handlers.base import DEFAULT_BLOCKED_PATTERNS
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="list_files",
    simple_description="List files in a directory",
    trust_level=ToolTrust.DISCOVERY,
    essential=True,
    usage_guidance=(
        "Use list_files to explore directory structure. "
        "Use the pattern parameter to filter by extension (e.g., '*.py'). "
        "Results are limited to 100 files."
    ),
)
class ListFilesTool(BaseTool):
    """List files in a directory. Returns file paths relative to workspace."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to workspace (default: current directory)",
                "default": ".",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (default: all files)",
                "default": "*",
            },
        },
    }

    def _is_blocked(self, relative_path: str) -> bool:
        """Check if path matches any blocked pattern.

        Args:
            relative_path: Path relative to workspace

        Returns:
            True if path should be blocked
        """
        for pattern in DEFAULT_BLOCKED_PATTERNS:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            # Check simple pattern without ** prefixes
            simple_pattern = pattern.removeprefix("**/").removesuffix("/**")
            if simple_pattern and simple_pattern in relative_path:
                return True
        return False

    async def execute(self, arguments: dict) -> str:
        """List files in directory.

        Args:
            arguments: Optional 'path' and 'pattern' keys

        Returns:
            Newline-separated list of file paths

        Raises:
            ValueError: If path is not a directory
        """
        path = self.resolve_path(arguments.get("path", "."))
        pattern = arguments.get("pattern", "*")

        if not path.is_dir():
            raise ValueError(f"Not a directory: {arguments.get('path', '.')}")

        files = []
        for f in sorted(path.glob(pattern)):
            try:
                relative = str(f.relative_to(self.project.root))
                if not self._is_blocked(relative):
                    files.append(relative)
            except ValueError:
                # Path outside workspace
                continue

        return "\n".join(files[:100]) or "(no matching files)"
