"""Hooks — Event-driven extensibility system.

This module provides infrastructure for external integrations to observe
and react to agent lifecycle events.

Components:
- HookEvent: Enumeration of available hook events
- HookMetadata: Hook requirements and subscriptions
- HookRegistry: Registration and dispatch
- Helper functions for convenient hook usage

Usage:
    from sunwell.agent.hooks import HookEvent, emit_hook, on_hook

    # Register a hook using decorator
    @on_hook(HookEvent.TASK_COMPLETE)
    async def handle_task(event: HookEvent, data: dict) -> None:
        print(f"Task completed: {data['task_id']}")

    # Or register manually
    registry = get_hook_registry()
    unsubscribe = registry.register(
        HookEvent.TASK_COMPLETE,
        my_handler,
    )

    # Emit events
    await emit_hook(
        HookEvent.TASK_COMPLETE,
        task_id="123",
        success=True,
    )
"""

from sunwell.agent.hooks.registry import (
    HookRegistry,
    emit_hook,
    emit_hook_sync,
    get_hook_registry,
    on_hook,
)
from sunwell.agent.hooks.types import (
    EVENT_DATA_SCHEMAS,
    HookEvent,
    HookHandler,
    HookMetadata,
    HookRegistration,
    Unsubscribe,
)

__all__ = [
    # Types
    "HookEvent",
    "HookHandler",
    "HookMetadata",
    "HookRegistration",
    "Unsubscribe",
    "EVENT_DATA_SCHEMAS",
    # Registry
    "HookRegistry",
    "get_hook_registry",
    # Convenience
    "emit_hook",
    "emit_hook_sync",
    "on_hook",
]
