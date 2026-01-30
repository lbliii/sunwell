"""Loader for user-defined hooks from TOML configuration.

Reads hooks from `.sunwell/hooks.toml` in the workspace.
"""

import logging
import shutil
import os
from pathlib import Path

from sunwell.interface.cli.hooks.schema import HookConfig, UserHooksConfig

logger = logging.getLogger(__name__)

# Default hooks file location
HOOKS_FILENAME = "hooks.toml"
CONFIG_DIR = ".sunwell"


def load_user_hooks(workspace: Path) -> UserHooksConfig:
    """Load user hooks from workspace configuration.
    
    Looks for `.sunwell/hooks.toml` in the workspace.
    
    Args:
        workspace: Workspace root path
        
    Returns:
        UserHooksConfig (empty if no config found)
    """
    hooks_path = workspace / CONFIG_DIR / HOOKS_FILENAME
    
    if not hooks_path.exists():
        logger.debug("No hooks.toml found at %s", hooks_path)
        return UserHooksConfig()
    
    try:
        return _load_hooks_file(hooks_path)
    except Exception as e:
        logger.warning("Failed to load hooks.toml: %s", e)
        return UserHooksConfig()


def _load_hooks_file(path: Path) -> UserHooksConfig:
    """Load and parse a hooks TOML file.
    
    Args:
        path: Path to hooks.toml
        
    Returns:
        Parsed configuration
        
    Raises:
        ValueError: If file is invalid
    """
    import tomllib
    
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    config = UserHooksConfig.from_dict(data)
    
    # Validate hooks
    valid_hooks: list[HookConfig] = []
    for hook in config.hooks:
        if _validate_hook(hook):
            valid_hooks.append(hook)
        else:
            logger.warning("Hook '%s' failed validation, skipping", hook.name)
    
    return UserHooksConfig(
        hooks=tuple(valid_hooks),
        version=config.version,
    )


def _validate_hook(hook: HookConfig) -> bool:
    """Validate a hook's requirements.
    
    Checks:
    - Required binaries are in PATH
    - Required environment variables are set
    
    Args:
        hook: Hook configuration to validate
        
    Returns:
        True if all requirements are met
    """
    # Check required binaries
    for bin_name in hook.requires:
        if shutil.which(bin_name) is None:
            logger.warning(
                "Hook '%s' requires '%s' which is not in PATH",
                hook.name,
                bin_name,
            )
            return False
    
    # Check required environment variables
    for env_var in hook.env:
        if not os.environ.get(env_var):
            logger.warning(
                "Hook '%s' requires env var '%s' which is not set",
                hook.name,
                env_var,
            )
            return False
    
    return True


def create_example_hooks_file(workspace: Path) -> Path:
    """Create an example hooks.toml file.
    
    Args:
        workspace: Workspace root path
        
    Returns:
        Path to created file
    """
    config_dir = workspace / CONFIG_DIR
    config_dir.mkdir(exist_ok=True)
    
    hooks_path = config_dir / HOOKS_FILENAME
    
    example = '''# Sunwell User Hooks Configuration
# See: https://sunwell.dev/docs/hooks

version = 1

# Example: Auto-commit on session end
# [[hooks]]
# name = "auto-commit"
# on = ["session:end"]
# run = "git add -A && git commit -m 'sunwell: ${SUNWELL_SESSION_SUMMARY}'"
# requires = ["git"]
# when = "success"

# Example: Desktop notification on task complete
# [[hooks]]
# name = "notify-complete"
# on = ["task:complete"]
# run = "terminal-notifier -title 'Sunwell' -message 'Task done: ${TASK_DESCRIPTION}'"
# requires = ["terminal-notifier"]

# Example: Slack webhook on gate failure
# [[hooks]]
# name = "slack-alert"
# on = ["gate:fail"]
# run = "curl -X POST ${SLACK_WEBHOOK} -d '{\\"text\\": \\"Gate ${GATE_NAME} failed\\"}'"
# env = ["SLACK_WEBHOOK"]
# when = "failure"

# Example: Run tests after file changes approved
# [[hooks]]
# name = "auto-test"
# on = ["file:change_approved"]
# run = "pytest ${FILE_PATH} -x --tb=short"
# requires = ["pytest"]
# background = true
# timeout = 120
'''
    
    hooks_path.write_text(example)
    logger.info("Created example hooks.toml at %s", hooks_path)
    
    return hooks_path
