"""Skill graph and compilation event factories (RFC-087, RFC-111).

Event factories for skill execution lifecycle:
- skill_graph_resolved_event: Graph resolved for lens
- skill_wave_start_event, skill_wave_complete_event: Wave execution
- skill_cache_hit_event: Result from cache
- skill_execute_start_event, skill_execute_complete_event: Individual skill
- skill_compile_* events: Compilation lifecycle (RFC-111)
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType

# =============================================================================
# RFC-087: Skill Graph Event Factories
# =============================================================================


def skill_graph_resolved_event(
    lens_name: str,
    skill_count: int,
    wave_count: int,
    content_hash: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill graph resolved event (RFC-087).

    Emitted when the skill graph for a lens has been resolved.

    Args:
        lens_name: Name of the lens
        skill_count: Number of skills in graph
        wave_count: Number of execution waves
        content_hash: Hash for cache invalidation
    """
    return AgentEvent(
        EventType.SKILL_GRAPH_RESOLVED,
        {
            "lens_name": lens_name,
            "skill_count": skill_count,
            "wave_count": wave_count,
            "content_hash": content_hash,
            **kwargs,
        },
    )


def skill_wave_start_event(
    wave_index: int,
    total_waves: int,
    skills: list[str],
    parallel: bool = True,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill wave start event (RFC-087).

    Emitted when a wave of parallel skills starts executing.

    Args:
        wave_index: Index of this wave (0-based)
        total_waves: Total number of waves
        skills: Skill names in this wave
        parallel: Whether skills execute in parallel
    """
    return AgentEvent(
        EventType.SKILL_WAVE_START,
        {
            "wave_index": wave_index,
            "total_waves": total_waves,
            "skills": skills,
            "parallel": parallel,
            **kwargs,
        },
    )


def skill_wave_complete_event(
    wave_index: int,
    duration_ms: int,
    succeeded: list[str],
    failed: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill wave complete event (RFC-087).

    Emitted when a wave finishes execution.

    Args:
        wave_index: Index of the completed wave
        duration_ms: Wave execution time in milliseconds
        succeeded: Skills that succeeded
        failed: Skills that failed
    """
    return AgentEvent(
        EventType.SKILL_WAVE_COMPLETE,
        {
            "wave_index": wave_index,
            "duration_ms": duration_ms,
            "succeeded": succeeded,
            "failed": failed,
            **kwargs,
        },
    )


def skill_cache_hit_event(
    skill_name: str,
    cache_key: str,
    saved_ms: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill cache hit event (RFC-087).

    Emitted when a skill result is retrieved from cache.

    Args:
        skill_name: Name of the cached skill
        cache_key: Cache key that matched
        saved_ms: Estimated time saved in milliseconds
    """
    return AgentEvent(
        EventType.SKILL_CACHE_HIT,
        {
            "skill_name": skill_name,
            "cache_key": cache_key,
            "saved_ms": saved_ms,
            **kwargs,
        },
    )


def skill_execute_start_event(
    skill_name: str,
    wave_index: int,
    requires: list[str],
    context_keys_available: list[str],
    *,
    risk_level: str | None = None,
    has_permissions: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill execute start event (RFC-087).

    Emitted when a single skill starts executing.

    Args:
        skill_name: Name of the skill
        wave_index: Which wave this skill is in
        requires: Context keys this skill requires
        context_keys_available: Context keys currently available
        risk_level: Security risk level (low/medium/high/critical)
        has_permissions: Whether skill declares explicit permissions
    """
    return AgentEvent(
        EventType.SKILL_EXECUTE_START,
        {
            "skill_name": skill_name,
            "wave_index": wave_index,
            "requires": requires,
            "context_keys_available": context_keys_available,
            "risk_level": risk_level,
            "has_permissions": has_permissions,
            **kwargs,
        },
    )


def skill_execute_complete_event(
    skill_name: str,
    duration_ms: int,
    produces: list[str],
    cached: bool,
    success: bool,
    error: str | None = None,
    *,
    risk_level: str | None = None,
    violations_detected: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill execute complete event (RFC-087).

    Emitted when a skill finishes execution (success or failure).

    Args:
        skill_name: Name of the skill
        duration_ms: Execution time in milliseconds
        produces: Context keys this skill produces
        cached: Whether result was from cache
        success: Whether execution succeeded
        error: Error message if failed
        risk_level: Evaluated security risk level
        violations_detected: Number of security violations during execution
    """
    return AgentEvent(
        EventType.SKILL_EXECUTE_COMPLETE,
        {
            "skill_name": skill_name,
            "duration_ms": duration_ms,
            "produces": produces,
            "cached": cached,
            "success": success,
            "error": error,
            "risk_level": risk_level,
            "violations_detected": violations_detected,
            **kwargs,
        },
    )


# =============================================================================
# RFC-111: Skill Compilation Event Factories
# =============================================================================


def skill_compile_start_event(
    lens_name: str,
    skill_count: int,
    target_skills: list[str] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile start event (RFC-111).

    Emitted when starting to compile skills into tasks.

    Args:
        lens_name: Name of the lens being compiled
        skill_count: Number of skills to compile
        target_skills: Optional subset of skills being compiled
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_START,
        {
            "lens_name": lens_name,
            "skill_count": skill_count,
            "target_skills": target_skills,
            **kwargs,
        },
    )


def skill_compile_complete_event(
    lens_name: str,
    task_count: int,
    wave_count: int,
    duration_ms: int,
    cached: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile complete event (RFC-111).

    Emitted when skill compilation finishes.

    Args:
        lens_name: Name of the compiled lens
        task_count: Number of tasks in compiled graph
        wave_count: Number of execution waves
        duration_ms: Compilation time in milliseconds
        cached: Whether result was from compilation cache
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_COMPLETE,
        {
            "lens_name": lens_name,
            "task_count": task_count,
            "wave_count": wave_count,
            "duration_ms": duration_ms,
            "cached": cached,
            **kwargs,
        },
    )


def skill_compile_cache_hit_event(
    cache_key: str,
    task_count: int,
    wave_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile cache hit event (RFC-111).

    Emitted when a compiled TaskGraph is retrieved from cache.

    Args:
        cache_key: Cache key that matched
        task_count: Number of tasks in cached graph
        wave_count: Number of execution waves
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_CACHE_HIT,
        {
            "cache_key": cache_key,
            "task_count": task_count,
            "wave_count": wave_count,
            **kwargs,
        },
    )


def skill_subgraph_extracted_event(
    target_skills: list[str],
    total_skills: int,
    extracted_skills: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill subgraph extracted event (RFC-111).

    Emitted when a subgraph is extracted for targeted execution.

    Args:
        target_skills: Skills that were targeted
        total_skills: Total skills in original graph
        extracted_skills: Skills in extracted subgraph (including dependencies)
    """
    return AgentEvent(
        EventType.SKILL_SUBGRAPH_EXTRACTED,
        {
            "target_skills": target_skills,
            "total_skills": total_skills,
            "extracted_skills": extracted_skills,
            **kwargs,
        },
    )
