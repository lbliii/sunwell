"""DAG Path Display for intent visualization.

Shows the current position in the Conversational DAG tree
with Holy Light themed styling.
"""

from dataclasses import dataclass, field
from typing import Sequence

from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text

from sunwell.interface.cli.core.theme import SUNWELL_THEME


# Node display names and styles
NODE_STYLES: dict[str, tuple[str, str]] = {
    # Root
    "conversation": ("Conversation", "holy.gold"),
    # Understanding branch
    "understand": ("Understand", "holy.gold"),
    "clarify": ("Clarify", "holy.gold.dim"),
    "explain": ("Explain", "holy.gold.dim"),
    # Analysis branch
    "analyze": ("Analyze", "holy.gold"),
    "review": ("Review", "holy.gold.dim"),
    "audit": ("Audit", "holy.gold.dim"),
    # Planning branch
    "plan": ("Plan", "holy.gold"),
    "design": ("Design", "holy.gold.dim"),
    "decompose": ("Decompose", "holy.gold.dim"),
    # Action branch
    "act": ("Act", "void.indigo"),
    "read": ("Read", "holy.gold"),
    "write": ("Write", "void.purple"),
    "create": ("Create", "green"),
    "modify": ("Modify", "yellow"),
    "delete": ("Delete", "red"),
}


@dataclass
class DAGPathDisplay:
    """Displays the current DAG intent path.
    
    Shows a breadcrumb-style path visualization with
    appropriate styling for each node type.
    
    Example:
        >>> display = DAGPathDisplay(console)
        >>> display.update(["conversation", "act", "write", "modify"])
        ┌─ Path: Conversation → Act → Write → Modify ─┐
    """
    
    console: Console
    current_path: list[str] = field(default_factory=list)
    show_panel: bool = True
    
    def __post_init__(self) -> None:
        if not hasattr(self.console, "theme") or self.console.theme is None:
            self.console = Console(theme=SUNWELL_THEME)
    
    def update(self, path: Sequence[str]) -> None:
        """Update the displayed path.
        
        Args:
            path: New DAG path (e.g., ["conversation", "act", "write"])
        """
        self.current_path = list(path)
        self.render()
    
    def render(self) -> None:
        """Render the current path to the console."""
        if not self.current_path:
            return
        
        path_text = self._format_path()
        
        if self.show_panel:
            self.console.print(Panel(
                path_text,
                title="[holy.gold]Path[/]",
                border_style="holy.gold.dim",
                padding=(0, 1),
            ))
        else:
            self.console.print(f"  [holy.gold]Path:[/] {path_text}")
    
    def _format_path(self) -> Text:
        """Format the path as styled Rich text.
        
        Returns:
            Styled Text object
        """
        text = Text()
        
        for i, node in enumerate(self.current_path):
            # Add separator
            if i > 0:
                text.append(" → ", style="dim")
            
            # Get display name and style
            display_name, style = NODE_STYLES.get(
                node.lower(),
                (node.title(), "white"),
            )
            
            # Highlight the terminal node (last in path)
            if i == len(self.current_path) - 1:
                text.append(display_name, style=f"bold {style}")
            else:
                text.append(display_name, style=style)
        
        return text
    
    def render_inline(self) -> str:
        """Get path as inline string for status bar.
        
        Returns:
            Plain text path representation
        """
        if not self.current_path:
            return ""
        
        names = []
        for node in self.current_path:
            display_name, _ = NODE_STYLES.get(
                node.lower(),
                (node.title(), "white"),
            )
            names.append(display_name)
        
        return " → ".join(names)
    
    def get_terminal_node(self) -> str | None:
        """Get the terminal (deepest) node in the path.
        
        Returns:
            Terminal node name or None if path is empty
        """
        if not self.current_path:
            return None
        return self.current_path[-1]
    
    def get_depth(self) -> int:
        """Get the current path depth.
        
        Returns:
            Number of nodes in path
        """
        return len(self.current_path)


def format_dag_path(path: Sequence[str], *, bold_terminal: bool = True) -> Text:
    """Format a DAG path as styled Rich text.
    
    Args:
        path: DAG path nodes
        bold_terminal: Whether to bold the last node
        
    Returns:
        Styled Text object
    """
    text = Text()
    
    for i, node in enumerate(path):
        if i > 0:
            text.append(" → ", style="dim")
        
        display_name, style = NODE_STYLES.get(
            node.lower(),
            (node.title(), "white"),
        )
        
        if bold_terminal and i == len(path) - 1:
            text.append(display_name, style=f"bold {style}")
        else:
            text.append(display_name, style=style)
    
    return text


def render_path_header(console: Console, path: Sequence[str]) -> None:
    """Render a path header line.
    
    Args:
        console: Rich console
        path: DAG path nodes
    """
    path_text = format_dag_path(path)
    console.print(Panel(
        path_text,
        title="[holy.gold]Intent[/]",
        border_style="holy.gold.dim",
        padding=(0, 1),
    ))
