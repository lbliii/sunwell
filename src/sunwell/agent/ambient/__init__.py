"""Ambient intelligence system for proactive issue detection.

Detects issues during execution and surfaces them proactively
through AMBIENT_ALERT checkpoints.

Usage:
    from sunwell.agent.ambient import (
        AmbientAlert,
        AmbientAlertType,
        AlertSeverity,
        AmbientDetector,
        AmbientRegistry,
    )
    
    # Register custom detector
    registry = AmbientRegistry()
    registry.register(MyCustomDetector())
    
    # Analyze artifact
    alerts = await registry.analyze(artifact)
"""

from sunwell.agent.ambient.alerts import (
    AlertSeverity,
    AmbientAlert,
    AmbientAlertType,
)
from sunwell.agent.ambient.detectors import (
    AmbientDetector,
    AmbientRegistry,
    PerformancePatternDetector,
    SecretPatternDetector,
    StyleViolationDetector,
)

__all__ = [
    "AlertSeverity",
    "AmbientAlert",
    "AmbientAlertType",
    "AmbientDetector",
    "AmbientRegistry",
    "PerformancePatternDetector",
    "SecretPatternDetector",
    "StyleViolationDetector",
]
