"""Sunwell Native Files Provider (RFC-078).

File system access provider for the workspace.
"""

import fnmatch
import os
from datetime import datetime
from pathlib import Path

from sunwell.providers.base import FileInfo, FilesProvider


class SunwellFiles(FilesProvider):
    """Sunwell-native file system provider."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize with workspace root directory.

        Args:
            root_dir: The workspace root directory to operate within.
        """
        self.root = root_dir.resolve()

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path, ensuring it's within the workspace root."""
        resolved = (self.root / path).resolve()
        # Security: ensure we stay within root
        if not str(resolved).startswith(str(self.root)):
            raise ValueError(f"Path {path} escapes workspace root")
        return resolved

    def _file_info(self, path: Path) -> FileInfo:
        """Create FileInfo from a Path."""
        stat = path.stat()
        return FileInfo(
            path=str(path.relative_to(self.root)),
            name=path.name,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
            is_directory=path.is_dir(),
            extension=path.suffix[1:] if path.suffix else None,
        )

    async def list_files(
        self, path: str = ".", recursive: bool = False
    ) -> list[FileInfo]:
        """List files in a directory.

        Args:
            path: Directory path relative to workspace root.
            recursive: If True, list files recursively.

        Returns:
            List of FileInfo objects.
        """
        target = self._resolve_path(path)
        if not target.exists():
            return []
        if not target.is_dir():
            return [self._file_info(target)]

        results: list[FileInfo] = []

        if recursive:
            for root, dirs, files in os.walk(target):
                root_path = Path(root)
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in files:
                    if not name.startswith("."):
                        file_path = root_path / name
                        results.append(self._file_info(file_path))
        else:
            for entry in target.iterdir():
                if not entry.name.startswith("."):
                    results.append(self._file_info(entry))

        # Sort: directories first, then by name
        return sorted(
            results,
            key=lambda f: (not f.is_directory, f.name.lower()),
        )

    async def search_files(
        self, query: str, path: str | None = None
    ) -> list[FileInfo]:
        """Search files by name pattern.

        Args:
            query: Search query (supports * and ? wildcards).
            path: Optional directory to search within.

        Returns:
            List of matching FileInfo objects.
        """
        search_root = self._resolve_path(path or ".")
        if not search_root.exists() or not search_root.is_dir():
            return []

        # Normalize query for case-insensitive matching
        query_lower = query.lower()
        results: list[FileInfo] = []

        # Walk the directory tree
        for root, dirs, files in os.walk(search_root):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for name in files:
                if name.startswith("."):
                    continue

                # Check if name matches query (glob pattern or substring)
                name_lower = name.lower()
                if "*" in query or "?" in query:
                    if fnmatch.fnmatch(name_lower, query_lower):
                        file_path = Path(root) / name
                        results.append(self._file_info(file_path))
                elif query_lower in name_lower:
                    file_path = Path(root) / name
                    results.append(self._file_info(file_path))

            # Limit results for performance
            if len(results) >= 100:
                break

        # Sort by modification time (most recent first)
        return sorted(results, key=lambda f: f.modified, reverse=True)

    async def read_file(self, path: str) -> str:
        """Read file contents as text.

        Args:
            path: File path relative to workspace root.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file is binary.
        """
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if target.is_dir():
            raise ValueError(f"Cannot read directory: {path}")

        # Try to read as text, with size limit for safety
        max_size = 1024 * 1024  # 1MB
        if target.stat().st_size > max_size:
            raise ValueError(f"File too large: {path} (>{max_size} bytes)")

        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"Binary file cannot be read as text: {path}") from e

    async def get_metadata(self, path: str) -> FileInfo | None:
        """Get metadata for a specific file.

        Args:
            path: File path relative to workspace root.

        Returns:
            FileInfo if file exists, None otherwise.
        """
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return None
            return self._file_info(target)
        except ValueError:
            return None
