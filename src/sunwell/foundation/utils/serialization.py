"""Safe JSON/YAML serialization utilities.

RFC-138: Module Architecture Consolidation

Provides safe parsing and serialization with clear error messages.
YAML support requires pyyaml (optional dependency).
"""

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


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
