"""Skill execution types and interfaces.

RFC-110: Skill execution moved to Agent. This module provides type definitions
and interfaces for skill execution that are used across the codebase.
"""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from sunwell.planning.skills.graph import SkillGraph
    from sunwell.planning.skills.types import SkillOutput


class ExecutionContext:
    """Execution context for skill execution.
    
    Provides context data (inputs, state) and a snapshot method
    for hashing/caching purposes.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        """Initialize execution context.
        
        Args:
            data: Context data dictionary
        """
        self._data = data or {}

    def __getitem__(self, key: str) -> Any:
        """Get context value by key."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set context value by key."""
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get context value with default."""
        return self._data.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        """Create a snapshot of the context for hashing/caching.
        
        Returns:
            Dictionary representation of the context
        """
        return dict(self._data)


class IncrementalSkillExecutor(Protocol):
    """Protocol for incremental skill execution with caching.
    
    RFC-110: Skill execution moved to Agent. This protocol defines
    the interface for skill executors that support incremental execution.
    """

    async def execute(
        self,
        graph: SkillGraph,
        context: ExecutionContext,
        on_wave_complete: Any | None = None,
        on_skill_complete: Any | None = None,
    ) -> dict[str, SkillOutput]:
        """Execute a skill graph with the given context.
        
        Args:
            graph: Skill graph to execute
            context: Execution context
            on_wave_complete: Optional callback for wave completion
            on_skill_complete: Optional callback for skill completion
            
        Returns:
            Mapping of skill name to output
        """
        ...
