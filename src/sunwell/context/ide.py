"""IDE context bridge for RFC-024.

Provides context from IDE extensions (VS Code, Neovim, Cursor, etc.)
for resolving @file, @selection, and other IDE-specific references.

Context can be provided via:
- Environment variable: SUNWELL_IDE_CONTEXT (path to JSON file)
- CLI option: --ide-context <path>
- Direct construction in code

Example JSON format:
{
    "focused_file": "/path/to/file.py",
    "selection": "selected text content",
    "cursor_position": [10, 5],
    "open_files": ["/path/to/file1.py", "/path/to/file2.py"],
    "visible_range": [5, 50],
    "diagnostics": [{"line": 10, "message": "unused import", "severity": 1}],
    "workspace_folders": ["/path/to/workspace"]
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class IDEContext:
    """Context from IDE extension.
    
    This dataclass captures the current state of the IDE to enable
    @file, @selection, and other context references.
    
    Passed via:
    - Environment variable: SUNWELL_IDE_CONTEXT (path to JSON file)
    - CLI option: --ide-context <path>
    - Stdin pipe: echo '{"focused_file": "..."}' | sunwell ...
    """
    
    focused_file: str | None = None
    """Currently focused file path (absolute)."""
    
    selection: str | None = None
    """Selected text content."""
    
    cursor_position: tuple[int, int] | None = None
    """Cursor position as (line, column), 0-indexed."""
    
    open_files: list[str] = field(default_factory=list)
    """All open file paths."""
    
    visible_range: tuple[int, int] | None = None
    """Visible line range as (start, end)."""
    
    diagnostics: list[dict] | None = None
    """Linter errors/warnings from IDE.
    
    Each diagnostic dict has:
    - line: int - line number
    - message: str - diagnostic message
    - severity: int - severity level
    """
    
    workspace_folders: list[str] = field(default_factory=list)
    """Workspace folders from IDE (multi-root support)."""
    
    @classmethod
    def from_json(cls, data: dict) -> IDEContext:
        """Parse from JSON (from IDE extension).
        
        Args:
            data: Dictionary with IDE context fields
            
        Returns:
            IDEContext instance
        """
        return cls(
            focused_file=data.get("focused_file"),
            selection=data.get("selection"),
            cursor_position=tuple(data["cursor_position"]) if data.get("cursor_position") else None,
            open_files=data.get("open_files", []),
            visible_range=tuple(data["visible_range"]) if data.get("visible_range") else None,
            diagnostics=data.get("diagnostics"),
            workspace_folders=data.get("workspace_folders", []),
        )
    
    @classmethod
    def from_file(cls, path: str) -> IDEContext:
        """Load from a JSON file.
        
        Args:
            path: Path to JSON file
            
        Returns:
            IDEContext instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(path, encoding="utf-8") as f:
            return cls.from_json(json.load(f))
    
    @classmethod
    def from_env(cls) -> IDEContext | None:
        """Load from SUNWELL_IDE_CONTEXT environment variable.
        
        The environment variable should contain a path to a JSON file.
        
        Returns:
            IDEContext instance if env var is set and file is valid,
            None otherwise.
        """
        path = os.environ.get("SUNWELL_IDE_CONTEXT")
        if not path:
            return None
        
        try:
            return cls.from_file(path)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def to_json(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "focused_file": self.focused_file,
            "selection": self.selection,
            "cursor_position": list(self.cursor_position) if self.cursor_position else None,
            "open_files": self.open_files,
            "visible_range": list(self.visible_range) if self.visible_range else None,
            "diagnostics": self.diagnostics,
            "workspace_folders": self.workspace_folders,
        }
    
    def has_selection(self) -> bool:
        """Check if there's selected text."""
        return bool(self.selection)
    
    def has_focused_file(self) -> bool:
        """Check if there's a focused file."""
        return bool(self.focused_file)
