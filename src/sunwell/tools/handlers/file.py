"""File operation handlers."""


import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.tools.handlers.base import BaseHandler, PathSecurityError

logger = logging.getLogger(__name__)

# Regex for detecting markdown code fences at start of content
_MARKDOWN_FENCE_RE = re.compile(r"^```\w*\n", re.MULTILINE)

if TYPE_CHECKING:
    from sunwell.planning.skills.sandbox import ScriptSandbox

# Type for file event callbacks (RFC-121 lineage integration)
FileEventCallback = Callable[[str, str, str, int, int], None]
# Args: (event_type, path, content, lines_added, lines_removed)


class FileHandlers(BaseHandler):
    """File operation handlers.

    Supports optional file event callbacks for lineage tracking (RFC-121).
    """

    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(workspace, **kwargs)
        self.sandbox = sandbox
        self._file_event_callback: FileEventCallback | None = None

    def set_file_event_callback(self, callback: FileEventCallback | None) -> None:
        """Set callback for file events (RFC-121 lineage tracking).

        Args:
            callback: Function called with (event_type, path, content, lines_added, lines_removed)
        """
        self._file_event_callback = callback

    def _emit_file_event(
        self,
        event_type: str,
        path: str,
        content: str,
        lines_added: int = 0,
        lines_removed: int = 0,
    ) -> None:
        """Emit file event if callback is set.

        Args:
            event_type: "file_created" or "file_modified"
            path: File path relative to workspace
            content: File content
            lines_added: Lines added
            lines_removed: Lines removed
        """
        if self._file_event_callback:
            self._file_event_callback(event_type, path, content, lines_added, lines_removed)

    def _sanitize_content(self, content: str, path: str) -> str:
        """Strip markdown fences if model accidentally included them.

        This is a defensive measure for when LLMs wrap code in markdown fences
        despite being instructed not to. Logs a warning for telemetry.

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
            lines = lines[1:]  # Remove opening fence

        # Check for closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing fence

        sanitized = "\n".join(lines)

        # Log warning for telemetry - indicates model regression or prompt issue
        logger.warning(
            "Stripped markdown fences from write_file content",
            extra={
                "path": path,
                "original_len": len(content),
                "sanitized_len": len(sanitized),
            },
        )

        return sanitized

    async def read_file(self, args: dict) -> str:
        """Read file contents. Respects blocked patterns."""
        path = self._safe_path(args["path"])

        if not path.exists():
            raise FileNotFoundError(f"File not found: {args['path']}")
        if not path.is_file():
            raise ValueError(f"Not a file: {args['path']}")

        size = path.stat().st_size
        if size > 1_000_000:
            return f"File too large ({size:,} bytes). Use search_files to find specific content."

        content = path.read_text(encoding="utf-8", errors="replace")
        return f"```\n{content}\n```\n({len(content):,} bytes)"

    async def write_file(self, args: dict) -> str:
        """Write file contents. Creates parent directories."""
        user_path = args["path"]

        if not user_path or user_path in (".", "..", "/"):
            raise ValueError(f"Invalid file path: '{user_path}'. Must specify a filename.")

        path = self._safe_path(user_path, allow_write=True)

        if path.exists() and path.is_dir():
            raise ValueError(
                f"Cannot write to '{user_path}': path is a directory, not a file. "
                f"Did you mean '{user_path}/filename.ext'?"
            )

        # Track if this is a new file or modification
        is_new = not path.exists()
        old_content = ""
        if not is_new:
            try:
                old_content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        path.parent.mkdir(parents=True, exist_ok=True)

        content = args.get("content", "")
        # Defensive sanitization: strip markdown fences if model included them
        content = self._sanitize_content(content, user_path)
        path.write_text(content, encoding="utf-8")

        # Emit file event for lineage tracking (RFC-121)
        if is_new:
            lines_added = content.count("\n") + 1 if content else 0
            self._emit_file_event("file_created", user_path, content, lines_added, 0)
        else:
            old_lines = old_content.count("\n") + 1 if old_content else 0
            new_lines = content.count("\n") + 1 if content else 0
            lines_added = max(0, new_lines - old_lines)
            lines_removed = max(0, old_lines - new_lines)
            self._emit_file_event("file_modified", user_path, content, lines_added, lines_removed)

        return f"✓ Wrote {user_path} ({len(content):,} bytes)"

    async def edit_file(self, args: dict) -> str:
        """Make targeted edits to a file by replacing specific content."""
        user_path = args["path"]
        old_content_arg = args["old_content"]
        new_content_arg = args["new_content"]
        # Defensive sanitization: strip markdown fences if model included them
        new_content_arg = self._sanitize_content(new_content_arg, user_path)
        occurrence = args.get("occurrence", 1)

        path = self._safe_path(user_path, allow_write=True)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {user_path}. Use write_file to create new files."
            )
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}")

        content = path.read_text(encoding="utf-8")
        count = content.count(old_content_arg)

        if count == 0:
            preview = old_content_arg[:100] + "..." if len(old_content_arg) > 100 else old_content_arg
            raise ValueError(
                f"Content not found in {user_path}.\n"
                f"Looking for:\n{preview}\n\n"
                f"Make sure the content matches exactly, including whitespace and indentation."
            )

        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")

        if occurrence == 0:
            new_file_content = content.replace(old_content_arg, new_content_arg)
            replaced_count = count
        elif occurrence == -1:
            idx = content.rfind(old_content_arg)
            new_file_content = content[:idx] + new_content_arg + content[idx + len(old_content_arg):]
            replaced_count = 1
        else:
            if occurrence > count:
                raise ValueError(
                    f"Requested occurrence {occurrence} but only {count} found in {user_path}"
                )
            idx = -1
            for _ in range(occurrence):
                idx = content.find(old_content_arg, idx + 1)
            new_file_content = content[:idx] + new_content_arg + content[idx + len(old_content_arg):]
            replaced_count = 1

        path.write_text(new_file_content, encoding="utf-8")

        lines_before = content[:content.find(old_content_arg)].count('\n') + 1
        old_lines = old_content_arg.count('\n') + 1
        new_lines = new_content_arg.count('\n') + 1

        # Emit file event for lineage tracking (RFC-121)
        lines_added = max(0, new_lines - old_lines) * replaced_count
        lines_removed = max(0, old_lines - new_lines) * replaced_count
        self._emit_file_event("file_modified", user_path, new_file_content, lines_added, lines_removed)

        return (
            f"✓ Edited {user_path}\n"
            f"  Replaced {replaced_count} occurrence(s) at ~line {lines_before}\n"
            f"  Lines: {old_lines} → {new_lines}\n"
            f"  Backup: {backup_path.name}"
        )

    async def list_files(self, args: dict) -> str:
        """List files in directory. Respects blocked patterns."""
        path = self._safe_path(args.get("path", "."))
        pattern = args.get("pattern", "*")

        if not path.is_dir():
            raise ValueError(f"Not a directory: {args.get('path', '.')}")

        files = []
        for f in sorted(path.glob(pattern)):
            try:
                relative = str(f.relative_to(self.workspace))
                self._safe_path(relative)
                files.append(relative)
            except PathSecurityError:
                continue

        return "\n".join(files[:100]) or "(no matching files)"

    async def search_files(self, args: dict) -> str:
        """Search for pattern in files using ripgrep."""
        search_path = self._safe_path(args.get("path", "."))
        pattern = args["pattern"]
        glob_pattern = args.get("glob", "**/*")

        rg_path = shutil.which("rg")
        if rg_path:
            cmd = [
                rg_path,
                "-n",
                "--max-filesize", "1M",
                "--glob", glob_pattern,
                pattern,
                "."
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
            output = result.stdout[:10_000]
            if result.returncode == 0:
                lines = output.strip().split('\n')
                return f"Found {len(lines)} matches:\n{output}" if output else "No matches found"
            elif result.returncode == 1:
                return "No matches found"
            else:
                return f"Search error: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return "Search timed out after 30s"
        except FileNotFoundError:
            return "Search tools (rg, grep) not available"
