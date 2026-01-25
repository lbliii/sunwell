"""Storage for User Environment Model (RFC-104).

Persists the environment model to ~/.sunwell/environment.json.
Provides thread-safe loading and saving with backup support.
"""

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path

from sunwell.knowledge.environment.model import UserEnvironment

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

ENVIRONMENT_DIR = Path.home() / ".sunwell"
"""Base directory for Sunwell global configuration."""

ENVIRONMENT_FILE = ENVIRONMENT_DIR / "environment.json"
"""Path to the environment model file."""

BACKUP_SUFFIX = ".backup"
"""Suffix for backup files."""


# =============================================================================
# Thread-safe Storage
# =============================================================================

_storage_lock = threading.Lock()
"""Lock for thread-safe file operations."""

_cached_env: UserEnvironment | None = None
"""Cached environment to avoid repeated disk reads."""

_cache_mtime: float = 0
"""Modification time of cached environment file."""


def load_environment() -> UserEnvironment:
    """Load the user environment from disk.

    Returns cached version if file hasn't changed. Creates a new
    empty environment if the file doesn't exist.

    Returns:
        The loaded UserEnvironment.
    """
    global _cached_env, _cache_mtime

    with _storage_lock:
        # Check if file exists and get mtime
        current_mtime = ENVIRONMENT_FILE.stat().st_mtime if ENVIRONMENT_FILE.exists() else 0

        # Return cache if still valid
        if _cached_env is not None and current_mtime == _cache_mtime:
            return _cached_env

        # Load from disk or create new
        if ENVIRONMENT_FILE.exists():
            try:
                data = json.loads(ENVIRONMENT_FILE.read_text(encoding="utf-8"))
                _cached_env = UserEnvironment.from_dict(data)
                _cache_mtime = current_mtime
                logger.debug("Loaded environment from %s", ENVIRONMENT_FILE)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Failed to load environment: %s. Creating new.", e)
                _cached_env = UserEnvironment()
                _cache_mtime = 0
        else:
            _cached_env = UserEnvironment()
            _cache_mtime = 0

        return _cached_env


def save_environment(env: UserEnvironment) -> Path:
    """Save the user environment to disk.

    Creates a backup of the existing file before overwriting.
    Ensures the directory exists.

    Args:
        env: The UserEnvironment to save.

    Returns:
        Path to the saved file.
    """
    global _cached_env, _cache_mtime

    with _storage_lock:
        # Ensure directory exists
        ENVIRONMENT_DIR.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if ENVIRONMENT_FILE.exists():
            backup_path = ENVIRONMENT_FILE.with_suffix(f".json{BACKUP_SUFFIX}")
            try:
                shutil.copy2(ENVIRONMENT_FILE, backup_path)
            except OSError as e:
                logger.warning("Failed to create backup: %s", e)

        # Update timestamp
        env.updated_at = datetime.now()

        # Write to disk
        data = env.to_dict()
        ENVIRONMENT_FILE.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

        # Update cache
        _cached_env = env
        _cache_mtime = ENVIRONMENT_FILE.stat().st_mtime

        logger.debug("Saved environment to %s", ENVIRONMENT_FILE)
        return ENVIRONMENT_FILE


def reset_environment() -> UserEnvironment:
    """Reset the environment to a fresh state.

    Creates a backup of the existing environment before reset.

    Returns:
        The new empty UserEnvironment.
    """
    global _cached_env, _cache_mtime

    # Backup existing (outside lock to avoid deadlock with save_environment)
    if ENVIRONMENT_FILE.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = ENVIRONMENT_DIR / f"environment_{timestamp}.json.backup"
        try:
            shutil.copy2(ENVIRONMENT_FILE, backup_path)
            logger.info("Backed up environment to %s", backup_path)
        except OSError as e:
            logger.warning("Failed to backup before reset: %s", e)

    # Clear cache
    with _storage_lock:
        _cached_env = None
        _cache_mtime = 0

    # Create and save new environment
    new_env = UserEnvironment()
    save_environment(new_env)
    return new_env


def clear_cache() -> None:
    """Clear the in-memory cache.

    Forces the next load_environment() to read from disk.
    """
    global _cached_env, _cache_mtime

    with _storage_lock:
        _cached_env = None
        _cache_mtime = 0


# =============================================================================
# Environment Utilities
# =============================================================================


def get_environment_path() -> Path:
    """Get the path to the environment file.

    Returns:
        Path to environment.json.
    """
    return ENVIRONMENT_FILE


def environment_exists() -> bool:
    """Check if an environment file exists.

    Returns:
        True if the environment file exists.
    """
    return ENVIRONMENT_FILE.exists()


def get_environment_age() -> float | None:
    """Get the age of the environment in seconds.

    Returns:
        Age in seconds, or None if no environment exists.
    """
    if not ENVIRONMENT_FILE.exists():
        return None

    mtime = datetime.fromtimestamp(ENVIRONMENT_FILE.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds()


def export_environment(output_path: Path) -> Path:
    """Export the environment to a specified path.

    Args:
        output_path: Where to export the environment.

    Returns:
        Path to the exported file.
    """
    env = load_environment()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(env.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    return output_path


def import_environment(input_path: Path, merge: bool = False) -> UserEnvironment:
    """Import an environment from a file.

    Args:
        input_path: Path to the environment file to import.
        merge: If True, merge with existing. If False, replace.

    Returns:
        The imported/merged UserEnvironment.
    """
    data = json.loads(input_path.read_text(encoding="utf-8"))
    imported = UserEnvironment.from_dict(data)

    if merge:
        existing = load_environment()
        # Merge projects (imported overwrites existing by path)
        # add_project handles update-or-insert with O(1) index lookup
        for project in imported.projects:
            existing.add_project(project)

        # Merge roots (avoid duplicates)
        existing_root_paths = {r.path for r in existing.roots}
        for root in imported.roots:
            if root.path not in existing_root_paths:
                existing.roots.append(root)

        # Merge references (imported takes precedence)
        existing.reference_projects.update(imported.reference_projects)

        save_environment(existing)
        return existing
    else:
        save_environment(imported)
        return imported
