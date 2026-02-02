"""Write file tool implementation."""

import logging
import re

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

logger = logging.getLogger(__name__)

# Regex for detecting markdown code fences at start of content
_MARKDOWN_FENCE_RE = re.compile(r"^```\w*\n", re.MULTILINE)


@tool_metadata(
    name="write_file",
    simple_description="Write content to a file",
    trust_level=ToolTrust.WORKSPACE,
    essential=True,
    usage_guidance=(
        "write_file overwrites the entire file. For modifying existing files, "
        "prefer edit_file which makes surgical changes with less risk of data loss. "
        "Content must be raw text - do NOT include markdown fences (```)."
    ),
)
class WriteFileTool(BaseTool):
    """Write content to a file.

    Creates parent directories if needed. Overwrites existing files completely.
    Use edit_file for targeted changes.

    IMPORTANT: The content parameter must contain ONLY raw file content -
    do NOT wrap code in markdown fences (```) or include language tags.
    """

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace root",
            },
            "content": {
                "type": "string",
                "description": (
                    "The raw file content to write. Must be the exact text that should "
                    "appear in the file. Do NOT include markdown code fences (```), "
                    "language tags, or wrapper formatting. For example, a Python file "
                    "should start directly with imports or code, not ```python."
                ),
            },
        },
        "required": ["path", "content"],
    }

    def _sanitize_content(self, content: str, path: str) -> str:
        """Strip markdown fences if model accidentally included them.

        This is a defensive measure for when LLMs wrap code in markdown fences
        despite being instructed not to.

        Args:
            content: Raw content from tool call
            path: File path (for logging)

        Returns:
            Content with markdown fences stripped if present
        """
        if not content.startswith("```"):
            return content

        lines = content.split("\n")

        # Check for opening fence (```python, ```rust, etc.)
        if lines[0].startswith("```"):
            lines = lines[1:]

        # Check for closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        sanitized = "\n".join(lines)

        logger.warning(
            "Stripped markdown fences from write_file content",
            extra={
                "path": path,
                "original_len": len(content),
                "sanitized_len": len(sanitized),
            },
        )

        return sanitized

    async def execute(self, arguments: dict) -> str:
        """Write content to file.

        Args:
            arguments: Must contain 'path' and 'content' keys

        Returns:
            Success message with byte count

        Raises:
            ValueError: If path is invalid or is a directory
        """
        user_path = arguments["path"]
        content = arguments.get("content", "")

        if not user_path or user_path in (".", "..", "/"):
            raise ValueError(
                f"Invalid file path: '{user_path}'. Must specify a filename."
            )

        path = self.resolve_path(user_path)

        if path.exists() and path.is_dir():
            raise ValueError(
                f"Cannot write to '{user_path}': path is a directory, not a file. "
                f"Did you mean '{user_path}/filename.ext'?"
            )

        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)

        # Defensive sanitization
        content = self._sanitize_content(content, user_path)

        # Write file
        path.write_text(content, encoding="utf-8")

        return f"✓ Wrote {user_path} ({len(content):,} bytes)"
