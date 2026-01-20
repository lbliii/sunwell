"""Tests for Autonomy Guardrails (RFC-048).

Tests action classification, scope limits, trust zones, and escalation.
"""

import pytest
from pathlib import Path

from sunwell.guardrails import (
    ActionClassifier,
    ActionRisk,
    TrustLevel,
    ScopeTracker,
    ScopeLimits,
    TrustZoneEvaluator,
    EscalationHandler,
    EscalationReason,
    VerificationGate,
    VerificationThresholds,
    GuardrailConfig,
    Action,
    FileChange,
)


# =============================================================================
# Action Classifier Tests
# =============================================================================


class TestActionClassifier:
    """Test action classification logic."""

    def test_forbidden_env_file(self):
        """Ensure .env files are always FORBIDDEN."""
        classifier = ActionClassifier(trust_level=TrustLevel.FULL)
        result = classifier.classify(
            Action(action_type="file_write", path=".env.production")
        )
        assert result.risk == ActionRisk.FORBIDDEN

    def test_forbidden_key_file(self):
        """Ensure .key files are FORBIDDEN."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="secrets/api.key")
        )
        assert result.risk == ActionRisk.FORBIDDEN

    def test_safe_zone_test_files(self):
        """Tests in tests/ are SAFE."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="tests/test_foo.py")
        )
        assert result.risk == ActionRisk.SAFE
        assert result.escalation_required is False

    def test_safe_zone_docs(self):
        """Documentation files are SAFE."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="docs/api.md")
        )
        assert result.risk == ActionRisk.SAFE

    def test_dangerous_auth_path(self):
        """Auth paths are DANGEROUS."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="src/auth/oauth.py")
        )
        assert result.risk == ActionRisk.DANGEROUS
        assert result.escalation_required is True

    def test_dangerous_migrations(self):
        """Migration files are DANGEROUS."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="src/migrations/0023_add_users.py")
        )
        assert result.risk == ActionRisk.DANGEROUS

    def test_moderate_source_file(self):
        """Regular source files are MODERATE."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="file_write", path="src/utils/helpers.py")
        )
        assert result.risk == ActionRisk.MODERATE

    def test_shell_test_command_safe(self):
        """Test commands are SAFE."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="shell_exec", command="pytest tests/")
        )
        assert result.risk == ActionRisk.SAFE

    def test_shell_rm_dangerous(self):
        """rm commands that could delete everything are FORBIDDEN."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="shell_exec", command="rm -rf /tmp/test")
        )
        # rm -rf / is in forbidden patterns, so rm -rf triggers FORBIDDEN
        assert result.risk == ActionRisk.FORBIDDEN

    def test_shell_git_push_dangerous(self):
        """git push is DANGEROUS."""
        classifier = ActionClassifier()
        result = classifier.classify(
            Action(action_type="shell_exec", command="git push origin main")
        )
        assert result.risk == ActionRisk.DANGEROUS

    def test_trust_level_affects_escalation(self):
        """Trust level affects escalation requirements."""
        # GUARDED: MODERATE escalates
        classifier_guarded = ActionClassifier(trust_level=TrustLevel.GUARDED)
        result_guarded = classifier_guarded.classify(
            Action(action_type="file_write", path="src/module.py")
        )
        assert result_guarded.escalation_required is True

        # SUPERVISED: MODERATE doesn't escalate
        classifier_supervised = ActionClassifier(trust_level=TrustLevel.SUPERVISED)
        result_supervised = classifier_supervised.classify(
            Action(action_type="file_write", path="src/module.py")
        )
        assert result_supervised.escalation_required is False


# =============================================================================
# Scope Tracker Tests
# =============================================================================


