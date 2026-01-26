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
- Tiered indexing (L0-L3) for multi-project scalability
- Signature extraction for lightweight L1 indexing
"""

from sunwell.knowledge.indexing.auto_config import (
    AutoFeatures,
    detect_auto_features,
    estimate_goal_complexity,
)
from sunwell.knowledge.indexing.fallback import ContextResult, SmartContext, create_smart_context
from sunwell.knowledge.indexing.metrics import IndexMetrics
from sunwell.knowledge.indexing.priority import get_priority_files
from sunwell.knowledge.indexing.project_type import (
    PROJECT_MARKERS,
    ProjectType,
    detect_file_type,
    detect_project_type,
)
from sunwell.knowledge.indexing.service import IndexingService, IndexState, IndexStatus
from sunwell.knowledge.indexing.signature_extractor import (
    Signature,
    SignatureExtractor,
    extract_signatures,
)

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
    # Signature extraction (L1 indexing)
    "SignatureExtractor",
    "Signature",
    "extract_signatures",
]
