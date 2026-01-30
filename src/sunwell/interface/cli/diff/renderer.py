"""Diff renderer with Holy Light theme colors.

Renders unified diffs in the terminal with Sunwell styling:
- Green for additions (+)
- Red/Magenta for deletions (-)
- Yellow for hunk headers (@@)
- Dim for context lines
"""

import difflib
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from sunwell.interface.cli.core.theme import SUNWELL_THEME


@dataclass(frozen=True, slots=True)
class DiffStats:
    """Statistics about a diff."""
    
    additions: int
    deletions: int
    hunks: int
    
    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions
    
    def format(self) -> str:
        """Format stats as a string."""
        parts = []
        if self.additions:
            parts.append(f"+{self.additions}")
        if self.deletions:
            parts.append(f"-{self.deletions}")
        return ", ".join(parts) if parts else "no changes"


class DiffRenderer:
    """Renders unified diffs with Holy Light theme styling.
    
    Usage:
        renderer = DiffRenderer(console)
        stats = renderer.render_unified_diff(diff_text)
        # or
        stats = renderer.render_file_change(path, old_content, new_content)
    """
    
    def __init__(
        self,
        console: Console | None = None,
        *,
        context_lines: int = 3,
        show_line_numbers: bool = True,
        max_lines: int = 100,
    ) -> None:
        """Initialize the renderer.
        
        Args:
            console: Rich console (creates one if not provided)
            context_lines: Lines of context around changes
            show_line_numbers: Show line numbers in output
            max_lines: Maximum lines to display (truncate after)
        """
        self.console = console or Console(theme=SUNWELL_THEME)
        self.context_lines = context_lines
        self.show_line_numbers = show_line_numbers
        self.max_lines = max_lines
    
    def render_unified_diff(
        self,
        diff_text: str,
        *,
        title: str | None = None,
    ) -> DiffStats:
        """Render a unified diff string.
        
        Args:
            diff_text: Unified diff text
            title: Optional title for the panel
            
        Returns:
            DiffStats with change counts
        """
        lines = diff_text.splitlines()
        stats = self._count_stats(lines)
        
        # Build styled text
        styled = Text()
        line_count = 0
        
        for line in lines:
            if line_count >= self.max_lines:
                styled.append(f"\n... ({len(lines) - line_count} more lines)", style="dim")
                break
            
            styled_line = self._style_line(line)
            styled.append(styled_line)
            styled.append("\n")
            line_count += 1
        
        # Render in panel
        panel_title = title or "Changes"
        stats_str = f" ({stats.format()})"
        
        self.console.print(Panel(
            styled,
            title=f"[holy.gold]{panel_title}[/]{stats_str}",
            border_style="holy.gold.dim",
            padding=(0, 1),
        ))
        
        return stats
    
    def render_file_change(
        self,
        file_path: str | Path,
        old_content: str,
        new_content: str,
        *,
        change_type: str = "modify",
    ) -> DiffStats:
        """Render a diff between old and new file content.
        
        Args:
            file_path: Path to the file
            old_content: Original content (empty for new files)
            new_content: New content (empty for deleted files)
            change_type: One of "create", "modify", "delete"
            
        Returns:
            DiffStats with change counts
        """
        path_str = str(file_path)
        
        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path_str}",
            tofile=f"b/{path_str}",
            n=self.context_lines,
        )
        
        diff_text = "".join(diff)
        
        if not diff_text:
            self.console.print(f"  [dim]No changes in {path_str}[/]")
            return DiffStats(additions=0, deletions=0, hunks=0)
        
        # Add file operation indicator
        op_style, op_icon = self._get_operation_style(change_type)
        self.console.print(f"\n  [{op_style}]{op_icon}[/] {path_str}")
        
        return self.render_unified_diff(diff_text, title=path_str)
    
    def _style_line(self, line: str) -> Text:
        """Style a single diff line.
        
        Args:
            line: Raw diff line
            
        Returns:
            Styled Rich Text
        """
        text = Text()
        
        if line.startswith("+++") or line.startswith("---"):
            # File headers
            text.append(line, style="bold white")
        elif line.startswith("@@"):
            # Hunk header
            text.append(line, style="holy.gold")
        elif line.startswith("+"):
            # Addition
            text.append(line, style="green")
        elif line.startswith("-"):
            # Deletion
            text.append(line, style="red")
        elif line.startswith("\\"):
            # "No newline at end of file"
            text.append(line, style="dim")
        else:
            # Context line
            text.append(line, style="dim white")
        
        return text
    
    def _count_stats(self, lines: list[str]) -> DiffStats:
        """Count additions, deletions, and hunks.
        
        Args:
            lines: Diff lines
            
        Returns:
            DiffStats
        """
        additions = 0
        deletions = 0
        hunks = 0
        
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
            elif line.startswith("@@"):
                hunks += 1
        
        return DiffStats(
            additions=additions,
            deletions=deletions,
            hunks=hunks,
        )
    
    def _get_operation_style(self, change_type: str) -> tuple[str, str]:
        """Get style and icon for file operation.
        
        Args:
            change_type: Operation type
            
        Returns:
            Tuple of (style, icon)
        """
        operations = {
            "create": ("green", "+"),
            "modify": ("yellow", "~"),
            "delete": ("red", "-"),
        }
        return operations.get(change_type, ("white", "?"))


def render_file_diff(
    console: Console,
    file_path: str | Path,
    old_content: str,
    new_content: str,
    *,
    change_type: str = "modify",
    context_lines: int = 3,
) -> DiffStats:
    """Convenience function to render a file diff.
    
    Args:
        console: Rich console
        file_path: Path to file
        old_content: Original content
        new_content: New content
        change_type: Operation type
        context_lines: Context lines around changes
        
    Returns:
        DiffStats
    """
    renderer = DiffRenderer(console, context_lines=context_lines)
    return renderer.render_file_change(
        file_path,
        old_content,
        new_content,
        change_type=change_type,
    )


def render_inline_diff(
    console: Console,
    old_text: str,
    new_text: str,
    *,
    label: str = "",
) -> None:
    """Render an inline diff of two text strings.
    
    Good for showing small changes like variable renames.
    
    Args:
        console: Rich console
        old_text: Original text
        new_text: New text
        label: Optional label
    """
    # Use difflib to find differences
    matcher = difflib.SequenceMatcher(None, old_text, new_text)
    
    old_styled = Text()
    new_styled = Text()
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            old_styled.append(old_text[i1:i2], style="dim")
            new_styled.append(new_text[j1:j2], style="dim")
        elif op == "delete":
            old_styled.append(old_text[i1:i2], style="red strike")
        elif op == "insert":
            new_styled.append(new_text[j1:j2], style="green bold")
        elif op == "replace":
            old_styled.append(old_text[i1:i2], style="red strike")
            new_styled.append(new_text[j1:j2], style="green bold")
    
    if label:
        console.print(f"  [holy.gold]{label}:[/]")
    
    console.print("    ", old_styled, " → ", new_styled)


def generate_unified_diff(
    file_path: str | Path,
    old_content: str,
    new_content: str,
    context_lines: int = 3,
) -> str:
    """Generate unified diff text without rendering.
    
    Args:
        file_path: Path to file
        old_content: Original content
        new_content: New content
        context_lines: Context lines
        
    Returns:
        Unified diff string
    """
    path_str = str(file_path)
    
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path_str}",
        tofile=f"b/{path_str}",
        n=context_lines,
    )
    
    return "".join(diff)
