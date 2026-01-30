"""File change preview with approval workflow.

Shows pending file changes with diffs and prompts for approval
before applying changes.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from sunwell.agent.hooks import HookEvent, emit_hook_sync
from sunwell.interface.cli.diff.renderer import DiffRenderer, DiffStats, generate_unified_diff

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Type of file change."""
    
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class ApprovalChoice(Enum):
    """User's approval decision."""
    
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    SKIP = "skip"
    APPROVE_ALL = "approve_all"
    REJECT_ALL = "reject_all"


@dataclass(slots=True)
class FileChange:
    """A pending file change.
    
    Attributes:
        path: Path to the file
        change_type: Type of change (create/modify/delete)
        old_content: Original content (empty for create)
        new_content: New content (empty for delete)
        description: Optional description of the change
    """
    
    path: Path
    change_type: ChangeType
    old_content: str = ""
    new_content: str = ""
    description: str = ""
    
    @property
    def diff(self) -> str:
        """Generate unified diff for this change."""
        return generate_unified_diff(
            self.path,
            self.old_content,
            self.new_content,
        )
    
    @property
    def stats(self) -> DiffStats:
        """Get diff statistics."""
        lines = self.diff.splitlines()
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        hunks = sum(1 for l in lines if l.startswith("@@"))
        return DiffStats(additions=additions, deletions=deletions, hunks=hunks)


@dataclass
class FileChangePreview:
    """Manages preview and approval of file changes.
    
    Usage:
        preview = FileChangePreview(console)
        preview.add_change(FileChange(path, ChangeType.MODIFY, old, new))
        approved = await preview.show_and_approve()
    """
    
    console: Console
    changes: list[FileChange] = field(default_factory=list)
    auto_approve: bool = False
    
    def add_change(self, change: FileChange) -> None:
        """Add a file change to preview.
        
        Args:
            change: The file change
        """
        self.changes.append(change)
        
        # Emit hook
        emit_hook_sync(
            HookEvent.FILE_CHANGE_PENDING,
            file_path=str(change.path),
            change_type=change.change_type.value,
            diff=change.diff,
        )
    
    def add_create(
        self,
        path: Path | str,
        content: str,
        description: str = "",
    ) -> None:
        """Add a file creation.
        
        Args:
            path: Path to new file
            content: File content
            description: Optional description
        """
        self.add_change(FileChange(
            path=Path(path),
            change_type=ChangeType.CREATE,
            old_content="",
            new_content=content,
            description=description,
        ))
    
    def add_modify(
        self,
        path: Path | str,
        old_content: str,
        new_content: str,
        description: str = "",
    ) -> None:
        """Add a file modification.
        
        Args:
            path: Path to file
            old_content: Original content
            new_content: New content
            description: Optional description
        """
        self.add_change(FileChange(
            path=Path(path),
            change_type=ChangeType.MODIFY,
            old_content=old_content,
            new_content=new_content,
            description=description,
        ))
    
    def add_delete(
        self,
        path: Path | str,
        content: str = "",
        description: str = "",
    ) -> None:
        """Add a file deletion.
        
        Args:
            path: Path to file
            content: Current content (for diff display)
            description: Optional description
        """
        self.add_change(FileChange(
            path=Path(path),
            change_type=ChangeType.DELETE,
            old_content=content,
            new_content="",
            description=description,
        ))
    
    def show_summary(self) -> None:
        """Display a summary table of pending changes."""
        if not self.changes:
            self.console.print("  [dim]No pending changes[/]")
            return
        
        table = Table(
            title="[holy.gold]Pending Changes[/]",
            border_style="holy.gold.dim",
            show_header=True,
        )
        table.add_column("Type", style="bold")
        table.add_column("Path")
        table.add_column("Changes", justify="right")
        
        for change in self.changes:
            # Type with color
            type_styles = {
                ChangeType.CREATE: ("[green]+[/]", "create"),
                ChangeType.MODIFY: ("[yellow]~[/]", "modify"),
                ChangeType.DELETE: ("[red]-[/]", "delete"),
            }
            icon, label = type_styles[change.change_type]
            
            # Stats
            stats = change.stats
            stats_str = stats.format()
            
            table.add_row(
                f"{icon} {label}",
                str(change.path),
                stats_str,
            )
        
        self.console.print()
        self.console.print(table)
        self.console.print()
    
    def show_change(self, change: FileChange, index: int) -> None:
        """Display a single change with diff.
        
        Args:
            change: The change to display
            index: Index in the changes list (1-based for display)
        """
        # Header
        type_styles = {
            ChangeType.CREATE: ("green", "+", "Creating"),
            ChangeType.MODIFY: ("yellow", "~", "Modifying"),
            ChangeType.DELETE: ("red", "-", "Deleting"),
        }
        color, icon, action = type_styles[change.change_type]
        
        self.console.print(f"\n  [{color}]{icon}[/] {action} [bold]{change.path}[/]")
        
        if change.description:
            self.console.print(f"    [dim]{change.description}[/]")
        
        # Show diff
        renderer = DiffRenderer(self.console)
        
        if change.change_type == ChangeType.CREATE:
            # For creates, show the new content
            renderer.render_file_change(
                change.path,
                "",
                change.new_content,
                change_type="create",
            )
        elif change.change_type == ChangeType.DELETE:
            # For deletes, show what's being removed
            renderer.render_file_change(
                change.path,
                change.old_content,
                "",
                change_type="delete",
            )
        else:
            # For modifications, show the diff
            renderer.render_file_change(
                change.path,
                change.old_content,
                change.new_content,
                change_type="modify",
            )
    
    def prompt_approval(self, change: FileChange, index: int, total: int) -> ApprovalChoice:
        """Prompt user for approval of a single change.
        
        Args:
            change: The change
            index: Current index (1-based)
            total: Total number of changes
            
        Returns:
            User's choice
        """
        self.console.print()
        self.console.print(f"  [holy.gold]Change {index}/{total}[/]")
        
        choices = {
            "y": ("Approve", ApprovalChoice.APPROVE),
            "n": ("Reject", ApprovalChoice.REJECT),
            "s": ("Skip", ApprovalChoice.SKIP),
            "a": ("Approve all", ApprovalChoice.APPROVE_ALL),
            "r": ("Reject all", ApprovalChoice.REJECT_ALL),
        }
        
        prompt_text = " / ".join(
            f"[bold]{k}[/]={v[0]}" for k, v in choices.items()
        )
        
        while True:
            choice = Prompt.ask(
                f"  {prompt_text}",
                default="y",
            ).lower()
            
            if choice in choices:
                return choices[choice][1]
            
            self.console.print("  [dim]Invalid choice. Try again.[/]")
    
    async def show_and_approve(self) -> list[FileChange]:
        """Show all changes and get approval.
        
        Returns:
            List of approved changes
        """
        if not self.changes:
            return []
        
        if self.auto_approve:
            # Auto-approve all
            for change in self.changes:
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_APPROVED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                )
            return self.changes
        
        # Show summary first
        self.show_summary()
        
        approved: list[FileChange] = []
        approve_all = False
        reject_all = False
        
        for i, change in enumerate(self.changes, 1):
            if reject_all:
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_REJECTED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                    reason="User rejected all",
                )
                continue
            
            if approve_all:
                approved.append(change)
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_APPROVED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                )
                continue
            
            # Show the change
            self.show_change(change, i)
            
            # Get approval
            choice = self.prompt_approval(change, i, len(self.changes))
            
            if choice == ApprovalChoice.APPROVE:
                approved.append(change)
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_APPROVED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                )
            elif choice == ApprovalChoice.APPROVE_ALL:
                approve_all = True
                approved.append(change)
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_APPROVED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                )
            elif choice == ApprovalChoice.REJECT:
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_REJECTED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                    reason="User rejected",
                )
            elif choice == ApprovalChoice.REJECT_ALL:
                reject_all = True
                emit_hook_sync(
                    HookEvent.FILE_CHANGE_REJECTED,
                    file_path=str(change.path),
                    change_type=change.change_type.value,
                    reason="User rejected all",
                )
            # SKIP doesn't emit either event
        
        # Summary
        self.console.print()
        if approved:
            self.console.print(f"  [holy.success]✓ {len(approved)} changes approved[/]")
        rejected = len(self.changes) - len(approved)
        if rejected:
            self.console.print(f"  [void.purple]✗ {rejected} changes rejected[/]")
        
        return approved


