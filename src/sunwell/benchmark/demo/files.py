"""File-based storage for demo outputs (RFC-095).

Saves generated code to actual files to avoid JSON escaping/corruption issues.
Files are stored in .sunwell/demo/ and served via the API.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DemoFiles:
    """Paths to saved demo files."""

    single_shot: Path
    sunwell: Path
    run_id: str


def get_demo_dir() -> Path:
    """Get the demo output directory, creating if needed."""
    demo_dir = Path.cwd() / ".sunwell" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    return demo_dir


def save_demo_code(
    run_id: str,
    single_shot_code: str,
    sunwell_code: str,
) -> DemoFiles:
    """Save demo code to files.

    Args:
        run_id: Unique identifier for this demo run.
        single_shot_code: Code from single-shot execution.
        sunwell_code: Code from Sunwell execution.

    Returns:
        DemoFiles with paths to the saved files.
    """
    demo_dir = get_demo_dir()

    # Create run-specific directory
    run_dir = demo_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    single_shot_path = run_dir / "single_shot.py"
    sunwell_path = run_dir / "sunwell.py"

    # Write raw code (no escaping needed)
    single_shot_path.write_text(single_shot_code, encoding="utf-8")
    sunwell_path.write_text(sunwell_code, encoding="utf-8")

    return DemoFiles(
        single_shot=single_shot_path,
        sunwell=sunwell_path,
        run_id=run_id,
    )


def load_demo_code(run_id: str) -> tuple[str, str] | None:
    """Load demo code from files.

    Args:
        run_id: The demo run identifier.

    Returns:
        Tuple of (single_shot_code, sunwell_code) or None if not found.
    """
    demo_dir = get_demo_dir()
    run_dir = demo_dir / run_id

    single_shot_path = run_dir / "single_shot.py"
    sunwell_path = run_dir / "sunwell.py"

    if not single_shot_path.exists() or not sunwell_path.exists():
        return None

    return (
        single_shot_path.read_text(encoding="utf-8"),
        sunwell_path.read_text(encoding="utf-8"),
    )


def cleanup_old_demos(keep_count: int = 10) -> None:
    """Clean up old demo files, keeping the most recent ones.

    Args:
        keep_count: Number of recent demo runs to keep.
    """
    demo_dir = get_demo_dir()

    # Get all run directories sorted by modification time
    run_dirs = sorted(
        [d for d in demo_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    # Remove old directories
    for old_dir in run_dirs[keep_count:]:
        for file in old_dir.iterdir():
            file.unlink()
        old_dir.rmdir()