class TestScopeTracker:
    """Test scope limit enforcement."""

    def test_per_goal_file_limit(self):
        """Reject goals exceeding file limit."""
        tracker = ScopeTracker(ScopeLimits(max_files_per_goal=5))
        changes = [
            FileChange(path=Path(f"src/file{i}.py"), lines_added=10)
            for i in range(10)
        ]
        result = tracker.check_goal(changes)
        assert not result.passed
        assert "10 files" in result.reason
        assert result.limit_type == "files_per_goal"

    def test_per_goal_line_limit(self):
        """Reject goals exceeding line limit."""
        tracker = ScopeTracker(ScopeLimits(max_lines_changed_per_goal=100))
        changes = [
            FileChange(path=Path("src/big_file.py"), lines_added=500, lines_removed=100)
        ]
        result = tracker.check_goal(changes)
        assert not result.passed
        assert "600 lines" in result.reason
        assert result.limit_type == "lines_per_goal"

    def test_session_file_accumulation(self):
        """Track cumulative session file usage."""
        # Disable require_tests to isolate file limit testing
        tracker = ScopeTracker(ScopeLimits(
            max_files_per_session=20,
            require_tests_for_source_changes=False,
        ))

        # Complete 3 goals touching 5 unique files each
        for i in range(3):
            changes = [
                FileChange(path=Path(f"src/goal{i}_file{j}.py"), lines_added=10)
                for j in range(5)
            ]
            check = tracker.check_goal(changes)
            assert check.passed
            tracker.record_goal_completion(changes)

        # 4th goal with 10 more files should fail (15 + 10 > 20)
        new_changes = [
            FileChange(path=Path(f"src/goal4_file{j}.py"), lines_added=10)
            for j in range(10)
        ]
        result = tracker.check_goal(new_changes)
        assert not result.passed
        assert result.limit_type == "files_per_session"

    def test_require_tests_for_source(self):
        """Source changes require test changes."""
        tracker = ScopeTracker(
            ScopeLimits(require_tests_for_source_changes=True)
        )

        # Source only - should fail
        source_only = [FileChange(path=Path("src/module.py"), lines_added=50)]
        result = tracker.check_goal(source_only)
        assert not result.passed
        assert result.limit_type == "require_tests"

        # Source + tests - should pass
        with_tests = [
            FileChange(path=Path("src/module.py"), lines_added=50),
            FileChange(path=Path("tests/test_module.py"), lines_added=30),
        ]
        result = tracker.check_goal(with_tests)
        assert result.passed

    def test_session_stats(self):
        """Get session statistics."""
        tracker = ScopeTracker(ScopeLimits())
        changes = [
            FileChange(path=Path("src/a.py"), lines_added=100, lines_removed=20),
            FileChange(path=Path("src/b.py"), lines_added=50),
        ]
        tracker.record_goal_completion(changes)

        stats = tracker.get_session_stats()
        assert stats["files_touched"] == 2
        assert stats["lines_changed"] == 170
        assert stats["goals_completed"] == 1


# =============================================================================
# Trust Zone Tests
# =============================================================================


class TestTrustZoneEvaluator:
    """Test trust zone evaluation."""

    def test_safe_path_detection(self):
        """Detect SAFE paths."""
        evaluator = TrustZoneEvaluator()
        assert evaluator.is_safe_path("tests/test_foo.py")
        assert evaluator.is_safe_path("docs/guide.md")
        assert not evaluator.is_safe_path("src/main.py")

    def test_forbidden_path_detection(self):
        """Detect FORBIDDEN paths."""
        evaluator = TrustZoneEvaluator()
        assert evaluator.is_forbidden_path(".env")
        assert evaluator.is_forbidden_path(".env.local")
        assert not evaluator.is_forbidden_path("config.yaml")

    def test_autonomous_allowed(self):
        """Check autonomous mode allowance."""
        evaluator = TrustZoneEvaluator()
        assert evaluator.is_allowed_in_autonomous("tests/test_foo.py")
        assert not evaluator.is_allowed_in_autonomous("src/auth/login.py")
        assert not evaluator.is_allowed_in_autonomous(".env")

    def test_blocked_paths_extraction(self):
        """Extract blocked paths from list."""
        evaluator = TrustZoneEvaluator()
        paths = [
            "tests/test_foo.py",
            "src/auth/login.py",
            "src/utils/helpers.py",
            ".env",
        ]
        blocked = evaluator.get_blocked_paths(paths)
        assert "src/auth/login.py" in blocked
        assert ".env" in blocked
        assert "tests/test_foo.py" not in blocked

    def test_path_summary(self):
        """Summarize paths by risk."""
        evaluator = TrustZoneEvaluator()
        paths = [
            "tests/test_a.py",
            "tests/test_b.py",
            "src/auth/oauth.py",
            ".env",
        ]
        summary = evaluator.summarize_paths(paths)
        assert summary["by_risk"]["safe"] == 2
        assert summary["by_risk"]["dangerous"] == 1
        assert summary["by_risk"]["forbidden"] == 1
        assert summary["blocked_in_autonomous"] == 2


