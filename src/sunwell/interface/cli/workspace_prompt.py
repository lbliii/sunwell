"""CLI workspace prompts and confirmation (RFC-043 addendum).

Provides interactive workspace selection and confirmation for the CLI.
"""


import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from sunwell.knowledge.workspace import (
    ResolutionSource,
    WorkspaceResult,
    default_workspace_root,
    ensure_workspace_exists,
    format_resolution_message,
    resolve_workspace,
)

console = Console()


def resolve_workspace_interactive(
    explicit: Path | str | None = None,
    project_name: str | None = None,
    non_interactive: bool = False,
    quiet: bool = False,
) -> Path:
    """Resolve workspace with interactive confirmation if needed.

    This is the main entry point for CLI commands that need a workspace.

    Args:
        explicit: Explicit path from --workspace flag
        project_name: Name for new project (derived from goal)
        non_interactive: If True, use defaults without prompting
        quiet: If True, suppress informational messages

    Returns:
        Resolved and confirmed workspace path

    Raises:
        SystemExit: If user cancels or resolution fails
    """
    result = resolve_workspace(
        explicit=explicit,
        project_name=project_name,
    )

    # High confidence or explicit - just use it
    if not result.needs_confirmation or non_interactive:
        if not quiet:
            console.print(f"[dim]{format_resolution_message(result)}[/dim]")
        return _finalize_workspace(result, create=not result.exists)

    # Low confidence - need confirmation
    return _prompt_workspace_confirmation(result, project_name)


def _prompt_workspace_confirmation(
    result: WorkspaceResult,
    project_name: str | None,
) -> Path:
    """Prompt user to confirm or change workspace location.

    Args:
        result: Initial resolution result
        project_name: Name for new project

    Returns:
        Confirmed workspace path
    """
    cwd = Path.cwd()

    # Build options
    default_path = default_workspace_root()
    if project_name:
        from sunwell.knowledge.workspace.resolver import _slugify
        default_path = default_path / _slugify(project_name)

    console.print()
    console.print("[yellow]⚠️  No project found in current directory[/yellow]")
    console.print(f"[dim]   {cwd}[/dim]")
    console.print()

    console.print("Where should I create this project?")
    console.print()

    # Format default path for display
    default_display = _shorten_path(default_path)
    cwd_display = _shorten_path(cwd / (project_name or "project"))

    console.print(f"  [cyan][1][/cyan] {default_display}  [dim](default)[/dim]")
    console.print(f"  [cyan][2][/cyan] {cwd_display}  [dim](current directory)[/dim]")
    console.print("  [cyan][3][/cyan] Choose different location...")
    console.print()

    choice = Prompt.ask("Choice", default="1", choices=["1", "2", "3"])

    match choice:
        case "1":
            path = default_path
        case "2":
            path = cwd / (project_name or "project")
        case "3":
            path_str = Prompt.ask("Enter path")
            path = Path(path_str).expanduser().resolve()
        case _:
            path = default_path

    # Check for collision
    if path.exists() and any(path.iterdir()):
        return _handle_collision(path, project_name)

    # Create and return
    console.print()
    console.print(f"[green]✓[/green] Creating project in: {_shorten_path(path)}")

    new_result = WorkspaceResult(
        path=path,
        source=ResolutionSource.EXPLICIT,
        confidence=1.0,
        project_name=project_name,
        exists=path.exists(),
    )
    return _finalize_workspace(new_result, create=True)


def _handle_collision(path: Path, project_name: str | None) -> Path:
    """Handle case where target directory already exists.

    Args:
        path: Target path that exists
        project_name: Name for new project

    Returns:
        Resolved path (existing or new)
    """
    console.print()
    console.print(f"[yellow]⚠️  {_shorten_path(path)} already exists[/yellow]")
    console.print()

    # Check if it looks like a Sunwell project
    is_sunwell_project = (path / ".sunwell").exists()

    if is_sunwell_project:
        console.print("  [cyan][1][/cyan] Open existing project")
    else:
        console.print("  [cyan][1][/cyan] Use existing directory")

    # Generate alternative name
    alt_name = _find_available_name(path)
    console.print(f"  [cyan][2][/cyan] Create {alt_name.name}/ instead")
    console.print("  [cyan][3][/cyan] Choose different name...")
    console.print("  [cyan][4][/cyan] Cancel")
    console.print()

    choice = Prompt.ask("Choice", default="1", choices=["1", "2", "3", "4"])

    match choice:
        case "1":
            console.print()
            console.print(f"[green]✓[/green] Using existing: {_shorten_path(path)}")
            return path
        case "2":
            alt_name.mkdir(parents=True, exist_ok=True)
            console.print()
            console.print(f"[green]✓[/green] Created: {_shorten_path(alt_name)}")
            return alt_name
        case "3":
            new_name = Prompt.ask("Enter new name")
            new_path = path.parent / new_name
            new_path.mkdir(parents=True, exist_ok=True)
            console.print()
            console.print(f"[green]✓[/green] Created: {_shorten_path(new_path)}")
            return new_path
        case "4":
            console.print("[dim]Cancelled[/dim]")
            sys.exit(0)
        case _:
            return path


def _find_available_name(path: Path) -> Path:
    """Find an available name by appending a number.

    Args:
        path: Original path that exists

    Returns:
        Path with -2, -3, etc. suffix that doesn't exist
    """
    base = path.name
    parent = path.parent

    for i in range(2, 100):
        candidate = parent / f"{base}-{i}"
        if not candidate.exists():
            return candidate

    # Fallback
    import time
    return parent / f"{base}-{int(time.time())}"


def _finalize_workspace(result: WorkspaceResult, create: bool = False) -> Path:
    """Finalize workspace resolution.

    Args:
        result: Workspace result to finalize
        create: Whether to create directory if missing

    Returns:
        The workspace path
    """
    if create:
        ensure_workspace_exists(result)
    return result.path


def _shorten_path(path: Path) -> str:
    """Shorten path for display by replacing home with ~.

    Args:
        path: Path to shorten

    Returns:
        Shortened path string
    """
    path_str = str(path)
    home = str(Path.home())

    if path_str.startswith(home):
        return "~" + path_str[len(home):]

    return path_str


def confirm_destructive_action(
    action: str,
    path: Path,
    default: bool = False,
) -> bool:
    """Confirm a destructive action on a workspace.

    Args:
        action: Description of the action
        path: Path being affected
        default: Default response if user just hits enter

    Returns:
        True if confirmed, False otherwise
    """
    console.print()
    console.print(f"[yellow]⚠️  {action}[/yellow]")
    console.print(f"[dim]   {_shorten_path(path)}[/dim]")
    console.print()

    return Confirm.ask("Continue?", default=default)
