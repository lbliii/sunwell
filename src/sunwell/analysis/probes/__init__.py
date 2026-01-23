"""Health probes for State DAG analysis (RFC-100, RFC-103).

Probes are pluggable components that analyze nodes and produce health scores.

Available probes:
- drift: Detect documentation drift from source code (requires workspace linking)
"""

from sunwell.analysis.probes.drift import DriftProbe, DriftResult

__all__ = ["DriftProbe", "DriftResult"]
