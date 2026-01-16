"""Workspace detection and codebase indexing.

RFC-024 additions:
- WorkspaceConfig: Extended configuration with trust suggestions
- resolve_trust_level: Trust level resolution with precedence rules
"""

from sunwell.workspace.detector import (
    WorkspaceDetector,
    Workspace,
    WorkspaceConfig,
    resolve_trust_level,
    DEFAULT_TRUST,
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