# =============================================================================
# Escalation Handler Tests
# =============================================================================


class TestEscalationHandler:
    """Test escalation handling."""

    @pytest.mark.asyncio
    async def test_auto_response(self):
        """Test auto-response mode."""
        handler = EscalationHandler(auto_response="approve")
        escalation = handler.create_escalation(
            goal_id="test-1",
            reason=EscalationReason.DANGEROUS_ACTION,
            details="Test escalation",
            blocking_rule="dangerous_pattern",
        )

        resolution = await handler.escalate(escalation)
        assert resolution.action == "approve"
        assert resolution.acknowledged is True

    def test_escalation_options_for_forbidden(self):
        """FORBIDDEN actions have limited options."""
        handler = EscalationHandler()
        escalation = handler.create_escalation(
            goal_id="test-1",
            reason=EscalationReason.FORBIDDEN_ACTION,
            details="Cannot modify .env",
            blocking_rule="forbidden_pattern",
        )

        option_actions = {o.action for o in escalation.options}
        assert "approve" not in option_actions
        assert "skip" in option_actions
        assert "abort" in option_actions

    def test_escalation_options_for_scope(self):
        """Scope exceeded offers split option."""
        handler = EscalationHandler()
        escalation = handler.create_escalation(
            goal_id="test-1",
            reason=EscalationReason.SCOPE_EXCEEDED,
            details="Too many files",
            blocking_rule="scope_files",
        )

        option_ids = {o.id for o in escalation.options}
        assert "split" in option_ids
        assert "relax" in option_ids


# =============================================================================
# Verification Gate Tests
# =============================================================================


class TestVerificationGate:
    """Test verification gate."""

    @pytest.mark.asyncio
    async def test_forbidden_never_passes(self):
        """FORBIDDEN actions never pass."""
        gate = VerificationGate()
        result = await gate.check(ActionRisk.FORBIDDEN)
        assert not result.passed
        assert not result.auto_approvable

    @pytest.mark.asyncio
    async def test_dangerous_passes_not_auto(self):
        """DANGEROUS passes but not auto-approvable."""
        gate = VerificationGate()
        result = await gate.check(ActionRisk.DANGEROUS)
        assert result.passed
        assert not result.auto_approvable

    @pytest.mark.asyncio
    async def test_safe_auto_approves(self):
        """SAFE actions auto-approve without verifier."""
        gate = VerificationGate()
        result = await gate.check(ActionRisk.SAFE)
        assert result.passed
        assert result.auto_approvable

    @pytest.mark.asyncio
    async def test_moderate_needs_verification(self):
        """MODERATE needs verification."""
        gate = VerificationGate()
        result = await gate.check(ActionRisk.MODERATE)
        assert result.passed
        assert not result.auto_approvable

    @pytest.mark.asyncio
    async def test_thresholds_configurable(self):
        """Thresholds are configurable."""
        gate = VerificationGate(
            thresholds=VerificationThresholds(
                safe_threshold=0.5,
                moderate_threshold=0.7,
            )
        )
        assert gate.thresholds.safe_threshold == 0.5
        assert gate.thresholds.moderate_threshold == 0.7


# =============================================================================
# Config Tests
# =============================================================================


class TestGuardrailConfig:
    """Test configuration."""

    def test_default_config(self):
        """Default configuration values."""
        config = GuardrailConfig()
        assert config.trust_level == TrustLevel.GUARDED
        assert config.scope.max_files_per_goal == 10
        assert config.verification.safe_threshold == 0.70
        assert "fix" in config.auto_approve_categories

    def test_custom_config(self):
        """Custom configuration values."""
        config = GuardrailConfig(
            trust_level=TrustLevel.SUPERVISED,
            scope=ScopeLimits(max_files_per_goal=20),
            auto_approve_categories=frozenset({"test"}),
        )
        assert config.trust_level == TrustLevel.SUPERVISED
        assert config.scope.max_files_per_goal == 20
        assert "fix" not in config.auto_approve_categories
        assert "test" in config.auto_approve_categories
