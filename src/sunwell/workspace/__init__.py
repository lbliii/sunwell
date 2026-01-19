"""Workspace detection and codebase indexing.

RFC-024 additions:
- WorkspaceConfig: Extended configuration with trust suggestions
- resolve_trust_level: Trust level resolution with precedence rules
"""

from sunwell.workspace.detector import (
    DEFAULT_TRUST,
    Workspace,
    WorkspaceConfig,
    WorkspaceDetector,
    resolve_trust_level,
)
from sunwell.workspace.indexer import CodebaseIndexer

__all__ = [
    "WorkspaceDetector",
    "Workspace",
    "WorkspaceConfig",
    "resolve_trust_level",
    "DEFAULT_TRUST",
    "CodebaseIndexer",
]
