"""Integration of user hooks with the global HookRegistry.

Registers user-defined hooks from `.sunwell/hooks.toml` with the
global hook registry so they're invoked on agent events.
"""

import logging
from pathlib import Path
from typing import Any

from sunwell.agent.hooks.registry import HookRegistry, get_hook_registry
from sunwell.agent.hooks.types import HookEvent, HookMetadata
from sunwell.interface.cli.hooks.executor import ShellHookExecutor
from sunwell.interface.cli.hooks.loader import load_user_hooks
from sunwell.interface.cli.hooks.schema import HookConfig

logger = logging.getLogger(__name__)

# Cache of registered user hooks (for cleanup)
_registered_hooks: list[tuple[str, callable]] = []


def register_user_hooks(workspace: Path) -> int:
    """Load and register user hooks from workspace.
    
    Reads `.sunwell/hooks.toml` and registers all valid hooks
    with the global HookRegistry.
    
    Args:
        workspace: Workspace root path
        
    Returns:
        Number of hooks registered
    """
    global _registered_hooks
    
    # Load configuration
    config = load_user_hooks(workspace)
    
    if not config.hooks:
        logger.debug("No user hooks configured")
        return 0
    
    # Create executor
    executor = ShellHookExecutor(workspace)
    
    # Get registry
    registry = get_hook_registry()
    
    # Register each hook
    count = 0
    for hook in config.hooks:
        try:
            unsubscribes = _register_hook(hook, executor, registry)
            _registered_hooks.extend(
                (hook.name, unsub) for unsub in unsubscribes
            )
            count += 1
            logger.info("Registered user hook: %s", hook.name)
        except Exception as e:
            logger.warning("Failed to register hook '%s': %s", hook.name, e)
    
    return count


def unregister_user_hooks() -> int:
    """Unregister all user hooks.
    
    Returns:
        Number of hooks unregistered
    """
    global _registered_hooks
    
    count = 0
    for name, unsubscribe in _registered_hooks:
        try:
            unsubscribe()
            count += 1
            logger.debug("Unregistered hook: %s", name)
        except Exception as e:
            logger.warning("Failed to unregister hook '%s': %s", name, e)
    
    _registered_hooks.clear()
    return count


def _register_hook(
    hook: HookConfig,
    executor: ShellHookExecutor,
    registry: HookRegistry,
) -> list[callable]:
    """Register a single hook with the registry.
    
    Args:
        hook: Hook configuration
        executor: Shell executor
        registry: Target registry
        
    Returns:
        List of unsubscribe functions
    """
    unsubscribes: list[callable] = []
    
    # Create metadata
    metadata = HookMetadata(
        events=tuple(_parse_event(e) for e in hook.on if _parse_event(e)),
        requires_bins=hook.requires,
        requires_env=hook.env,
        name=hook.name,
        description=f"User hook: {hook.run[:50]}...",
    )
    
    # Create handler
    async def handler(event: HookEvent, data: dict[str, Any]) -> None:
        await executor.execute(hook, event, data)
    
    # Register for each event
    for event_str in hook.on:
        event = _parse_event(event_str)
        if event:
            unsub = registry.register(event, handler, metadata)
            unsubscribes.append(unsub)
        else:
            logger.warning(
                "Hook '%s' subscribes to unknown event: %s",
                hook.name, event_str,
            )
    
    return unsubscribes


def _parse_event(event_str: str) -> HookEvent | None:
    """Parse event string to HookEvent.
    
    Args:
        event_str: Event name (e.g., "session:end", "task:complete")
        
    Returns:
        HookEvent or None if not found
    """
    # Normalize the string
    normalized = event_str.lower().strip()
    
    # Try direct match
    for event in HookEvent:
        if event.value == normalized:
            return event
    
    # Try with colon replacement (some users might use underscore)
    normalized_underscore = normalized.replace("_", ":")
    for event in HookEvent:
        if event.value == normalized_underscore:
            return event
    
    return None


def get_registered_hook_count() -> int:
    """Get number of currently registered user hooks.
    
    Returns:
        Number of registered hooks
    """
    return len(_registered_hooks)


def list_registered_hooks() -> list[str]:
    """Get names of all registered user hooks.
    
    Returns:
        List of hook names
    """
    return [name for name, _ in _registered_hooks]
