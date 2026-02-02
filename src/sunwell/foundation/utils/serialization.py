"""Safe JSON/YAML serialization utilities.

RFC-138: Module Architecture Consolidation

Provides safe parsing and serialization with clear error messages.
Includes crash-tolerant file I/O with atomic writes.
YAML support requires pyyaml (optional dependency).
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

T = TypeVar("T")


def safe_json_loads(data: str) -> dict[str, Any] | list[Any]:
    """Parse JSON with clear error messages.

    Args:
        data: JSON string to parse

    Returns:
        Parsed dict or list

    Raises:
        ValueError: If JSON is invalid (with clear message)

    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}") from e


def safe_json_dumps(obj: dict[str, Any] | list[Any], **kwargs: Any) -> str:
    """Serialize to JSON with defaults.

    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to json.dumps

    Returns:
        JSON string

    Example:
        >>> safe_json_dumps({"key": "value"})
        '{"key": "value"}'
    """
    # Default to compact output unless indent specified
    if "indent" not in kwargs:
        kwargs["indent"] = None
    if "separators" not in kwargs:
        kwargs["separators"] = (",", ":")
    return json.dumps(obj, **kwargs)


def safe_yaml_loads(content: str) -> dict[str, Any]:
    """Load YAML from string with error handling.

    Args:
        content: YAML string content

    Returns:
        Parsed dict

    Raises:
        ImportError: If pyyaml is not installed
        ValueError: If YAML is invalid

    Example:
        >>> safe_yaml_loads("key: value\\nnumber: 42")
        {'key': 'value', 'number': 42}
    """
    if yaml is None:
        raise ImportError("pyyaml is required for YAML support. Install with: pip install pyyaml")

    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError(f"YAML must contain a dict, got {type(data).__name__}")
        return data
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e


def safe_yaml_load(path: Path) -> dict[str, Any]:
    """Load YAML file with error handling.

    Args:
        path: Path to YAML file

    Returns:
        Parsed dict

    Raises:
        ImportError: If pyyaml is not installed
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid

    Example:
        >>> safe_yaml_load(Path("config.yaml"))
        {'key': 'value'}
    """
    if yaml is None:
        raise ImportError("pyyaml is required for YAML support. Install with: pip install pyyaml")

    try:
        content = path.read_text(encoding="utf-8")
        return safe_yaml_loads(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e


def safe_yaml_dumps(obj: dict[str, Any], **kwargs: Any) -> str:
    """Serialize dict to YAML string.

    Args:
        obj: Dict to serialize
        **kwargs: Additional arguments to yaml.safe_dump

    Returns:
        YAML string

    Raises:
        ImportError: If pyyaml is not installed

    Example:
        >>> safe_yaml_dumps({"key": "value"})
        'key: value\\n'
    """
    if yaml is None:
        raise ImportError("pyyaml is required for YAML support. Install with: pip install pyyaml")

    # Default to block style unless specified
    if "default_flow_style" not in kwargs:
        kwargs["default_flow_style"] = False
    if "sort_keys" not in kwargs:
        kwargs["sort_keys"] = False

    try:
        return yaml.safe_dump(obj, **kwargs)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to serialize YAML: {e}") from e


def safe_yaml_dump(obj: dict[str, Any], path: Path) -> None:
    """Write YAML file with error handling.

    Args:
        obj: Dict to serialize
        path: Path to write YAML file

    Raises:
        ImportError: If pyyaml is not installed
        OSError: If file cannot be written

    Example:
        >>> safe_yaml_dump({"key": "value"}, Path("output.yaml"))
    """
    if yaml is None:
        raise ImportError("pyyaml is required for YAML support. Install with: pip install pyyaml")

    content = safe_yaml_dumps(obj)
    path.write_text(content, encoding="utf-8")


# =============================================================================
# Crash-Tolerant JSON File I/O
# =============================================================================


def safe_json_load(
    path: Path,
    default: T | None = None,
) -> dict[str, Any] | list[Any] | T | None:
    """Load JSON file with graceful error handling.

    Returns default value if file doesn't exist or is corrupted.
    Never raises exceptions - logs warnings instead.

    Args:
        path: Path to JSON file
        default: Value to return on error (default: None)

    Returns:
        Parsed JSON data, or default on any error

    Example:
        >>> data = safe_json_load(Path("config.json"), default={})
        >>> data = safe_json_load(Path("missing.json"), default={"version": 1})
    """
    if not path.exists():
        return default

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning("Corrupted JSON in %s: %s (using default)", path, e)
        return default
    except OSError as e:
        logger.warning("Failed to read %s: %s (using default)", path, e)
        return default


def safe_json_dump(
    obj: dict[str, Any] | list[Any],
    path: Path,
    *,
    indent: int = 2,
    atomic: bool = True,
) -> bool:
    """Write JSON file with crash tolerance.

    Uses atomic write (temp file + rename) to prevent corruption on crash.
    Creates parent directories if needed.

    Args:
        obj: Object to serialize
        path: Destination path
        indent: JSON indentation (default: 2)
        atomic: Use atomic write via temp file (default: True)

    Returns:
        True if successful, False on error

    Example:
        >>> success = safe_json_dump({"key": "value"}, Path("config.json"))
        >>> if not success:
        ...     print("Warning: failed to save config")
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(obj, indent=indent)

        if atomic:
            # Write to temp file in same directory, then rename (atomic on POSIX)
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=path.stem + "_",
                dir=path.parent,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, path)  # Atomic on POSIX
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        return True
    except OSError as e:
        logger.error("Failed to write %s: %s", path, e)
        return False
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize JSON for %s: %s", path, e)
        return False


def safe_jsonl_append(
    record: dict[str, Any],
    path: Path,
) -> bool:
    """Append a single record to JSONL file.

    JSONL (JSON Lines) is naturally crash-tolerant since each line is
    independent. A crash mid-write only corrupts the last line.

    Args:
        record: Dict to append as JSON line
        path: Path to JSONL file

    Returns:
        True if successful, False on error

    Example:
        >>> safe_jsonl_append({"event": "start"}, Path("events.jsonl"))
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except OSError as e:
        logger.error("Failed to append to %s: %s", path, e)
        return False
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize record for %s: %s", path, e)
        return False


def safe_jsonl_load(
    path: Path,
) -> list[dict[str, Any]]:
    """Load all records from JSONL file.

    Skips corrupted lines gracefully - partial data is better than none.

    Args:
        path: Path to JSONL file

    Returns:
        List of parsed records (empty list if file missing or all corrupted)

    Example:
        >>> records = safe_jsonl_load(Path("events.jsonl"))
    """
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.debug("Skipping corrupted line %d in %s", lineno, path)
    except OSError as e:
        logger.warning("Failed to read %s: %s", path, e)

    return records
