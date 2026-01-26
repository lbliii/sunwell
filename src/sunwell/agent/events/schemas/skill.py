"""Skill compilation and execution event schemas."""

from typing import TypedDict


class SkillCompileStartData(TypedDict, total=False):
    """Data for skill_compile_start event."""
    lens_name: str  # Required


class SkillCompileCompleteData(TypedDict, total=False):
    """Data for skill_compile_complete event."""
    lens_name: str  # Required
    skill_count: int  # Required
    duration_ms: int  # Required


class SkillCompileCacheHitData(TypedDict, total=False):
    """Data for skill_compile_cache_hit event."""
    lens_name: str  # Required


class SkillSubgraphExtractedData(TypedDict, total=False):
    """Data for skill_subgraph_extracted event."""
    skill_name: str  # Required
    subgraph_size: int  # Required


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
