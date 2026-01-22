# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Tests for security monitor (RFC-089)."""

import pytest

from sunwell.security.analyzer import PermissionScope
from sunwell.security.monitor import (
    SecurityClassification,
    SecurityMonitor,
    SecurityViolation,
)


class TestSecurityClassification:
    """Tests for SecurityClassification."""

    def test_safe_classification(self):
        """Safe classification is not a violation."""
        result = SecurityClassification(
            classification="safe",
            violation=False,
            detection_method="deterministic",
        )
        assert not result.violation
        assert result.confidence == 1.0

    def test_violation_classification(self):
        """Violation classification includes evidence."""
        result = SecurityClassification(
            classification="credential_leak",
            violation=True,
            violation_type="credential_leak",
            evidence="AWS key detected",
            detection_method="deterministic",
        )
        assert result.violation
        assert result.violation_type == "credential_leak"

    def test_to_dict(self):
        """Serialization works correctly."""
        result = SecurityClassification(
            classification="safe",
            violation=False,
            detection_method="deterministic",
        )
        data = result.to_dict()
        assert data["classification"] == "safe"
        assert data["violation"] is False


class TestSecurityMonitor:
    """Tests for SecurityMonitor."""

    def test_detects_credential_leak(self):
        """Detects credential leaks in output."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "Here's the API key: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "credential_leak"
        assert result.detection_method == "deterministic"

    def test_detects_path_traversal(self):
        """Detects path traversal attempts."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "Reading file: ../../../etc/passwd"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "path_traversal"

    def test_detects_shell_injection_backticks(self):
        """Detects backtick shell injection."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "The result is `whoami`"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "shell_injection"

    def test_detects_shell_injection_subshell(self):
        """Detects $() subshell injection."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "User: $(id -un)"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "shell_injection"

    def test_detects_pii_email(self):
        """Detects email PII exposure."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "Contact: john.doe@example.com"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "pii_exposure"

    def test_detects_pii_ssn(self):
        """Detects SSN PII exposure."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "SSN: 123-45-6789"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "pii_exposure"

    def test_detects_pii_credit_card(self):
        """Detects credit card PII exposure."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "Card: 4111-1111-1111-1111"
        result = monitor.classify_output_deterministic(output, permissions)

        assert result.violation
        assert result.classification == "pii_exposure"

    def test_allows_pii_when_permitted(self):
        """Allows PII when explicitly permitted."""
        monitor = SecurityMonitor()
        # PII in env_read indicates explicit permission
        permissions = PermissionScope(
            env_read=frozenset(["PII_HANDLING_ENABLED"])
        )

        output = "Contact: john.doe@example.com"
        result = monitor.classify_output_deterministic(output, permissions)

        # Should still classify as safe because pii is in permissions
        assert result.classification == "safe"

    def test_clean_output_is_safe(self):
        """Clean output classifies as safe."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        output = "Build completed successfully. 42 tests passed."
        result = monitor.classify_output_deterministic(output, permissions)

        assert not result.violation
        assert result.classification == "safe"


class TestSecurityMonitorScan:
    """Tests for batch scanning."""

    def test_scan_finds_multiple_violations(self):
        """Batch scan finds multiple violations."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        content = """
        Config:
          api_key: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
          ssh_key: -----BEGIN RSA PRIVATE KEY-----
          path: ../../../etc/passwd
        """

        violations = monitor.scan_content(content, permissions)

        # Should find credential leak (2x) + path traversal
        assert len(violations) >= 3

        types = [v.type for v in violations]
        assert "credential_leak" in types
        assert "path_traversal" in types

    def test_scan_empty_content(self):
        """Scanning empty content returns no violations."""
        monitor = SecurityMonitor()
        permissions = PermissionScope()

        violations = monitor.scan_content("", permissions)
        assert len(violations) == 0


class TestSecurityViolation:
    """Tests for SecurityViolation."""

    def test_to_dict_truncates_content(self):
        """Content is truncated in serialization."""
        violation = SecurityViolation(
            type="test",
            content="x" * 500,
            position=0,
            detection_method="deterministic",
        )

        data = violation.to_dict()
        assert len(data["content"]) <= 200

    def test_includes_timestamp(self):
        """Violation includes timestamp."""
        violation = SecurityViolation(
            type="test",
            content="test",
            position=0,
            detection_method="deterministic",
        )

        assert violation.timestamp is not None
        data = violation.to_dict()
        assert "timestamp" in data
