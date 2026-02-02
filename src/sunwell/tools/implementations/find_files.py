"""Find files tool implementation."""

import fnmatch

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.handlers.base import DEFAULT_BLOCKED_PATTERNS
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="find_files",
    simple_description="Find files by name pattern",
    trust_level=ToolTrust.DISCOVERY,
    usage_guidance=(
        "Finds files by glob pattern (name/path), unlike search_files which searches content. "
        "Use for discovering project structure. "
        "Examples: '**/*.py', 'src/**/*.ts'"
    ),
)
class FindFilesTool(BaseTool):
    """Find files matching a glob pattern.

    Unlike search_files which searches content, this finds files by name/path pattern.
    Useful for discovering project structure.
    """

    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., '**/*.py', 'src/**/*.ts')",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: workspace root)",
                "default": ".",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 100)",
                "default": 100,
            },
        },
        "required": ["pattern"],
    }

    def _is_blocked(self, relative_path: str) -> bool:
        """Check if path matches any blocked pattern."""
        for pattern in DEFAULT_BLOCKED_PATTERNS:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            simple_pattern = pattern.removeprefix("**/").removesuffix("/**")
            if simple_pattern and simple_pattern in relative_path:
                return True
        return False

    async def execute(self, arguments: dict) -> str:
        """Find files matching pattern.

        Args:
            arguments: Must contain 'pattern', optional 'path' and 'max_results'

        Returns:
            List of matching files

        Raises:
            ValueError: If path is not a directory
        """
        pattern = arguments["pattern"]
        search_path = self.resolve_path(arguments.get("path", "."))
        max_results = min(arguments.get("max_results", 100), 500)

        if not search_path.is_dir():
            raise ValueError(f"Not a directory: {arguments.get('path', '.')}")

        files = []
        for f in search_path.glob(pattern):
            if len(files) >= max_results:
                break
            try:
                relative = str(f.relative_to(self.project.root))
                if not self._is_blocked(relative):
                    files.append(relative)
            except ValueError:
                continue

        files.sort()

        if not files:
            return f"No files matching '{pattern}'"

        result = f"Found {len(files)} file(s) matching '{pattern}':\n"
        result += "\n".join(files)

        if len(files) == max_results:
            result += f"\n\n(results limited to {max_results})"

        return result
