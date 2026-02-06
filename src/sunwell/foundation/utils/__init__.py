"""Foundation utilities - Generic helpers with zero dependencies.

RFC-138: Module Architecture Consolidation

Provides generic utilities used across domains:
- String manipulation (slugify)
- Validation (validate_slug)
- Hashing (compute_hash, compute_file_hash, compute_string_hash, compute_short_hash)
- Math (cosine_similarity)
- Path operations (normalize_path, sanitize_filename, ensure_dir, relative_to_cwd)
- Serialization (safe_json_loads, safe_json_dumps, safe_yaml_load, safe_yaml_dump)
- Timestamps (absolute_timestamp, format_for_summary)
"""

from sunwell.foundation.utils.hashing import (
    compute_file_hash,
    compute_hash,
    compute_short_hash,
    compute_string_hash,
)
from sunwell.foundation.utils.math import cosine_similarity
from sunwell.foundation.utils.paths import (
    ensure_dir,
    normalize_path,
    relative_to_cwd,
    sanitize_filename,
)
from sunwell.foundation.utils.serialization import (
    safe_json_dump,
    safe_json_dumps,
    safe_json_load,
    safe_json_loads,
    safe_jsonl_append,
    safe_jsonl_load,
    safe_yaml_dump,
    safe_yaml_dumps,
    safe_yaml_load,
    safe_yaml_loads,
)
from sunwell.foundation.utils.strings import slugify
from sunwell.foundation.utils.timestamps import (
    absolute_timestamp,
    absolute_timestamp_full,
    format_for_summary,
)
from sunwell.foundation.utils.validation import validate_slug

__all__ = [
    # String utilities
    "slugify",
    # Validation utilities
    "validate_slug",
    # Hashing utilities
    "compute_hash",
    "compute_file_hash",
    "compute_string_hash",
    "compute_short_hash",
    # Math utilities
    "cosine_similarity",
    # Path utilities
    "normalize_path",
    "sanitize_filename",
    "ensure_dir",
    "relative_to_cwd",
    # Serialization utilities
    "safe_json_load",
    "safe_json_loads",
    "safe_json_dump",
    "safe_json_dumps",
    "safe_jsonl_load",
    "safe_jsonl_append",
    "safe_yaml_load",
    "safe_yaml_loads",
    "safe_yaml_dump",
    "safe_yaml_dumps",
    # Timestamp utilities
    "absolute_timestamp",
    "absolute_timestamp_full",
    "format_for_summary",
]
