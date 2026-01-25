"""Continuous codebase indexing for always-smart RAG (RFC-108).

This module provides background semantic indexing that makes Sunwell
always aware of your project without requiring explicit --smart flags.

Features:
- Background indexing (never blocks user)
- Project type detection (code/prose/script/docs)
- Content-aware chunking (AST for code, paragraphs for prose)
- Priority indexing (hot files first)
- Graceful fallback (grep when no embeddings)
- File watching (incremental updates)
"""

from sunwell.indexing.auto_config import (
    AutoFeatures,
    detect_auto_features,
    estimate_goal_complexity,
)
from sunwell.indexing.fallback import ContextResult, SmartContext, create_smart_context
from sunwell.indexing.metrics import IndexMetrics
from sunwell.indexing.priority import get_priority_files
from sunwell.indexing.project_type import (
    PROJECT_MARKERS,
    ProjectType,
    detect_file_type,
    detect_project_type,
)
from sunwell.indexing.service import IndexingService, IndexState, IndexStatus

__all__ = [
    # Core types
    "IndexingService",
    "IndexState",
    "IndexStatus",
    # Project detection
    "ProjectType",
    "detect_project_type",
    "detect_file_type",
    "PROJECT_MARKERS",
    # Priority
    "get_priority_files",
    # Fallback
    "SmartContext",
    "ContextResult",
    "create_smart_context",
    # Auto-configuration
    "AutoFeatures",
    "detect_auto_features",
    "estimate_goal_complexity",
    # Observability
    "IndexMetrics",
]
