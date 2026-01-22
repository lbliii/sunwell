# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Tests for security analyzer (RFC-089)."""

import pytest

from sunwell.guardrails.types import ActionRisk
from sunwell.security.analyzer import (
    PermissionAnalyzer,
    PermissionScope,
    RiskAssessment,
    RiskWeights,
)
from sunwell.skills.graph import SkillGraph
from sunwell.skills.types import Skill, SkillType


class TestPermissionScope:
    """Tests for PermissionScope."""

    def test_empty_scope(self):
        """Empty scope has no permissions."""
        scope = PermissionScope()
        assert scope.is_empty()
        assert scope.filesystem_read == frozenset()
        assert scope.network_deny == frozenset(["*"])

    def test_merge_scopes(self):
        """Merging scopes combines permissions."""
        scope1 = PermissionScope(
            filesystem_read=frozenset(["/app/src/*"]),
            shell_allow=frozenset(["docker build"]),
        )
        scope2 = PermissionScope(
            filesystem_read=frozenset(["/app/config/*"]),
            network_allow=frozenset(["registry.internal:5000"]),
        )

        merged = scope1.merge_with(scope2)

        assert "/app/src/*" in merged.filesystem_read
        assert "/app/config/*" in merged.filesystem_read
        assert "docker build" in merged.shell_allow
        assert "registry.internal:5000" in merged.network_allow

    def test_to_dict_roundtrip(self):
        """Serialization preserves data."""
        scope = PermissionScope(
            filesystem_read=frozenset(["/app/src/*"]),
            filesystem_write=frozenset(["/tmp/*"]),
            network_allow=frozenset(["localhost:8080"]),
        )

        data = scope.to_dict()
        restored = PermissionScope.from_dict(data)

        assert restored.filesystem_read == scope.filesystem_read
        assert restored.filesystem_write == scope.filesystem_write
        assert restored.network_allow == scope.network_allow


class TestRiskAssessment:
    """Tests for RiskAssessment."""

    def test_low_risk_maps_to_safe(self):
        """Low risk maps to ActionRisk.SAFE."""
        risk = RiskAssessment(level="low", score=0.1)
        assert risk.to_action_risk() == ActionRisk.SAFE

    def test_medium_risk_maps_to_moderate(self):
        """Medium risk maps to ActionRisk.MODERATE."""
        risk = RiskAssessment(level="medium", score=0.3)
        assert risk.to_action_risk() == ActionRisk.MODERATE

    def test_high_risk_maps_to_dangerous(self):
        """High risk maps to ActionRisk.DANGEROUS."""
        risk = RiskAssessment(level="high", score=0.6)
        assert risk.to_action_risk() == ActionRisk.DANGEROUS

    def test_critical_risk_maps_to_forbidden(self):
        """Critical risk maps to ActionRisk.FORBIDDEN."""
        risk = RiskAssessment(level="critical", score=0.9)
        assert risk.to_action_risk() == ActionRisk.FORBIDDEN


class TestPermissionAnalyzer:
    """Tests for PermissionAnalyzer."""

    def test_credential_scanning_aws_key(self):
        """Detects AWS access keys."""
        analyzer = PermissionAnalyzer()
        content = "AWS key: AKIAIOSFODNN7EXAMPLE"
        findings = analyzer.scan_for_credentials(content)

        assert len(findings) == 1
        assert findings[0][0] == "AWS_KEY"

    def test_credential_scanning_github_token(self):
        """Detects GitHub tokens."""
        analyzer = PermissionAnalyzer()
        content = "token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        findings = analyzer.scan_for_credentials(content)

        assert len(findings) == 1
        assert findings[0][0] == "GITHUB_TOKEN"

    def test_credential_scanning_private_key(self):
        """Detects private keys."""
        analyzer = PermissionAnalyzer()
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA"
        findings = analyzer.scan_for_credentials(content)

        assert len(findings) == 1
        assert findings[0][0] == "PRIVATE_KEY"

    def test_credential_scanning_no_matches(self):
        """Returns empty for clean content."""
        analyzer = PermissionAnalyzer()
        content = "This is just regular code without any secrets"
        findings = analyzer.scan_for_credentials(content)

        assert len(findings) == 0

    def test_is_internal_localhost(self):
        """Localhost is internal."""
        analyzer = PermissionAnalyzer()
        assert analyzer._is_internal("localhost:8080")
        assert analyzer._is_internal("127.0.0.1:3000")

    def test_is_internal_private_networks(self):
        """Private network ranges are internal."""
        analyzer = PermissionAnalyzer()
        assert analyzer._is_internal("10.0.0.1:443")
        assert analyzer._is_internal("192.168.1.1:80")

    def test_is_internal_external_hosts(self):
        """External hosts are not internal."""
        analyzer = PermissionAnalyzer()
        assert not analyzer._is_internal("api.github.com:443")
        assert not analyzer._is_internal("8.8.8.8:53")

    def test_risk_weights_customization(self):
        """Custom weights affect risk calculation."""
        # Higher weight for filesystem writes
        weights = RiskWeights(filesystem_write=0.2)
        analyzer = PermissionAnalyzer(weights=weights)

        scope = PermissionScope(
            filesystem_write=frozenset(["/tmp/a", "/tmp/b", "/tmp/c"])
        )

        risk = analyzer._compute_risk(scope, [])

        # 3 writes * 0.2 = 0.6 → high risk (>= 0.5)
        assert risk.level in ("high", "critical")


