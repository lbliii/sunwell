"""File operation handlers."""


import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.tools.handlers.base import BaseHandler, PathSecurityError

if TYPE_CHECKING:
    from sunwell.skills.sandbox import ScriptSandbox


class FileHandlers(BaseHandler):
    """File operation handlers."""

    def __init__(
        self,
        workspace: Path,
        sandbox: ScriptSandbox | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(workspace, **kwargs)
        self.sandbox = sandbox

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

        path.parent.mkdir(parents=True, exist_ok=True)

        content = args.get("content", "")
        path.write_text(content, encoding="utf-8")

        return f"✓ Wrote {user_path} ({len(content):,} bytes)"

    async def edit_file(self, args: dict) -> str:
        """Make targeted edits to a file by replacing specific content."""
        user_path = args["path"]
        old_content = args["old_content"]
        new_content = args["new_content"]
        occurrence = args.get("occurrence", 1)

        path = self._safe_path(user_path, allow_write=True)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {user_path}. Use write_file to create new files."
            )
        if not path.is_file():
            raise ValueError(f"Not a file: {user_path}")

        content = path.read_text(encoding="utf-8")
        count = content.count(old_content)

        if count == 0:
            preview = old_content[:100] + "..." if len(old_content) > 100 else old_content
            raise ValueError(
                f"Content not found in {user_path}.\n"
                f"Looking for:\n{preview}\n\n"
                f"Make sure the content matches exactly, including whitespace and indentation."
            )

        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")

        if occurrence == 0:
            new_file_content = content.replace(old_content, new_content)
            replaced_count = count
        elif occurrence == -1:
            idx = content.rfind(old_content)
            new_file_content = content[:idx] + new_content + content[idx + len(old_content):]
            replaced_count = 1
        else:
            if occurrence > count:
                raise ValueError(
                    f"Requested occurrence {occurrence} but only {count} found in {user_path}"
                )
            idx = -1
            for _ in range(occurrence):
                idx = content.find(old_content, idx + 1)
            new_file_content = content[:idx] + new_content + content[idx + len(old_content):]
            replaced_count = 1

        path.write_text(new_file_content, encoding="utf-8")

        lines_before = content[:content.find(old_content)].count('\n') + 1
        old_lines = old_content.count('\n') + 1
        new_lines = new_content.count('\n') + 1

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