def render_change_preview(
    console: Console,
    changes: list[dict[str, Any]],
    *,
    auto_approve: bool = False,
) -> list[dict[str, Any]]:
    """Convenience function to preview and approve changes.
    
    Args:
        console: Rich console
        changes: List of change dicts with keys:
            - path: File path
            - type: "create", "modify", or "delete"
            - old_content: Original content (for modify/delete)
            - new_content: New content (for create/modify)
            - description: Optional description
        auto_approve: Skip approval prompts
        
    Returns:
        List of approved change dicts
    """
    import asyncio
    
    preview = FileChangePreview(console, auto_approve=auto_approve)
    
    for change_dict in changes:
        change_type = ChangeType(change_dict.get("type", "modify"))
        change = FileChange(
            path=Path(change_dict["path"]),
            change_type=change_type,
            old_content=change_dict.get("old_content", ""),
            new_content=change_dict.get("new_content", ""),
            description=change_dict.get("description", ""),
        )
        preview.add_change(change)
    
    # Run approval loop
    loop = asyncio.get_event_loop()
    approved_changes = loop.run_until_complete(preview.show_and_approve())
    
    # Convert back to dicts
    return [
        {
            "path": str(c.path),
            "type": c.change_type.value,
            "old_content": c.old_content,
            "new_content": c.new_content,
            "description": c.description,
        }
        for c in approved_changes
    ]
