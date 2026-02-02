"""Skill compilation and execution event schemas."""

from typing import TypedDict


class SkillCompileStartData(TypedDict, total=False):
    """Data for skill_compile_start event."""

    lens_name: str  # Required
    skill_count: int
    target_skills: list[str] | None


class SkillCompileCompleteData(TypedDict, total=False):
    """Data for skill_compile_complete event.

    Note: Factory provides task_count instead of skill_count.
    """

    lens_name: str  # Required
    task_count: int  # Required - number of tasks in compiled graph
    wave_count: int  # Required - number of execution waves
    duration_ms: int  # Required
    cached: bool


class SkillCompileCacheHitData(TypedDict, total=False):
    """Data for skill_compile_cache_hit event.

    Note: Factory provides cache_key/task_count/wave_count.
    """

    cache_key: str  # Required
    task_count: int  # Required
    wave_count: int  # Required


class SkillSubgraphExtractedData(TypedDict, total=False):
    """Data for skill_subgraph_extracted event.

    Note: Factory provides target_skills/total_skills/extracted_skills.
    """

    target_skills: list[str]  # Required
    total_skills: int  # Required
    extracted_skills: int  # Required


class SkillGraphResolvedData(TypedDict, total=False):
    """Data for skill_graph_resolved event (RFC-087)."""
    lens_name: str  # Required
    skill_count: int  # Required
    wave_count: int  # Required
    content_hash: str  # Required


class SkillWaveStartData(TypedDict, total=False):
    """Data for skill_wave_start event (RFC-087)."""
    wave_index: int  # Required
    total_waves: int  # Required
    skills: list[str]  # Required - skill names in this wave
    parallel: bool  # Whether skills execute in parallel


class SkillWaveCompleteData(TypedDict, total=False):
    """Data for skill_wave_complete event (RFC-087)."""
    wave_index: int  # Required
    duration_ms: int  # Required
    succeeded: list[str]  # Required - skills that succeeded
    failed: list[str]  # Required - skills that failed


class SkillCacheHitData(TypedDict, total=False):
    """Data for skill_cache_hit event (RFC-087)."""
    skill_name: str  # Required
    cache_key: str  # Required
    saved_ms: int  # Required - estimated time saved


class SkillExecuteStartData(TypedDict, total=False):
    """Data for skill_execute_start event (RFC-087)."""
    skill_name: str  # Required
    wave_index: int  # Required
    requires: list[str]  # Required - context keys this skill needs
    context_keys_available: list[str]  # Required - context keys currently available
    # RFC-089: Security metadata
    risk_level: str | None  # low/medium/high/critical (None = not assessed)
    has_permissions: bool  # Whether skill declares explicit permissions


class SkillExecuteCompleteData(TypedDict, total=False):
    """Data for skill_execute_complete event (RFC-087)."""
    skill_name: str  # Required
    duration_ms: int  # Required
    produces: list[str]  # Required - context keys produced
    cached: bool  # Required - whether result was from cache
    success: bool  # Required - whether execution succeeded
    error: str | None  # Error message if failed
    # RFC-089: Security metadata
    risk_level: str | None  # Evaluated risk level after execution
    violations_detected: int  # Number of security violations during execution
