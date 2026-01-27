"""Hook registry for event-driven extensibility.

Manages hook registration, requirement validation, and event dispatch.
Thread-safe implementation supporting Python 3.14t free-threading.
"""

import asyncio
import logging
import os
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from sunwell.agent.hooks.types import (
    HookEvent,
    HookHandler,
    HookMetadata,
    HookRegistration,
    Unsubscribe,
)

logger = logging.getLogger(__name__)


@dataclass
class HookRegistry:
    """Registry for event hooks.

    Thread-safe implementation with requirement validation.

    Usage:
        registry = HookRegistry()

        # Register a hook
        unsubscribe = registry.register(
            HookEvent.TASK_COMPLETE,
            my_handler,
            metadata=HookMetadata(
                events=(HookEvent.TASK_COMPLETE,),
                requires_bins=("git",),
                name="my-hook",
            ),
        )

        # Emit an event
        await registry.emit(HookEvent.TASK_COMPLETE, {"task_id": "123"})

        # Unsubscribe
        unsubscribe()
    """

    _registrations: dict[str, HookRegistration] = field(default_factory=dict)
    """All registered hooks by ID."""

    _by_event: dict[HookEvent, set[str]] = field(default_factory=dict)
    """Registration IDs indexed by event."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    _failed_requirements: dict[str, str] = field(default_factory=dict)
    """Cache of failed requirement checks: hook_id -> reason."""

    def register(
        self,
        event: HookEvent,
        handler: HookHandler,
        metadata: HookMetadata | None = None,
    ) -> Unsubscribe:
        """Register a hook for an event.

        Args:
            event: The event to subscribe to
            handler: Handler function (sync or async)
            metadata: Optional metadata with requirements

        Returns:
            Unsubscribe function to remove the hook
        """
        hook_id = uuid.uuid4().hex[:12]

        # Validate requirements if metadata provided
        if metadata and not self.check_requirements(metadata):
            reason = self._failed_requirements.get(hook_id, "Unknown requirement failure")
            logger.warning(
                "Hook %s requirements not met: %s",
                metadata.name or hook_id,
                reason,
            )
            # Still register but mark as failed
            self._failed_requirements[hook_id] = reason

        registration = HookRegistration(
            handler=handler,
            metadata=metadata,
            id=hook_id,
        )

        with self._lock:
            self._registrations[hook_id] = registration

            # Index by event
            if event not in self._by_event:
                self._by_event[event] = set()
            self._by_event[event].add(hook_id)

            # Also index by metadata events if provided
            if metadata:
                for meta_event in metadata.events:
                    if meta_event not in self._by_event:
                        self._by_event[meta_event] = set()
                    self._by_event[meta_event].add(hook_id)

        logger.debug(
            "Registered hook %s for event %s",
            metadata.name if metadata else hook_id,
            event.value,
        )

        return lambda: self._unregister(hook_id)

    def _unregister(self, hook_id: str) -> None:
        """Remove a hook registration."""
        with self._lock:
            if hook_id not in self._registrations:
                return

            registration = self._registrations.pop(hook_id)

            # Remove from event index
            for event, hook_ids in self._by_event.items():
                hook_ids.discard(hook_id)

            # Clean up failed requirements cache
            self._failed_requirements.pop(hook_id, None)

            logger.debug(
                "Unregistered hook %s",
                registration.metadata.name if registration.metadata else hook_id,
            )

    async def emit(self, event: HookEvent, data: dict[str, Any]) -> None:
        """Emit an event to all registered handlers.

        Handles both sync and async handlers. Errors in handlers are logged
        but don't stop other handlers from executing.

        Args:
            event: The event to emit
            data: Event-specific data dictionary
        """
        with self._lock:
            hook_ids = list(self._by_event.get(event, set()))
            registrations = [
                self._registrations[hid]
                for hid in hook_ids
                if hid in self._registrations
            ]

        if not registrations:
            return

        logger.debug("Emitting %s to %d hooks", event.value, len(registrations))

        for registration in registrations:
            # Skip if requirements failed
            if registration.id in self._failed_requirements:
                continue

            try:
                result = registration.handler(event, data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                hook_name = (
                    registration.metadata.name
                    if registration.metadata
                    else registration.id
                )
                logger.exception("Hook %s failed for event %s", hook_name, event.value)

    def emit_sync(self, event: HookEvent, data: dict[str, Any]) -> None:
        """Emit an event synchronously.

        Only calls sync handlers; async handlers are skipped with a warning.

        Args:
            event: The event to emit
            data: Event-specific data dictionary
        """
        with self._lock:
            hook_ids = list(self._by_event.get(event, set()))
            registrations = [
                self._registrations[hid]
                for hid in hook_ids
                if hid in self._registrations
            ]

        for registration in registrations:
            if registration.id in self._failed_requirements:
                continue

            try:
                result = registration.handler(event, data)
                if asyncio.iscoroutine(result):
                    logger.warning(
                        "Async hook %s skipped in sync emit",
                        registration.metadata.name
                        if registration.metadata
                        else registration.id,
                    )
            except Exception:
                hook_name = (
                    registration.metadata.name
                    if registration.metadata
                    else registration.id
                )
                logger.exception("Hook %s failed for event %s", hook_name, event.value)

    def check_requirements(self, metadata: HookMetadata) -> bool:
        """Check if hook requirements are satisfied.

        Validates:
        - Required binaries are in PATH
        - Required environment variables are set

        Args:
            metadata: Hook metadata with requirements

        Returns:
            True if all requirements are met
        """
        # Check required binaries
        for bin_name in metadata.requires_bins:
            if shutil.which(bin_name) is None:
                logger.debug("Required binary not found: %s", bin_name)
                return False

        # Check required environment variables
        for env_var in metadata.requires_env:
            if not os.environ.get(env_var):
                logger.debug("Required env var not set: %s", env_var)
                return False

        return True

    def get_hooks_for_event(self, event: HookEvent) -> list[HookRegistration]:
        """Get all hooks registered for an event.

        Args:
            event: The event to query

        Returns:
            List of hook registrations
        """
        with self._lock:
            hook_ids = self._by_event.get(event, set())
            return [
                self._registrations[hid]
                for hid in hook_ids
                if hid in self._registrations
            ]

    def get_all_hooks(self) -> list[HookRegistration]:
        """Get all registered hooks.

        Returns:
            List of all hook registrations
        """
        with self._lock:
            return list(self._registrations.values())

    def clear(self) -> None:
        """Remove all hooks (for testing)."""
        with self._lock:
            self._registrations.clear()
            self._by_event.clear()
            self._failed_requirements.clear()


# =============================================================================
# Global Instance
# =============================================================================

_global_hooks: HookRegistry | None = None
_global_hooks_lock = threading.Lock()


def get_hook_registry() -> HookRegistry:
    """Get the global HookRegistry instance.

    Lazily initialized on first access. Thread-safe.
    """
    global _global_hooks
    if _global_hooks is None:
        with _global_hooks_lock:
            if _global_hooks is None:
                _global_hooks = HookRegistry()
    return _global_hooks


def reset_hooks_for_tests() -> None:
    """Reset the global hooks registry (for testing only)."""
    global _global_hooks
    with _global_hooks_lock:
        if _global_hooks is not None:
            _global_hooks.clear()
        _global_hooks = None


# =============================================================================
# Convenience Functions
# =============================================================================


def on_hook(
    event: HookEvent,
    metadata: HookMetadata | None = None,
) -> Unsubscribe:
    """Decorator to register a hook handler.

    Usage:
        @on_hook(HookEvent.TASK_COMPLETE)
        async def handle_task_complete(event: HookEvent, data: dict) -> None:
            print(f"Task completed: {data['task_id']}")

    Args:
        event: Event to subscribe to
        metadata: Optional hook metadata

    Returns:
        Decorator function
    """
    def decorator(handler: HookHandler) -> HookHandler:
        registry = get_hook_registry()
        registry.register(event, handler, metadata)
        return handler
    return decorator


async def emit_hook(event: HookEvent, **data: Any) -> None:
    """Emit a hook event using the global registry.

    Convenience function for emitting events.

    Args:
        event: Event to emit
        **data: Event data as keyword arguments
    """
    registry = get_hook_registry()
    await registry.emit(event, data)


def emit_hook_sync(event: HookEvent, **data: Any) -> None:
    """Emit a hook event synchronously using the global registry.

    Args:
        event: Event to emit
        **data: Event data as keyword arguments
    """
    registry = get_hook_registry()
    registry.emit_sync(event, data)
