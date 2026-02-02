"""Edit file tool implementation."""

import logging
import re

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata

logger = logging.getLogger(__name__)


@tool_metadata(
    name="edit_file",
    simple_description="Make surgical edits to a file",
    trust_level=ToolTrust.WORKSPACE,
    essential=True,
    usage_guidance=(
        "Prefer edit_file over write_file for existing files. "
        "Include 3-5 lines of context around the change to uniquely identify the location. "
        "old_content must match exactly including whitespace. "
        "Creates a backup before editing."
    ),
)
class EditFileTool(BaseTool):
    """Make targeted edits to a file by replacing specific content.

    MUCH safer than write_file for modifying existing files.
    Requires unique context (3-5 lines) to identify the edit location.
    Creates a backup before editing.
    """

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace root",
            },
            "old_content": {
                "type": "string",
                "description": (
                    "The exact content to find and replace. "
                    "Include enough surrounding context (3-5 lines) to uniquely identify the location. "
                    "Must match exactly, including whitespace and indentation."
                ),
            },
            "new_content": {
                "type": "string",
                "description": (
                    "The content to replace old_content with. Must be raw code/text - "
                    "do NOT wrap in markdown fences (```) or include language tags."
                ),
            },
            "occurrence": {
                "type": "integer",
                "description": "Which occurrence to replace: 1=first (default), -1=last, 0=all",
                "default": 1,
            },
        },
        "required": ["path", "old_content", "new_content"],
    }

    def _sanitize_content(self, content: str, path: str) -> str:
        """Strip markdown fences if model accidentally included them."""
        if not content.startswith("```"):
            return content

        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        sanitized = "\n".join(lines)
        logger.warning(
            "Stripped markdown fences from edit_file new_content",
            extra={"path": path},
        )
        return sanitized

    async def execute(self, arguments: dict) -> str:
        """Make targeted edit to file.

        Args:
            arguments: Must contain 'path', 'old_content', 'new_content'

        Returns:
            Success message with edit details

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If old_content not found or not unique
        """
        user_path = arguments["path"]
        old_content_arg = arguments["old_content"]
        new_content_arg = arguments["new_content"]
        occurrence = arguments.get("occurrence", 1)

        # Sanitize new content
        new_content_arg = self._sanitize_content(new_content_arg, user_path)

        path = self.resolve_path(user_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {user_path}. Use write_file to create new files."
            )
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}")

        content = path.read_text(encoding="utf-8")
        count = content.count(old_content_arg)

        if count == 0:
            preview = (
                old_content_arg[:100] + "..."
                if len(old_content_arg) > 100
                else old_content_arg
            )
            raise ValueError(
                f"Content not found in {user_path}.\n"
                f"Looking for:\n{preview}\n\n"
                f"Make sure the content matches exactly, including whitespace and indentation."
            )

        # Create backup
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")

        # Perform replacement
        if occurrence == 0:
            new_file_content = content.replace(old_content_arg, new_content_arg)
            replaced_count = count
            first_idx = content.find(old_content_arg)
            lines_before = content[:first_idx].count("\n") + 1
        elif occurrence == -1:
            idx = content.rfind(old_content_arg)
            new_file_content = (
                content[:idx] + new_content_arg + content[idx + len(old_content_arg) :]
            )
            replaced_count = 1
            lines_before = content[:idx].count("\n") + 1
        else:
            if occurrence > count:
                raise ValueError(
                    f"Requested occurrence {occurrence} but only {count} found in {user_path}"
                )
            idx = -1
            for _ in range(occurrence):
                idx = content.find(old_content_arg, idx + 1)
            new_file_content = (
                content[:idx] + new_content_arg + content[idx + len(old_content_arg) :]
            )
            replaced_count = 1
            lines_before = content[:idx].count("\n") + 1

        path.write_text(new_file_content, encoding="utf-8")

        old_lines = old_content_arg.count("\n") + 1
        new_lines = new_content_arg.count("\n") + 1

        return (
            f"✓ Edited {user_path}\n"
            f"  Replaced {replaced_count} occurrence(s) at ~line {lines_before}\n"
            f"  Lines: {old_lines} → {new_lines}\n"
            f"  Backup: {backup_path.name}"
        )
