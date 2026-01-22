"""Import command — Bring existing projects into Sunwell workspace (RFC-043 addendum).

Allows users to import existing projects into the default Sunwell workspace,
either by copying or symlinking.
"""


import shutil
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from sunwell.workspace import default_workspace_root

console = Console()


@click.command()
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--name",
    "-n",
    help="Name for imported project (default: source directory name)",
)
@click.option(
    "--link",
    "-l",
    is_flag=True,
    help="Create symlink instead of copying",
)
@click.option(
    "--target",
    "-t",
    type=click.Path(),
    help="Target directory (default: ~/Sunwell/projects/)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts",
)
def import_project(
    source: str,
    name: str | None,
    link: bool,
    target: str | None,
    yes: bool,
) -> None:
    """Import an existing project into Sunwell workspace.

    This command helps migrate existing projects to the default Sunwell
    workspace location for unified project management.

    \b
    Examples:

        # Import by copying
        sunwell import ~/old-projects/myapp

        # Import with symlink (no disk space used)
        sunwell import ~/work/api-project --link

        # Import with custom name
        sunwell import ./legacy-code --name modern-app

        # Non-interactive (for scripts)
        sunwell import ~/projects/app --yes
    """
    source_path = Path(source).resolve()

    # Determine project name
    project_name = name or source_path.name

    # Determine target directory
    if target:
        target_dir = Path(target).resolve()
    else:
        target_dir = default_workspace_root()

    target_path = target_dir / project_name

    # Show what we're going to do
    console.print()
    console.print("[bold]Import Project[/bold]")
    console.print()
    console.print(f"  Source: {_shorten_path(source_path)}")
    console.print(f"  Target: {_shorten_path(target_path)}")
    console.print(f"  Method: {'symlink' if link else 'copy'}")
    console.print()

    # Check for conflicts
    if target_path.exists():
        if target_path.is_symlink():
            console.print(
                f"[yellow]⚠️  Target already exists as symlink[/yellow]"
            )
            if not yes:
                if not Confirm.ask("Replace existing symlink?", default=False):
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)
            target_path.unlink()
        elif target_path.is_dir():
            console.print(
                f"[yellow]⚠️  Target directory already exists[/yellow]"
            )
            if not yes:
                choice = Prompt.ask(
                    "What would you like to do?",
                    choices=["rename", "replace", "cancel"],
                    default="cancel",
                )
                if choice == "cancel":
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)
                elif choice == "rename":
                    new_name = Prompt.ask(
                        "New name",
                        default=f"{project_name}-imported",
                    )
                    target_path = target_dir / new_name
                elif choice == "replace":
                    console.print("[dim]Removing existing directory...[/dim]")
                    shutil.rmtree(target_path)
            else:
                console.print("[red]Target exists. Use --name to specify different name.[/red]")
                sys.exit(1)

    # Confirm
    if not yes:
        if not Confirm.ask("Proceed with import?", default=True):
            console.print("[dim]Cancelled[/dim]")
            sys.exit(0)

    # Ensure target parent exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Perform import
    try:
        if link:
            target_path.symlink_to(source_path)
            console.print(f"[green]✓[/green] Created symlink: {_shorten_path(target_path)}")
        else:
            console.print("[dim]Copying files...[/dim]")
            shutil.copytree(source_path, target_path, dirs_exist_ok=False)
            console.print(f"[green]✓[/green] Copied to: {_shorten_path(target_path)}")

        # Initialize .sunwell if not present
        sunwell_dir = target_path / ".sunwell"
        if not sunwell_dir.exists():
            sunwell_dir.mkdir()
            console.print("[dim]   Initialized .sunwell/ directory[/dim]")

        console.print()
        console.print("[green]Import complete![/green]")
        console.print()
        console.print("You can now work on this project with:")
        console.print(f"  [cyan]cd {_shorten_path(target_path)}[/cyan]")
        console.print(f"  [cyan]sunwell chat[/cyan]")

    except PermissionError as e:
        console.print(f"[red]Permission denied: {e}[/red]")
        sys.exit(1)
    except OSError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _shorten_path(path: Path) -> str:
    """Shorten path for display by replacing home with ~."""
    path_str = str(path)
    home = str(Path.home())

    if path_str.startswith(home):
        return "~" + path_str[len(home):]

    return path_str
