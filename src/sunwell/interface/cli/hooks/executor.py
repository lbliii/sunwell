"""Shell command executor for user hooks.

Executes shell commands with variable interpolation and proper
error handling.
"""

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sunwell.agent.hooks.types import HookEvent
from sunwell.interface.cli.hooks.schema import HookConfig, HookTriggerCondition

logger = logging.getLogger(__name__)

# Pattern for ${VAR} or $VAR interpolation
_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)")


class ShellHookExecutor:
    """Executes shell commands for user hooks.
    
    Handles variable interpolation, timeouts, and background execution.
    
    Usage:
        executor = ShellHookExecutor(workspace=Path.cwd())
        await executor.execute(hook_config, event, event_data)
    """
    
    def __init__(self, workspace: Path) -> None:
        """Initialize the executor.
        
        Args:
            workspace: Working directory for commands
        """
        self.workspace = workspace
    
    async def execute(
        self,
        hook: HookConfig,
        event: HookEvent,
        data: dict[str, Any],
        *,
        success: bool = True,
    ) -> bool:
        """Execute a hook's shell command.
        
        Args:
            hook: Hook configuration
            event: The triggering event
            data: Event data for variable interpolation
            success: Whether the triggering operation was successful
            
        Returns:
            True if command succeeded (or was skipped), False on error
        """
        # Check trigger condition
        if not self._should_run(hook, success):
            logger.debug(
                "Skipping hook '%s' (when=%s, success=%s)",
                hook.name, hook.when.value, success,
            )
            return True
        
        # Interpolate variables
        try:
            command = self._interpolate(hook.run, event, data)
        except ValueError as e:
            logger.warning("Hook '%s' interpolation failed: %s", hook.name, e)
            return False
        
        # Determine working directory
        cwd = Path(hook.cwd) if hook.cwd else self.workspace
        
        logger.debug(
            "Executing hook '%s': %s (cwd=%s, timeout=%s, bg=%s)",
            hook.name, command[:100], cwd, hook.timeout, hook.background,
        )
        
        try:
            if hook.background:
                # Fire and forget
                self._run_background(command, cwd)
                return True
            else:
                # Wait for completion
                return await self._run_foreground(command, cwd, hook.timeout, hook.name)
        except Exception as e:
            logger.exception("Hook '%s' execution failed: %s", hook.name, e)
            return False
    
    def _should_run(self, hook: HookConfig, success: bool) -> bool:
        """Check if hook should run based on condition.
        
        Args:
            hook: Hook configuration
            success: Whether the triggering operation succeeded
            
        Returns:
            True if hook should run
        """
        if hook.when == HookTriggerCondition.ALWAYS:
            return True
        if hook.when == HookTriggerCondition.SUCCESS:
            return success
        if hook.when == HookTriggerCondition.FAILURE:
            return not success
        return False
    
    def _interpolate(
        self,
        template: str,
        event: HookEvent,
        data: dict[str, Any],
    ) -> str:
        """Interpolate variables in command template.
        
        Supports ${VAR} and $VAR syntax.
        
        Args:
            template: Command template
            event: Triggering event
            data: Event data
            
        Returns:
            Interpolated command string
            
        Raises:
            ValueError: If a required variable is missing
        """
        # Build variable context
        context = self._build_context(event, data)
        
        def replace(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            
            # Check context first
            if var_name in context:
                return _shell_escape(str(context[var_name]))
            
            # Fall back to environment
            env_value = os.environ.get(var_name)
            if env_value is not None:
                return _shell_escape(env_value)
            
            # Variable not found - use empty string with warning
            logger.warning("Variable ${%s} not found, using empty string", var_name)
            return ""
        
        return _VAR_PATTERN.sub(replace, template)
    
    def _build_context(
        self,
        event: HookEvent,
        data: dict[str, Any],
    ) -> dict[str, str]:
        """Build variable context from event and data.
        
        Args:
            event: Triggering event
            data: Event data
            
        Returns:
            Variable name -> value mapping
        """
        context: dict[str, str] = {
            # Generic event variables
            "EVENT_TYPE": event.value,
            "EVENT_TIMESTAMP": datetime.now(timezone.utc).isoformat(),
            
            # Workspace
            "SUNWELL_WORKSPACE": str(self.workspace),
        }
        
        # Map event data to standard variable names
        var_mapping: dict[str, str] = {
            # Session
            "session_id": "SUNWELL_SESSION_ID",
            "summary": "SUNWELL_SESSION_SUMMARY",
            
            # Task
            "task_id": "TASK_ID",
            "description": "TASK_DESCRIPTION",
            "success": "TASK_SUCCESS",
            "duration_ms": "TASK_DURATION_MS",
            
            # Tool
            "tool_name": "TOOL_NAME",
            "tool_call_id": "TOOL_CALL_ID",
            
            # Gate
            "gate_name": "GATE_NAME",
            "files": "GATE_FILES",
            "errors": "GATE_ERRORS",
            
            # Intent (DAG)
            "path": "INTENT_PATH",
            "confidence": "INTENT_CONFIDENCE",
            "reasoning": "INTENT_REASONING",
            "user_input": "USER_INPUT",
            
            # File changes
            "file_path": "FILE_PATH",
            "change_type": "FILE_CHANGE_TYPE",
            "diff": "FILE_DIFF",
        }
        
        for data_key, var_name in var_mapping.items():
            if data_key in data:
                value = data[data_key]
                
                # Convert lists to space-separated strings
                if isinstance(value, (list, tuple)):
                    if data_key == "errors":
                        # Errors are newline-separated
                        value = "\n".join(str(v) for v in value)
                    elif data_key == "path":
                        # DAG path is dot-separated
                        value = ".".join(str(v) for v in value)
                    else:
                        # Default: space-separated
                        value = " ".join(str(v) for v in value)
                elif isinstance(value, bool):
                    value = "true" if value else "false"
                else:
                    value = str(value)
                
                context[var_name] = value
        
        # Derive additional intent variables if path present
        if "path" in data:
            path = data["path"]
            if len(path) > 1:
                context["INTENT_BRANCH"] = str(path[1])
            if path:
                context["INTENT_TERMINAL"] = str(path[-1])
        
        return context
    
    def _run_background(self, command: str, cwd: Path) -> None:
        """Run command in background without waiting.
        
        Args:
            command: Shell command
            cwd: Working directory
        """
        # Use subprocess.Popen without waiting
        subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent
        )
        logger.debug("Started background command")
    
    async def _run_foreground(
        self,
        command: str,
        cwd: Path,
        timeout: int,
        hook_name: str,
    ) -> bool:
        """Run command and wait for completion.
        
        Args:
            command: Shell command
            cwd: Working directory
            timeout: Timeout in seconds
            hook_name: Hook name for logging
            
        Returns:
            True if command succeeded (exit code 0)
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            if proc.returncode == 0:
                logger.debug("Hook '%s' completed successfully", hook_name)
                if stdout:
                    logger.debug("stdout: %s", stdout.decode()[:500])
                return True
            else:
                logger.warning(
                    "Hook '%s' failed with exit code %d",
                    hook_name, proc.returncode,
                )
                if stderr:
                    logger.warning("stderr: %s", stderr.decode()[:500])
                return False
                
        except asyncio.TimeoutError:
            logger.warning(
                "Hook '%s' timed out after %d seconds",
                hook_name, timeout,
            )
            return False


def _shell_escape(value: str) -> str:
    """Escape a value for safe shell interpolation.
    
    Args:
        value: Value to escape
        
    Returns:
        Shell-safe string
    """
    # Replace single quotes with escaped version
    # and wrap in single quotes for safety
    if "'" in value:
        # Use $'...' syntax for strings with single quotes
        value = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"$'{value}'"
    elif any(c in value for c in " \t\n\"$`\\"):
        # Wrap in single quotes if special chars present
        return f"'{value}'"
    else:
        return value
