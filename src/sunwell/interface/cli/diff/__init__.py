"""Inline Diff Visualization with Holy Light Theme.

Renders git-style diffs in the terminal with Sunwell's branded colors:
- Green (holy.success) for additions
- Red (void.purple) for deletions  
- Yellow (holy.gold) for hunk headers
- Dim for context lines

Usage:
    from sunwell.interface.cli.diff import DiffRenderer, render_file_diff
    
    renderer = DiffRenderer(console)
    renderer.render_unified_diff(diff_text)
    
    # Or render file change preview
    render_file_diff(console, file_path, old_content, new_content)
"""

from sunwell.interface.cli.diff.renderer import (
    DiffRenderer,
    render_file_diff,
    render_inline_diff,
)
from sunwell.interface.cli.diff.preview import (
    FileChangePreview,
    render_change_preview,
)

__all__ = [
    "DiffRenderer",
    "render_file_diff",
    "render_inline_diff",
    "FileChangePreview",
    "render_change_preview",
]
