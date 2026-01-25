"""Open command — Launch Sunwell Studio with project (RFC-086).

Enables `sunwell .` and `sunwell open .` patterns for quick project access.
Auto-detects appropriate lens based on project structure.
"""

import subprocess
import sys
from pathlib import Path

import click

from sunwell.interface.generative.surface.fallback import get_domain_for_project
from sunwell.interface.generative.surface.lens_detection import get_lens_for_project, get_mode_for_domain


def launch_studio(
    project: str,
    lens: str,
    mode: str,
    plan_file: str | None = None,
) -> None:
    """Launch Sunwell Studio (Tauri app).

    Looks for binary in this order:
    1. Debug build (dev): studio/src-tauri/target/debug/sunwell-studio
    2. Release build: studio/src-tauri/target/release/sunwell-studio
    3. Installed app (macOS): /Applications/Sunwell.app
    4. Installed binary (Linux/Windows): sunwell-studio in PATH

    Args:
        project: Absolute path to project directory
        lens: Lens filename to use
        mode: Workspace mode (writer, code, planning)
        plan_file: Optional path to plan JSON file (RFC-090)
    """
    studio_dir = Path(__file__).parent.parent.parent.parent / "studio"
    args = ["--project", project, "--lens", lens, "--mode", mode]

    # RFC-090: Pass plan file if provided
    if plan_file:
        args.extend(["--plan", plan_file])

    # Try debug build first (most common in dev)
    debug_binary = studio_dir / "src-tauri" / "target" / "debug" / "sunwell-studio"
    if debug_binary.exists():
        subprocess.Popen([str(debug_binary), *args])
        return

    # Try release build
    release_binary = studio_dir / "src-tauri" / "target" / "release" / "sunwell-studio"
    if release_binary.exists():
        subprocess.Popen([str(release_binary), *args])
        return

    # Try installed app (platform-specific)
    if sys.platform == "darwin":
        mac_app = Path("/Applications/Sunwell.app/Contents/MacOS/Sunwell")
        if mac_app.exists():
            subprocess.Popen([str(mac_app), *args])
            return
    elif sys.platform == "win32":
        win_app = Path("C:\\Program Files\\Sunwell\\Sunwell.exe")
        if win_app.exists():
            subprocess.Popen([str(win_app), *args])
            return

    # Fallback: try to find in PATH
    import shutil

    if binary := shutil.which("sunwell-studio"):
        subprocess.Popen([binary, *args])
        return

    # Nothing found - tell user to build first
    click.echo("Error: Sunwell Studio not found.", err=True)
    click.echo("", err=True)
    click.echo("Build it first:", err=True)
    click.echo("  cd studio && cargo tauri build --debug", err=True)
    click.echo("", err=True)
    click.echo("Or run the dev server manually:", err=True)
    click.echo("  make studio-dev", err=True)
    sys.exit(1)


@click.command(name="open")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--lens", "-l", help="Override lens selection")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["auto", "writer", "code", "planning"]),
    default="auto",
    help="Workspace mode",
)
@click.option("--dry-run", is_flag=True, help="Show what would be launched without launching")
def open_project(path: str, lens: str | None, mode: str, dry_run: bool) -> None:
    """Open a project in Sunwell Studio.

    \b
    Examples:
        sunwell .                        # Open current directory
        sunwell open docs/               # Open docs folder
        sunwell open . --lens tech-writer
        sunwell open . --mode writer
    """
    project_path = Path(path).resolve()

    # Auto-detect mode from domain if not specified
    domain = get_domain_for_project(project_path)
    if mode == "auto":
        mode = get_mode_for_domain(domain)

    # Auto-detect lens if not specified
    if not lens:
        lens = get_lens_for_project(project_path)

    if dry_run:
        click.echo(f"Project: {project_path}")
        click.echo(f"Domain:  {domain}")
        click.echo(f"Mode:    {mode}")
        click.echo(f"Lens:    {lens}")
        return

    click.echo(f"Opening {project_path.name} in {mode} mode with {lens}...")

    launch_studio(
        project=str(project_path),
        lens=lens,
        mode=mode,
    )
