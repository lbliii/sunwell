"""Schema for user-configurable hooks.

Defines the structure of `.sunwell/hooks.toml` configuration.

Example:
    [[hooks]]
    name = "auto-commit"
    on = ["session:end"]
    run = "git add -A && git commit -m '${SUNWELL_SESSION_SUMMARY}'"
    requires = ["git"]
    when = "success"  # only run on success
    
    [[hooks]]
    name = "notify-slack"
    on = ["task:complete", "gate:fail"]
    run = "curl -X POST ${SLACK_WEBHOOK} -d '{\"text\": \"${EVENT_TYPE}: ${EVENT_MESSAGE}\"}'"
    env = ["SLACK_WEBHOOK"]
"""

from dataclasses import dataclass, field
from enum import Enum


class HookTriggerCondition(Enum):
    """When to trigger a hook."""
    
    ALWAYS = "always"
    """Always run (default)."""
    
    SUCCESS = "success"
    """Only run on success."""
    
    FAILURE = "failure"
    """Only run on failure."""


@dataclass(frozen=True, slots=True)
class HookConfig:
    """Configuration for a single user hook.
    
    Attributes:
        name: Human-readable name for logging
        on: List of event names to subscribe to (e.g., "session:end", "task:complete")
        run: Shell command to execute (supports ${VAR} interpolation)
        requires: Required binaries that must be in PATH
        env: Required environment variables
        when: Condition for running (always/success/failure)
        timeout: Command timeout in seconds (default 30)
        background: Run in background without waiting (default False)
        cwd: Working directory for command (default: workspace)
    """
    
    name: str
    """Hook name for logging."""
    
    on: tuple[str, ...]
    """Events to subscribe to."""
    
    run: str
    """Shell command to execute."""
    
    requires: tuple[str, ...] = ()
    """Required binaries (e.g., 'git', 'curl')."""
    
    env: tuple[str, ...] = ()
    """Required environment variables."""
    
    when: HookTriggerCondition = HookTriggerCondition.ALWAYS
    """Trigger condition."""
    
    timeout: int = 30
    """Command timeout in seconds."""
    
    background: bool = False
    """Run in background without waiting."""
    
    cwd: str | None = None
    """Working directory (None = workspace)."""

    @classmethod
    def from_dict(cls, data: dict) -> "HookConfig":
        """Create from dictionary (TOML table).
        
        Args:
            data: Dictionary from TOML parsing
            
        Returns:
            HookConfig instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Required fields
        name = data.get("name")
        if not name:
            raise ValueError("Hook missing required 'name' field")
        
        on = data.get("on")
        if not on:
            raise ValueError(f"Hook '{name}' missing required 'on' field")
        if isinstance(on, str):
            on = (on,)
        else:
            on = tuple(on)
        
        run = data.get("run")
        if not run:
            raise ValueError(f"Hook '{name}' missing required 'run' field")
        
        # Optional fields
        requires = data.get("requires", ())
        if isinstance(requires, str):
            requires = (requires,)
        else:
            requires = tuple(requires)
        
        env = data.get("env", ())
        if isinstance(env, str):
            env = (env,)
        else:
            env = tuple(env)
        
        when_str = data.get("when", "always").lower()
        try:
            when = HookTriggerCondition(when_str)
        except ValueError:
            raise ValueError(
                f"Hook '{name}' has invalid 'when' value: {when_str}. "
                f"Must be one of: always, success, failure"
            )
        
        timeout = data.get("timeout", 30)
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError(f"Hook '{name}' has invalid 'timeout': {timeout}")
        
        background = data.get("background", False)
        cwd = data.get("cwd")
        
        return cls(
            name=name,
            on=on,
            run=run,
            requires=requires,
            env=env,
            when=when,
            timeout=timeout,
            background=background,
            cwd=cwd,
        )


@dataclass(frozen=True, slots=True)
class UserHooksConfig:
    """Root configuration for user hooks.
    
    Loaded from `.sunwell/hooks.toml`.
    
    Attributes:
        hooks: Tuple of hook configurations
        version: Config version (for future compatibility)
    """
    
    hooks: tuple[HookConfig, ...] = ()
    """All configured hooks."""
    
    version: int = 1
    """Config version."""

    @classmethod
    def from_dict(cls, data: dict) -> "UserHooksConfig":
        """Create from dictionary (TOML root).
        
        Args:
            data: Dictionary from TOML parsing
            
        Returns:
            UserHooksConfig instance
        """
        version = data.get("version", 1)
        
        hooks_data = data.get("hooks", [])
        hooks = tuple(HookConfig.from_dict(h) for h in hooks_data)
        
        return cls(hooks=hooks, version=version)
    
    def get_hooks_for_event(self, event_name: str) -> tuple[HookConfig, ...]:
        """Get hooks that subscribe to an event.
        
        Args:
            event_name: Event name (e.g., "session:end")
            
        Returns:
            Tuple of matching hooks
        """
        return tuple(h for h in self.hooks if event_name in h.on)


# Variable interpolation patterns
# These are replaced in shell commands before execution
INTERPOLATION_VARS = {
    # Session variables
    "SUNWELL_SESSION_ID": "Current session ID",
    "SUNWELL_SESSION_SUMMARY": "Human-readable session summary",
    "SUNWELL_WORKSPACE": "Workspace path",
    
    # Task variables
    "TASK_ID": "Current task ID",
    "TASK_DESCRIPTION": "Task description",
    "TASK_SUCCESS": "true/false",
    "TASK_DURATION_MS": "Duration in milliseconds",
    
    # Tool variables
    "TOOL_NAME": "Name of the tool",
    "TOOL_CALL_ID": "Unique tool call ID",
    "TOOL_SUCCESS": "true/false",
    
    # Gate variables
    "GATE_NAME": "Validation gate name",
    "GATE_FILES": "Space-separated list of files",
    "GATE_ERRORS": "Newline-separated errors (for failures)",
    
    # Intent variables (DAG)
    "INTENT_PATH": "DAG path (e.g., 'conversation.act.write.modify')",
    "INTENT_BRANCH": "First-level branch (e.g., 'act')",
    "INTENT_TERMINAL": "Terminal node (e.g., 'modify')",
    "INTENT_CONFIDENCE": "Classification confidence (0.0-1.0)",
    
    # File change variables
    "FILE_PATH": "Path to changed file",
    "FILE_CHANGE_TYPE": "create/modify/delete",
    "FILE_DIFF": "Unified diff (for modifications)",
    
    # Generic event variables
    "EVENT_TYPE": "Full event name (e.g., 'task:complete')",
    "EVENT_TIMESTAMP": "ISO timestamp",
}
