"""Scanners for different project types (RFC-100).

Each scanner implements the Scanner protocol to:
1. Discover nodes (files, modules, packages)
2. Extract edges (imports, links, dependencies)
3. Run health probes (linting, coverage, drift detection)
"""

from sunwell.knowledge.analysis.scanners.code import CodeScanner
from sunwell.knowledge.analysis.scanners.docs import DocsScanner

__all__ = [
    "CodeScanner",
    "DocsScanner",
]