class TestPermissionAnalyzerDeterministicChecks:
    """Tests for deterministic risk detection."""

    def test_detects_credential_path_access(self):
        """Flags access to credential paths."""
        analyzer = PermissionAnalyzer()

        scope = PermissionScope(
            filesystem_read=frozenset(["~/.ssh/id_rsa"])
        )

        # Create a minimal skill for testing
        skill = Skill(
            name="test-skill",
            description="Test skill",
            skill_type=SkillType.INLINE,
            instructions="Test",
            permissions=scope.to_dict(),
        )

        flags = analyzer._check_risks_deterministic(skill, scope)

        assert any("CREDENTIAL_ACCESS" in f for f in flags)
        assert any("~/.ssh/id_rsa" in f for f in flags)

    def test_detects_dangerous_commands(self):
        """Flags dangerous shell commands."""
        analyzer = PermissionAnalyzer()

        scope = PermissionScope(
            shell_allow=frozenset(["rm -rf /"])
        )

        skill = Skill(
            name="test-skill",
            description="Test skill",
            skill_type=SkillType.INLINE,
            instructions="Test",
            permissions=scope.to_dict(),
        )

        flags = analyzer._check_risks_deterministic(skill, scope)

        assert any("DANGEROUS_COMMAND" in f for f in flags)

    def test_detects_external_network(self):
        """Flags external network access."""
        analyzer = PermissionAnalyzer()

        scope = PermissionScope(
            network_allow=frozenset(["api.external.com:443"])
        )

        skill = Skill(
            name="test-skill",
            description="Test skill",
            skill_type=SkillType.INLINE,
            instructions="Test",
            permissions=scope.to_dict(),
        )

        flags = analyzer._check_risks_deterministic(skill, scope)

        assert any("EXTERNAL_NETWORK" in f for f in flags)

    def test_safe_permissions_no_flags(self):
        """Safe permissions produce no flags."""
        analyzer = PermissionAnalyzer()

        scope = PermissionScope(
            filesystem_read=frozenset(["/app/src/*"]),
            network_allow=frozenset(["localhost:3000"]),
            shell_allow=frozenset(["npm test"]),
        )

        skill = Skill(
            name="test-skill",
            description="Test skill",
            skill_type=SkillType.INLINE,
            instructions="Test",
            permissions=scope.to_dict(),
        )

        flags = analyzer._check_risks_deterministic(skill, scope)

        assert len(flags) == 0


class TestRecommendations:
    """Tests for security recommendations."""

    def test_credential_recommendations(self):
        """Generates recommendations for credential access."""
        analyzer = PermissionAnalyzer()

        flags = ["CREDENTIAL_ACCESS: test reads ~/.aws/credentials"]
        recommendations = analyzer._generate_recommendations(flags)

        assert any("IAM role" in r for r in recommendations)

    def test_dangerous_command_recommendations(self):
        """Generates recommendations for dangerous commands."""
        analyzer = PermissionAnalyzer()

        flags = ["DANGEROUS_COMMAND: test allows 'rm -rf'"]
        recommendations = analyzer._generate_recommendations(flags)

        assert any("targeted delete" in r for r in recommendations)

    def test_external_network_recommendations(self):
        """Generates recommendations for external network."""
        analyzer = PermissionAnalyzer()

        flags = ["EXTERNAL_NETWORK: test connects to api.example.com"]
        recommendations = analyzer._generate_recommendations(flags)

        assert any("internal" in r.lower() or "allowlist" in r.lower() for r in recommendations)
