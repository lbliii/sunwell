"""Foundation domain - Zero-dependency base types, config, errors, identity.

This domain contains the foundational building blocks that have no dependencies
on other sunwell modules. Everything else imports from here.

RFC-138: Module Architecture Consolidation
"""

# Config
# Binding (re-export from subpackage)
from sunwell.foundation.binding import (
    Binding,
    BindingIndex,
    BindingIndexEntry,
    BindingIndexManager,
    BindingManager,
    create_binding_identity,
    create_binding_uri,
    get_binding_or_create_temp,
)
from sunwell.foundation.config import (
    SunwellConfig,
    get_config,
    load_config,
    reset_config,
    resolve_naaru_model,
    save_default_config,
)

# Core (re-export from subpackage)
from sunwell.foundation.core.lens import Lens, LensMetadata

# Errors
from sunwell.foundation.errors import (
    ErrorCode,
    SunwellError,
    config_error,
    from_anthropic_error,
    from_openai_error,
    lens_error,
    model_error,
    tool_error,
    tools_not_supported,
)

# Identity
from sunwell.foundation.identity import (
    ResourceIdentity,
    ResourceType,
    SunwellURI,
    URIParseError,
    validate_slug,
)

# Schema (re-export from subpackage)
from sunwell.foundation.schema import LensLoader

# Threading
from sunwell.foundation.threading import (
    ParallelStats,
    WorkloadType,
    cpu_count,
    is_free_threaded,
    optimal_llm_workers,
    optimal_workers,
    run_cpu_bound,
    run_parallel,
    run_parallel_async,
    runtime_info,
)

# Types - import key types explicitly (more from sunwell.foundation.types)
from sunwell.foundation.types import (
    Confidence,
    ModelSize,
    NaaruConfig,
    SemanticVersion,
    Severity,
    Tier,
)

# Utils (re-export from subpackage)
from sunwell.foundation.utils import (
    compute_file_hash,
    compute_hash,
    compute_string_hash,
    ensure_dir,
    normalize_path,
    relative_to_cwd,
    safe_json_dumps,
    safe_json_loads,
    safe_yaml_dump,
    safe_yaml_dumps,
    safe_yaml_load,
    safe_yaml_loads,
    sanitize_filename,
    slugify,
)

__all__ = [
    # === Core Types ===
    "Lens",
    "LensMetadata",
    "NaaruConfig",
    "Severity",
    "Tier",
    "ModelSize",
    "Confidence",
    "SemanticVersion",
    # === Config ===
    "SunwellConfig",
    "get_config",
    "load_config",
    "reset_config",
    "resolve_naaru_model",
    "save_default_config",
    # === Errors ===
    "ErrorCode",
    "SunwellError",
    "config_error",
    "from_anthropic_error",
    "from_openai_error",
    "lens_error",
    "model_error",
    "tool_error",
    "tools_not_supported",
    # === Identity ===
    "ResourceIdentity",
    "ResourceType",
    "SunwellURI",
    "URIParseError",
    "validate_slug",
    # === Threading ===
    "WorkloadType",
    "cpu_count",
    "is_free_threaded",
    "optimal_llm_workers",
    "optimal_workers",
    "ParallelStats",
    "run_cpu_bound",
    "run_parallel",
    "run_parallel_async",
    "runtime_info",
    # === Schema ===
    "LensLoader",
    # === Binding ===
    "Binding",
    "BindingManager",
    "BindingIndex",
    "BindingIndexEntry",
    "BindingIndexManager",
    "create_binding_identity",
    "create_binding_uri",
    "get_binding_or_create_temp",
    # === Utils ===
    "compute_file_hash",
    "compute_hash",
    "compute_string_hash",
    "ensure_dir",
    "normalize_path",
    "relative_to_cwd",
    "safe_json_dumps",
    "safe_json_loads",
    "safe_yaml_dump",
    "safe_yaml_dumps",
    "safe_yaml_load",
    "safe_yaml_loads",
    "sanitize_filename",
    "slugify",
]
