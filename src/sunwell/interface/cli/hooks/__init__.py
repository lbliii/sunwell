"""User-configurable hooks for CLI.

Loads hooks from `.sunwell/hooks.toml` and executes shell commands
on agent events.

Example hooks.toml:
    [[hooks]]
    name = "auto-commit"
    on = ["session:end"]
    run = "git add -A && git commit -m '${SUNWELL_SESSION_SUMMARY}'"
    requires = ["git"]
    
    [[hooks]]
    name = "notify-complete"
    on = ["task:complete"]
    run = "terminal-notifier -title 'Sunwell' -message 'Task done: ${TASK_DESCRIPTION}'"
    requires = ["terminal-notifier"]
"""

from sunwell.interface.cli.hooks.executor import ShellHookExecutor
from sunwell.interface.cli.hooks.integration import (
    get_registered_hook_count,
    list_registered_hooks,
    register_user_hooks,
    unregister_user_hooks,
)
from sunwell.interface.cli.hooks.loader import create_example_hooks_file, load_user_hooks
from sunwell.interface.cli.hooks.schema import HookConfig, HookTriggerCondition, UserHooksConfig

__all__ = [
    # Schema
    "HookConfig",
    "HookTriggerCondition",
    "UserHooksConfig",
    # Loader
    "load_user_hooks",
    "create_example_hooks_file",
    # Executor
    "ShellHookExecutor",
    # Integration
    "register_user_hooks",
    "unregister_user_hooks",
    "get_registered_hook_count",
    "list_registered_hooks",
]
