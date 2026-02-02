"""Deep link generation for notifications.

Creates clickable deep links to open files, sessions, and other resources
directly from notifications.

Supported targets:
- VS Code: vscode://file/{path}:{line}:{column}
- Cursor: cursor://file/{path}:{line}:{column}
- Terminal sessions: File path for reference

Example:
    # Create context for a file notification
    context = create_file_context("/path/to/file.py", line=42, column=10)
    await notifier.send("Error", "Syntax error", NotificationType.ERROR, context=context)
    # Click opens file at line 42, column 10
"""

import urllib.parse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DeepLinkTarget(Enum):
    """Supported deep link targets."""
    
    VSCODE = "vscode"
    CURSOR = "cursor"
    ITERM = "iterm"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class DeepLink:
    """A deep link URL and metadata.
    
    Attributes:
        url: The deep link URL
        target: Target application
        fallback_path: Fallback file path if URL not supported
    """
    
    url: str
    target: DeepLinkTarget
    fallback_path: str | None = None
    
    def __str__(self) -> str:
        return self.url


def create_deep_link(
    file_path: str | Path,
    *,
    line: int | None = None,
    column: int | None = None,
    target: DeepLinkTarget = DeepLinkTarget.VSCODE,
) -> DeepLink:
    """Create a deep link to a file location.
    
    Args:
        file_path: Path to the file
        line: Line number (1-indexed)
        column: Column number (1-indexed)
        target: Target application (vscode, cursor, etc.)
        
    Returns:
        DeepLink with URL and metadata
        
    Example:
        >>> link = create_deep_link("/path/to/file.py", line=42)
        >>> str(link)
        'vscode://file//path/to/file.py:42'
    """
    path = Path(file_path).resolve()
    path_str = str(path)
    
    if target == DeepLinkTarget.VSCODE:
        url = _create_vscode_link(path_str, line, column)
    elif target == DeepLinkTarget.CURSOR:
        url = _create_cursor_link(path_str, line, column)
    elif target == DeepLinkTarget.ITERM:
        url = _create_iterm_link(path_str)
    else:
        # Fallback to file path
        url = f"file://{path_str}"
    
    return DeepLink(
        url=url,
        target=target,
        fallback_path=path_str,
    )


def _create_vscode_link(
    path: str,
    line: int | None,
    column: int | None,
) -> str:
    """Create a VS Code deep link.
    
    Format: vscode://file/{path}:{line}:{column}
    """
    url = f"vscode://file/{path}"
    if line is not None:
        url += f":{line}"
        if column is not None:
            url += f":{column}"
    return url


def _create_cursor_link(
    path: str,
    line: int | None,
    column: int | None,
) -> str:
    """Create a Cursor deep link.
    
    Format: cursor://file/{path}:{line}:{column}
    """
    url = f"cursor://file/{path}"
    if line is not None:
        url += f":{line}"
        if column is not None:
            url += f":{column}"
    return url


def _create_iterm_link(path: str) -> str:
    """Create an iTerm2 deep link.
    
    Note: iTerm doesn't have a direct file open protocol,
    so this creates a generic file URL.
    """
    return f"file://{path}"


def create_file_context(
    file_path: str | Path,
    *,
    line: int | None = None,
    column: int | None = None,
    workspace: str | Path | None = None,
) -> dict:
    """Create a notification context for a file location.
    
    This context can be passed to notification methods to enable
    deep linking when the notification is clicked.
    
    Args:
        file_path: Path to the file
        line: Line number (1-indexed)
        column: Column number (1-indexed)
        workspace: Workspace root for relative path display
        
    Returns:
        Context dictionary with file information
        
    Example:
        >>> context = create_file_context("/path/to/file.py", line=42)
        >>> await notifier.send("Error", "...", context=context)
    """
    path = Path(file_path).resolve()
    
    context: dict = {
        "file": str(path),
        "type": "file",
    }
    
    if line is not None:
        context["line"] = line
    if column is not None:
        context["column"] = column
    
    # Add relative path if workspace provided
    if workspace is not None:
        workspace_path = Path(workspace).resolve()
        try:
            rel_path = path.relative_to(workspace_path)
            context["relative_path"] = str(rel_path)
        except ValueError:
            pass  # File not in workspace
    
    # Pre-generate deep link URL
    link = create_deep_link(path, line=line, column=column)
    context["deep_link"] = str(link)
    
    return context


def create_session_context(
    session_id: str,
    *,
    workspace: str | Path | None = None,
    run_id: str | None = None,
) -> dict:
    """Create a notification context for a session.
    
    Args:
        session_id: Sunwell session ID
        workspace: Workspace root
        run_id: Optional run ID within the session
        
    Returns:
        Context dictionary with session information
        
    Example:
        >>> context = create_session_context("abc123", workspace="/path")
        >>> await notifier.send("Complete", "...", context=context)
    """
    context: dict = {
        "session_id": session_id,
        "type": "session",
    }
    
    if workspace is not None:
        context["workspace"] = str(Path(workspace).resolve())
    if run_id is not None:
        context["run_id"] = run_id
    
    return context


def get_deep_link_from_context(context: dict | None) -> str | None:
    """Extract or generate a deep link URL from context.
    
    Args:
        context: Notification context dictionary
        
    Returns:
        Deep link URL if available, None otherwise
    """
    if context is None:
        return None
    
    # Check for pre-generated deep link
    if "deep_link" in context:
        return context["deep_link"]
    
    # Try to generate from file info
    if "file" in context:
        link = create_deep_link(
            context["file"],
            line=context.get("line"),
            column=context.get("column"),
        )
        return str(link)
    
    return None
