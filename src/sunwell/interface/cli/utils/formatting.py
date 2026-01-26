"""CLI formatting utilities for tables and trees.

RFC-138: Module Architecture Consolidation

Provides generic formatting helpers for CLI output.
"""

from collections.abc import Sequence


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    max_width: int | None = None,
) -> str:
    """Format data as a simple text table.

    Args:
        headers: Column headers
        rows: Rows of data (each row is a sequence of strings)
        max_width: Maximum width per column (None = auto)

    Returns:
        Formatted table string

    Example:
        >>> headers = ["Name", "Age"]
        >>> rows = [["Alice", "30"], ["Bob", "25"]]
        >>> print(format_table(headers, rows))
        Name  Age
        ----- ---
        Alice 30
        Bob   25
    """
    if not headers:
        return ""

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Apply max_width if specified
    if max_width:
        col_widths = [min(w, max_width) for w in col_widths]

    # Format header
    header_row = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths, strict=True))
    separator = "  ".join("-" * w for w in col_widths)

    # Format rows
    formatted_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                cell_str = str(cell)
                if max_width and len(cell_str) > max_width:
                    cell_str = cell_str[: max_width - 3] + "..."
                cells.append(cell_str.ljust(col_widths[i]))
        formatted_rows.append("  ".join(cells))

    return "\n".join([header_row, separator] + formatted_rows)


def format_tree(
    items: Sequence[tuple[str, Sequence[str]]],
    prefix: str = "",
    is_last: bool = True,
) -> str:
    """Format items as a tree structure.

    Args:
        items: Sequence of (label, children) tuples
        prefix: Current prefix for indentation
        is_last: Whether this is the last item at this level

    Returns:
        Formatted tree string

    Example:
        >>> items = [("root", [("child1", []), ("child2", [])])]
        >>> print(format_tree(items))
        root
        ├─ child1
        └─ child2
    """
    lines: list[str] = []

    for i, (label, children) in enumerate(items):
        is_last_item = i == len(items) - 1
        connector = "└─ " if is_last_item else "├─ "
        lines.append(f"{prefix}{connector}{label}")

        if children:
            extension = "   " if is_last_item else "│  "
            child_prefix = prefix + extension
            lines.append(format_tree(children, child_prefix, is_last_item))

    return "\n".join(lines)
