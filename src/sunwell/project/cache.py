"""Project Analysis Cache (RFC-079).

Cache project analysis results for fast re-open with TTL and file hash invalidation.
"""

import contextlib
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sunwell.project.intent_types import ProjectAnalysis

# Cache configuration
CACHE_VERSION = 1
CACHE_TTL_HOURS = 1

# Key files that trigger re-analysis when changed
KEY_FILES = (
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "README.md",
    "README.rst",
    "README",
    "mkdocs.yml",
    "mkdocs.yaml",
)


def get_cache_path(project_path: Path) -> Path:
    """Get the cache file path for a project."""
    return project_path / ".sunwell" / "project.json"


def hash_file(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except OSError:
        return ""


def compute_file_hashes(project_path: Path) -> dict[str, str | None]:
    """Compute hashes for all key files."""
    hashes: dict[str, str | None] = {}

    for filename in KEY_FILES:
        file_path = project_path / filename
        if file_path.exists():
            hashes[filename] = hash_file(file_path)
        else:
            hashes[filename] = None

    return hashes


def is_cache_valid(cache_data: dict[str, Any], project_path: Path) -> bool:
    """Check if cached analysis is still valid.

    Invalidation rules:
    - Version mismatch
    - TTL expired (default: 1 hour)
    - Key file hash changed
    - Key file was deleted

    Args:
        cache_data: Loaded cache data.
        project_path: Project root path.

    Returns:
        True if cache is valid, False if re-analysis needed.
    """
    # Check version
    if cache_data.get("version") != CACHE_VERSION:
        return False

    # Check TTL
    try:
        analyzed_at = datetime.fromisoformat(cache_data["analyzed_at"])
        if datetime.now() - analyzed_at > timedelta(hours=CACHE_TTL_HOURS):
            return False
    except (KeyError, ValueError):
        return False

    # Check key file hashes
    stored_hashes = cache_data.get("file_hashes", {})
    current_hashes = compute_file_hashes(project_path)

    for filename, expected_hash in stored_hashes.items():
        current_hash = current_hashes.get(filename)

        # File existed before, check if changed or deleted
        if expected_hash is not None:
            if current_hash != expected_hash:
                return False  # File changed or deleted
        # File didn't exist before but exists now
        elif current_hash is not None:
            return False  # New key file appeared

    return True


def load_cached_analysis(project_path: Path) -> ProjectAnalysis | None:
    """Load cached analysis if valid.

    Args:
        project_path: Project root path.

    Returns:
        ProjectAnalysis if cache is valid, None otherwise.
    """
    cache_path = get_cache_path(project_path)

    if not cache_path.exists():
        return None

    try:
        cache_data = json.loads(cache_path.read_text(encoding="utf-8"))

        if not is_cache_valid(cache_data, project_path):
            return None

        return ProjectAnalysis.from_cache(cache_data)

    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return None


def save_analysis_cache(analysis: ProjectAnalysis) -> None:
    """Save analysis to cache.

    Args:
        analysis: ProjectAnalysis to cache.
    """
    cache_path = get_cache_path(analysis.path)

    # Ensure .sunwell directory exists
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Build cache data
    cache_data = analysis.to_cache_dict()

    # Add file hashes
    cache_data["file_hashes"] = compute_file_hashes(analysis.path)

    with contextlib.suppress(OSError):
        cache_path.write_text(
            json.dumps(cache_data, indent=2),
            encoding="utf-8",
        )


def invalidate_cache(project_path: Path) -> bool:
    """Force invalidate project cache.

    Args:
        project_path: Project root path.

    Returns:
        True if cache was removed, False if no cache existed.
    """
    cache_path = get_cache_path(project_path)

    if cache_path.exists():
        try:
            cache_path.unlink()
            return True
        except OSError:
            pass

    return False
