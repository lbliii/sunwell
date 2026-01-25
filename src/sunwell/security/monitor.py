# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Real-time security monitoring (RFC-089).

Monitors skill execution for security violations using a two-phase strategy:
1. Deterministic pattern matching (fast, reliable, no false negatives)
2. LLM classification (catches novel patterns, may have false positives)

Deterministic checks ALWAYS run. LLM is optional and runs only if
deterministic checks pass but paranoid_mode is enabled.
"""


import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sunwell.security.analyzer import PermissionAnalyzer, PermissionScope

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# SECURITY CLASSIFICATIONS
# =============================================================================


SECURITY_CLASSIFICATIONS = [
    "safe",
    "credential_leak",
    "path_traversal",
    "shell_injection",
    "network_exfil",
    "pii_exposure",
    "permission_escalation",
]


@dataclass(frozen=True, slots=True)
class SecurityClassification:
    """Result of security classification."""

    classification: str
    """One of SECURITY_CLASSIFICATIONS."""

    violation: bool
    """True if this is a security violation."""

    violation_type: str | None = None
    """Type of violation if violation is True."""

    evidence: str | None = None
    """Evidence supporting the classification."""

    confidence: float = 1.0
    """Confidence in the classification (0.0-1.0)."""

    detection_method: str = "deterministic"
    """Method used: 'deterministic' or 'llm'."""

    def to_dict(self) -> dict:
        """Serialize for JSON export."""
        return {
            "classification": self.classification,
            "violation": self.violation,
            "violation_type": self.violation_type,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
        }


@dataclass(frozen=True, slots=True)
class SecurityViolation:
    """A security violation detected during execution."""

    type: str
    """Type of violation (from SECURITY_CLASSIFICATIONS)."""

    content: str
    """Content that triggered the violation."""

    position: int
    """Position in output where violation was detected."""

    detection_method: str
    """How the violation was detected."""

    skill_name: str = ""
    """Name of the skill that caused the violation."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the violation was detected."""

    def to_dict(self) -> dict:
        """Serialize for JSON export."""
        return {
            "type": self.type,
            "content": self.content[:200],  # Truncate for safety
            "position": self.position,
            "detection_method": self.detection_method,
            "skill_name": self.skill_name,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# SECURITY MONITOR
# =============================================================================


class SecurityMonitor:
    """Real-time monitoring of skill execution for security violations.

    Uses a two-phase detection strategy:
    1. Deterministic pattern matching (fast, reliable, no false negatives)
    2. LLM classification (catches novel patterns, may have false positives)

    Deterministic checks ALWAYS run. LLM is optional and runs only if
    deterministic checks pass but paranoid_mode is enabled.
    """

    # Deterministic patterns for common violations
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.\/|\.\.\\|%2e%2e|%252e")

    # Pre-compiled pattern for JSON extraction in LLM responses
    _JSON_EXTRACT_PATTERN = re.compile(r"\{[^}]+\}")

    SHELL_INJECTION_PATTERNS = [
        re.compile(r"`[^`]+`"),  # Backtick execution
        re.compile(r"\$\([^)]+\)"),  # $() subshell
        re.compile(r";\s*\w+"),  # Command chaining
        re.compile(r"\|\s*\w+"),  # Pipe to command
        re.compile(r"&&\s*\w+"),  # AND chaining
        re.compile(r"\|\|\s*\w+"),  # OR chaining
    ]

    PII_PATTERNS = [
        (
            "EMAIL",
            re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ),
        (
            "PHONE",
            re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        ),
        (
            "SSN",
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        ),
        (
            "CREDIT_CARD",
            re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        ),
    ]

    def __init__(
        self,
        classifier_model: ModelProtocol | None = None,
        paranoid_mode: bool = False,
    ):
        """Initialize security monitor.

        Args:
            classifier_model: Optional LLM for Phase 2 classification
            paranoid_mode: If True, run LLM classification even when
                          deterministic checks pass (slower, more thorough)
        """
        self.classifier = classifier_model
        self.paranoid_mode = paranoid_mode
        self._analyzer = PermissionAnalyzer()

    def classify_output_deterministic(
        self,
        output: str,
        declared_permissions: PermissionScope,
    ) -> SecurityClassification:
        """Phase 1: Deterministic security classification.

        Fast, reliable, no false negatives for known patterns.
        Returns immediately if violation found.

        Args:
            output: The output to classify
            declared_permissions: Permissions declared by the skill

        Returns:
            SecurityClassification result
        """
        # 1. Credential leak (uses PermissionAnalyzer patterns)
        credential_findings = self._analyzer.scan_for_credentials(output)
        if credential_findings:
            return SecurityClassification(
                classification="credential_leak",
                violation=True,
                violation_type="credential_leak",
                evidence=f"Found: {credential_findings[0][0]}",
                detection_method="deterministic",
            )

        # 2. Path traversal
        if self.PATH_TRAVERSAL_PATTERN.search(output):
            return SecurityClassification(
                classification="path_traversal",
                violation=True,
                violation_type="path_traversal",
                evidence="Path traversal sequence detected",
                detection_method="deterministic",
            )

        # 3. Shell injection
        for pattern in self.SHELL_INJECTION_PATTERNS:
            match = pattern.search(output)
            if match:
                return SecurityClassification(
                    classification="shell_injection",
                    violation=True,
                    violation_type="shell_injection",
                    evidence=f"Shell metacharacter: {match.group()[:20]}",
                    detection_method="deterministic",
                )

        # 4. PII exposure (check against permissions)
        for pii_name, pattern in self.PII_PATTERNS:
            if pattern.search(output):
                # Only flag if PII handling not explicitly permitted
                if "pii" not in str(declared_permissions.env_read).lower():
                    return SecurityClassification(
                        classification="pii_exposure",
                        violation=True,
                        violation_type="pii_exposure",
                        evidence=f"Potential {pii_name} detected",
                        detection_method="deterministic",
                    )

        # No deterministic violations found
        return SecurityClassification(
            classification="safe",
            violation=False,
            detection_method="deterministic",
        )

    async def classify_output(
        self,
        output: str,
        declared_permissions: PermissionScope,
    ) -> SecurityClassification:
        """Full security classification (Phase 1 + optional Phase 2).

        Runs deterministic checks first. If clean and paranoid_mode
        is enabled (and classifier available), runs LLM classification.

        Args:
            output: The output to classify
            declared_permissions: Permissions declared by the skill

        Returns:
            SecurityClassification result
        """
        # Phase 1: Deterministic (always runs)
        result = self.classify_output_deterministic(output, declared_permissions)
        if result.violation:
            return result

        # Phase 2: LLM classification (optional)
        if self.paranoid_mode and self.classifier:
            llm_result = await self._classify_with_llm(output, declared_permissions)
            if llm_result.violation:
                # Mark as LLM-detected (lower confidence)
                return SecurityClassification(
                    classification=llm_result.classification,
                    violation=True,
                    violation_type=llm_result.violation_type,
                    evidence=llm_result.evidence,
                    confidence=0.7,  # LLM classifications have lower confidence
                    detection_method="llm",
                )

        return result

    async def _classify_with_llm(
        self,
        output: str,
        declared_permissions: PermissionScope,
    ) -> SecurityClassification:
        """Phase 2: LLM-based classification for novel patterns.

        Args:
            output: The output to classify
            declared_permissions: Permissions declared by the skill

        Returns:
            SecurityClassification result
        """
        if not self.classifier:
            return SecurityClassification(
                classification="safe",
                violation=False,
                detection_method="llm",
            )

        prompt = f"""Analyze this AI agent output for security issues.

Declared permissions:
- Filesystem read: {declared_permissions.filesystem_read}
- Filesystem write: {declared_permissions.filesystem_write}
- Network: {declared_permissions.network_allow}
- Shell: {declared_permissions.shell_allow}

Output to analyze:
---
{output[:2000]}
---

Check for:
1. credential_leak: Contains API keys, passwords, tokens, private keys
2. path_traversal: Accesses files outside declared scope (../, /etc/, ~/)
3. shell_injection: Embedded commands, backticks, $() constructs
4. network_exfil: Contacts hosts not in declared network permissions
5. pii_exposure: Contains emails, phone numbers, SSNs, addresses
6. permission_escalation: Attempts to gain more access than declared

Respond with JSON: {{"classification": "safe|<type>", "evidence": "brief explanation"}}
"""

        try:
            from sunwell.models.protocol import Message

            response = await self.classifier.generate(
                prompt=(Message(role="user", content=prompt),)
            )

            return self._parse_classification(response.content)

        except Exception:
            # On error, assume safe (fail open for LLM)
            return SecurityClassification(
                classification="safe",
                violation=False,
                detection_method="llm",
            )

    def _parse_classification(self, response: str) -> SecurityClassification:
        """Parse LLM classification response.

        Args:
            response: Raw LLM response

        Returns:
            SecurityClassification result
        """
        import json

        try:
            # Try to extract JSON from response
            json_match = self._JSON_EXTRACT_PATTERN.search(response)
            if json_match:
                data = json.loads(json_match.group())
                classification = data.get("classification", "safe")
                evidence = data.get("evidence", "")

                is_violation = classification != "safe"
                return SecurityClassification(
                    classification=classification,
                    violation=is_violation,
                    violation_type=classification if is_violation else None,
                    evidence=evidence if is_violation else None,
                    confidence=0.7,  # LLM has lower confidence
                    detection_method="llm",
                )
        except (json.JSONDecodeError, KeyError):
            pass

        # Default to safe if parsing fails
        return SecurityClassification(
            classification="safe",
            violation=False,
            detection_method="llm",
        )

    async def monitor_stream(
        self,
        stream: AsyncIterator[str],
        permissions: PermissionScope,
        on_violation: Callable[[SecurityViolation], None],
        skill_name: str = "",
    ) -> AsyncIterator[str]:
        """Monitor streaming output for security violations.

        Runs deterministic checks synchronously on each chunk.
        LLM classification (if enabled) runs periodically.

        Args:
            stream: Async iterator of output chunks
            permissions: Declared permissions
            on_violation: Callback when violation detected
            skill_name: Name of the skill being monitored

        Yields:
            Output chunks (passthrough)
        """
        buffer: list[str] = []

        async for chunk in stream:
            buffer.append(chunk)
            yield chunk

            # Deterministic check on every chunk (fast)
            text = "".join(buffer)
            result = self.classify_output_deterministic(text, permissions)

            if result.violation:
                on_violation(
                    SecurityViolation(
                        type=result.violation_type or "unknown",
                        content=text[-200:],  # Last 200 chars for context
                        position=len(text),
                        detection_method=result.detection_method,
                        skill_name=skill_name,
                    )
                )

            # LLM check periodically (slow, optional)
            if self.paranoid_mode and self.classifier and len(text) > 500:
                llm_result = await self._classify_with_llm(text, permissions)
                if llm_result.violation:
                    on_violation(
                        SecurityViolation(
                            type=llm_result.violation_type or "unknown",
                            content=text[-200:],
                            position=len(text),
                            detection_method="llm",
                            skill_name=skill_name,
                        )
                    )
                # Reset buffer after LLM check to avoid redundant checks
                buffer = buffer[-5:]  # Keep some context

    def scan_content(
        self,
        content: str,
        permissions: PermissionScope,
    ) -> list[SecurityViolation]:
        """Scan content for all violations (batch mode).

        Args:
            content: Content to scan
            permissions: Declared permissions

        Returns:
            List of violations found
        """
        violations: list[SecurityViolation] = []

        # Credential leaks
        credential_findings = self._analyzer.scan_for_credentials(content)
        for cred_type, redacted in credential_findings:
            violations.append(
                SecurityViolation(
                    type="credential_leak",
                    content=f"{cred_type}: {redacted}",
                    position=0,
                    detection_method="deterministic",
                )
            )

        # Path traversal
        for match in self.PATH_TRAVERSAL_PATTERN.finditer(content):
            violations.append(
                SecurityViolation(
                    type="path_traversal",
                    content=match.group(),
                    position=match.start(),
                    detection_method="deterministic",
                )
            )

        # Shell injection
        for pattern in self.SHELL_INJECTION_PATTERNS:
            for match in pattern.finditer(content):
                violations.append(
                    SecurityViolation(
                        type="shell_injection",
                        content=match.group()[:50],
                        position=match.start(),
                        detection_method="deterministic",
                    )
                )

        # PII exposure
        if "pii" not in str(permissions.env_read).lower():
            for pii_name, pattern in self.PII_PATTERNS:
                for match in pattern.finditer(content):
                    violations.append(
                        SecurityViolation(
                            type="pii_exposure",
                            content=f"{pii_name} detected",
                            position=match.start(),
                            detection_method="deterministic",
                        )
                    )

        return violations
