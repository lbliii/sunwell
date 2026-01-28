"""Logging configuration for Sunwell.

Provides centralized logging setup with sensible defaults:
- Default: WARNING level (quiet operation)
- --debug flag: DEBUG level with full context
- SUNWELL_DEBUG=true or SUNWELL_LOG_LEVEL=DEBUG env vars: Override for CI/scripting
- Config file: debug: true in .sunwell/config.yaml (persistent)

Usage:
    from sunwell.foundation.logging import configure_logging
    configure_logging(debug=args.debug)

Priority for level resolution (highest to lowest):
    1. Explicit `level` parameter (programmatic override)
    2. SUNWELL_LOG_LEVEL env var (any level: DEBUG, INFO, WARNING, etc.)
    3. SUNWELL_DEBUG=true env var (simple boolean)
    4. `debug=True` parameter (--debug flag)
    5. Config file: debug: true
    6. WARNING (default)
"""

import logging
import os
import sys
from pathlib import Path

# Format includes module path for tracing issues
_DEBUG_FORMAT = "%(asctime)s %(name)s [%(levelname)s] %(message)s"
_DEFAULT_FORMAT = "%(name)s: %(message)s"

# Noisy libraries we want to quiet even in debug mode
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "hpack",
    "charset_normalizer",
    "markdown_it",  # Spams block parser state on every render
)

# Cache config debug setting to avoid re-reading file
_config_debug_checked = False
_config_debug_value = False


def _check_config_debug() -> bool:
    """Check if debug is enabled in config file.
    
    This is a lightweight check that doesn't import the full config system
    to avoid circular imports. Only reads the debug setting from YAML.
    """
    global _config_debug_checked, _config_debug_value
    
    if _config_debug_checked:
        return _config_debug_value
    
    _config_debug_checked = True
    
    # Check config files in priority order
    config_paths = [
        Path(".sunwell/config.yaml"),
        Path.home() / ".sunwell" / "config.yaml",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                # Simple YAML parsing for just the debug key
                # Avoids importing yaml to keep this lightweight
                content = config_path.read_text()
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("debug:"):
                        value = stripped.split(":", 1)[1].strip().lower()
                        _config_debug_value = value in ("true", "yes", "1")
                        return _config_debug_value
            except Exception:
                pass
    
    return False


def configure_logging(
    *,
    debug: bool = False,
    level: int | str | None = None,
    stream: object = None,
) -> None:
    """Configure logging for Sunwell CLI.

    Call this early in the CLI entrypoint before any other imports
    that might trigger logging.

    Args:
        debug: Enable DEBUG level with detailed format
        level: Override log level (int or string like "DEBUG", "INFO")
               Also reads SUNWELL_LOG_LEVEL env var
        stream: Output stream (default: stderr)

    Priority for level resolution (highest to lowest):
        1. Explicit `level` parameter (programmatic override)
        2. SUNWELL_LOG_LEVEL env var (any level: DEBUG, INFO, WARNING, etc.)
        3. SUNWELL_DEBUG=true env var (simple boolean)
        4. `debug=True` parameter (--debug flag)
        5. Config file: debug: true
        6. WARNING (default)
    """
    # Resolve level with priority
    resolved_level: int
    if level is not None:
        resolved_level = _parse_level(level)
    elif env_level := os.environ.get("SUNWELL_LOG_LEVEL"):
        resolved_level = _parse_level(env_level)
    elif os.environ.get("SUNWELL_DEBUG", "").lower() in ("true", "1", "yes"):
        resolved_level = logging.DEBUG
    elif debug:
        resolved_level = logging.DEBUG
    elif _check_config_debug():
        resolved_level = logging.DEBUG
    else:
        resolved_level = logging.WARNING

    # Choose format based on verbosity
    log_format = _DEBUG_FORMAT if resolved_level <= logging.DEBUG else _DEFAULT_FORMAT

    # Configure root logger
    logging.basicConfig(
        level=resolved_level,
        format=log_format,
        stream=stream or sys.stderr,
        force=True,  # Override any existing config
    )

    # Quiet noisy third-party loggers
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Log that we're configured (only visible in debug mode)
    logger = logging.getLogger(__name__)
    logger.debug(
        "Logging configured: level=%s, debug=%s, from_config=%s",
        logging.getLevelName(resolved_level),
        debug,
        _config_debug_value,
    )


def _parse_level(level: int | str) -> int:
    """Parse log level from int or string."""
    if isinstance(level, int):
        return level
    # Handle string levels like "DEBUG", "INFO", etc.
    numeric = getattr(logging, level.upper(), None)
    if numeric is not None:
        return numeric
    # Try parsing as int string
    try:
        return int(level)
    except ValueError:
        return logging.WARNING
