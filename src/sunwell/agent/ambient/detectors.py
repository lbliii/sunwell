"""Ambient detectors for proactive issue detection.

Implements the detector protocol and provides built-in detectors
for common issues like secrets, performance problems, and style violations.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sunwell.agent.ambient.alerts import (
    AlertSeverity,
    AmbientAlert,
    AmbientAlertType,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Artifact:
    """A code artifact to analyze.

    Attributes:
        path: Path to the file
        content: File content
        task_id: ID of task that created/modified this artifact
    """

    path: Path
    content: str
    task_id: str | None = None


class AmbientDetector(Protocol):
    """Protocol for ambient issue detectors.

    Detectors analyze artifacts and return alerts for any issues found.
    """

    @property
    def name(self) -> str:
        """Detector name for identification."""
        ...

    async def analyze(self, artifact: Artifact) -> list[AmbientAlert]:
        """Analyze an artifact for issues.

        Args:
            artifact: The code artifact to analyze

        Returns:
            List of alerts found (empty if no issues)
        """
        ...


@dataclass
class SecretPatternDetector:
    """Detects potential secrets and sensitive data in code.

    Looks for patterns that commonly indicate hardcoded secrets,
    API keys, passwords, and other sensitive information.
    """

    name: str = "secret_detector"

    # Common secret patterns (regex)
    _patterns: list[tuple[str, str]] = field(default_factory=lambda: [
        (r'["\']?(?:api[_-]?key|apikey)["\']?\s*[=:]\s*["\'][^"\']{10,}["\']', "API key"),
        (r'["\']?(?:secret|password|passwd|pwd)["\']?\s*[=:]\s*["\'][^"\']{6,}["\']', "Password/secret"),
        (r'["\']?(?:token|auth[_-]?token)["\']?\s*[=:]\s*["\'][^"\']{10,}["\']', "Token"),
        (r'(?:AWS|aws)[_-]?(?:ACCESS|SECRET)[_-]?(?:KEY|ID)\s*[=:]\s*["\']?[A-Z0-9]{16,}', "AWS credential"),
        (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', "Private key"),
        (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}', "GitHub token"),
        (r'sk-[A-Za-z0-9]{32,}', "OpenAI API key"),
        (r'xox[baprs]-[A-Za-z0-9-]{10,}', "Slack token"),
    ])

    async def analyze(self, artifact: Artifact) -> list[AmbientAlert]:
        """Analyze artifact for potential secrets."""
        alerts: list[AmbientAlert] = []

        # Skip binary files and certain file types
        if artifact.path.suffix in ('.pyc', '.pyo', '.so', '.dll', '.exe'):
            return alerts

        content = artifact.content
        lines = content.split('\n')

        for pattern, secret_type in self._patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    alerts.append(AmbientAlert(
                        alert_type=AmbientAlertType.SECURITY_CONCERN,
                        severity=AlertSeverity.ERROR,
                        message=f"Potential {secret_type} found in code",
                        file_path=str(artifact.path),
                        line_number=line_num,
                        suggested_fix=f"Move {secret_type} to environment variable or secrets manager",
                        context={"pattern": pattern, "secret_type": secret_type},
                    ))
                    break  # One alert per pattern per file

        return alerts


@dataclass
class PerformancePatternDetector:
    """Detects potential performance issues in code.

    Looks for common anti-patterns that may cause performance problems.
    """

    name: str = "performance_detector"

    # Performance anti-patterns
    _patterns: list[tuple[str, str, str]] = field(default_factory=lambda: [
        (
            r'for\s+\w+\s+in\s+\w+\.keys\(\)',
            "Iterating over .keys() is slower than iterating over dict directly",
            "Use `for key in my_dict:` instead"
        ),
        (
            r'if\s+\w+\s+in\s+\w+\.keys\(\)',
            "Checking membership in .keys() is slower than checking dict directly",
            "Use `if key in my_dict:` instead"
        ),
        (
            r'\+\s*=\s*["\'][^"\']*["\']',
            "String concatenation in loop may be inefficient",
            "Consider using list and join for repeated string building"
        ),
        (
            r'import\s+\*',
            "Wildcard import may slow down module loading",
            "Use explicit imports instead"
        ),
        (
            r'\.read\(\)',
            "Reading entire file into memory may cause issues with large files",
            "Consider using chunked reading or line-by-line processing"
        ),
    ])

    async def analyze(self, artifact: Artifact) -> list[AmbientAlert]:
        """Analyze artifact for performance issues."""
        alerts: list[AmbientAlert] = []

        # Only analyze Python files
        if artifact.path.suffix not in ('.py', '.pyx'):
            return alerts

        content = artifact.content
        lines = content.split('\n')

        for pattern, issue, fix in self._patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    alerts.append(AmbientAlert(
                        alert_type=AmbientAlertType.OPTIMIZATION,
                        severity=AlertSeverity.INFO,
                        message=issue,
                        file_path=str(artifact.path),
                        line_number=line_num,
                        suggested_fix=fix,
                    ))

        return alerts


@dataclass
class StyleViolationDetector:
    """Detects common style violations.

    Looks for patterns that violate common style guidelines.
    """

    name: str = "style_detector"

    _max_line_length: int = 100
    _max_function_length: int = 50

    async def analyze(self, artifact: Artifact) -> list[AmbientAlert]:
        """Analyze artifact for style violations."""
        alerts: list[AmbientAlert] = []

        # Only analyze Python files
        if artifact.path.suffix not in ('.py', '.pyx'):
            return alerts

        content = artifact.content
        lines = content.split('\n')

        # Check line length
        for line_num, line in enumerate(lines, 1):
            if len(line) > self._max_line_length:
                alerts.append(AmbientAlert(
                    alert_type=AmbientAlertType.STYLE_VIOLATION,
                    severity=AlertSeverity.INFO,
                    message=f"Line exceeds {self._max_line_length} characters ({len(line)} chars)",
                    file_path=str(artifact.path),
                    line_number=line_num,
                    suggested_fix=f"Break line to stay under {self._max_line_length} characters",
                ))
                if len(alerts) >= 3:  # Limit to 3 line length warnings
                    break

        # Check for TODO/FIXME/HACK comments
        todo_pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX):', re.IGNORECASE)
        for line_num, line in enumerate(lines, 1):
            match = todo_pattern.search(line)
            if match:
                alerts.append(AmbientAlert(
                    alert_type=AmbientAlertType.DOCUMENTATION,
                    severity=AlertSeverity.INFO,
                    message=f"{match.group(1)} comment found",
                    file_path=str(artifact.path),
                    line_number=line_num,
                    suggested_fix="Address the TODO/FIXME or create a tracking issue",
                ))

        return alerts


@dataclass
class AmbientRegistry:
    """Registry for ambient detectors.

    Manages detector registration and coordinates analysis.

    Thread-safe for concurrent analysis.
    """

    _detectors: list[AmbientDetector] = field(default_factory=list, init=False)
    _suppressed: set[str] = field(default_factory=set, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        # Register built-in detectors
        self.register(SecretPatternDetector())
        self.register(PerformancePatternDetector())
        self.register(StyleViolationDetector())

    def register(self, detector: AmbientDetector) -> None:
        """Register a detector.

        Args:
            detector: Detector to register
        """
        with self._lock:
            self._detectors.append(detector)
        logger.debug("Registered ambient detector: %s", detector.name)

    def unregister(self, name: str) -> bool:
        """Unregister a detector by name.

        Args:
            name: Name of detector to unregister

        Returns:
            True if detector was found and removed
        """
        with self._lock:
            original_len = len(self._detectors)
            self._detectors = [d for d in self._detectors if d.name != name]
            return len(self._detectors) < original_len

    def suppress_alert_type(self, alert_type: AmbientAlertType) -> None:
        """Suppress a type of alert.

        Args:
            alert_type: Alert type to suppress
        """
        with self._lock:
            self._suppressed.add(alert_type.value)
        logger.debug("Suppressed alert type: %s", alert_type.value)

    def unsuppress_alert_type(self, alert_type: AmbientAlertType) -> None:
        """Unsuppress a type of alert.

        Args:
            alert_type: Alert type to unsuppress
        """
        with self._lock:
            self._suppressed.discard(alert_type.value)

    def is_suppressed(self, alert_type: AmbientAlertType) -> bool:
        """Check if alert type is suppressed."""
        return alert_type.value in self._suppressed

    async def analyze(self, artifact: Artifact) -> list[AmbientAlert]:
        """Analyze artifact with all registered detectors.

        Args:
            artifact: Artifact to analyze

        Returns:
            List of alerts from all detectors (filtered by suppression)
        """
        all_alerts: list[AmbientAlert] = []

        with self._lock:
            detectors = list(self._detectors)
            suppressed = set(self._suppressed)

        for detector in detectors:
            try:
                alerts = await detector.analyze(artifact)
                # Filter suppressed alerts
                for alert in alerts:
                    if alert.alert_type.value not in suppressed:
                        all_alerts.append(alert)
            except Exception as e:
                logger.warning(
                    "Detector %s failed on %s: %s",
                    detector.name,
                    artifact.path,
                    e,
                )

        return all_alerts

    def list_detectors(self) -> list[str]:
        """List registered detector names."""
        with self._lock:
            return [d.name for d in self._detectors]

    def list_suppressed(self) -> list[str]:
        """List suppressed alert types."""
        with self._lock:
            return list(self._suppressed)
