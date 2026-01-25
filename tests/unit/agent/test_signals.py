"""Tests for signal extraction (RFC-042, RFC-077).

Tests AdaptiveSignals, parsing, and routing logic.
"""

import pytest

from sunwell.agent.signals import (
    AdaptiveSignals,
    ErrorSignals,
    TaskSignals,
    classify_error,
    parse_signals,
)


class TestAdaptiveSignals:
    """Tests for AdaptiveSignals dataclass."""

    def test_default_signals(self) -> None:
        """Signals have conservative defaults."""
        signals = AdaptiveSignals()

        assert signals.complexity == "MAYBE"
        assert signals.needs_tools == "NO"
        assert signals.is_ambiguous == "NO"
        assert signals.is_dangerous == "NO"
        assert signals.is_epic == "NO"
        assert signals.confidence == 0.5

    def test_effective_confidence_with_boost(self) -> None:
        """Memory boost increases effective confidence."""
        signals = AdaptiveSignals(confidence=0.7, memory_boost=0.1)

        assert signals.effective_confidence == 0.8

    def test_effective_confidence_capped_at_1(self) -> None:
        """Effective confidence doesn't exceed 1.0."""
        signals = AdaptiveSignals(confidence=0.9, memory_boost=0.2)

        assert signals.effective_confidence == 1.0

    def test_planning_route_stop_for_dangerous(self) -> None:
        """Dangerous tasks route to STOP."""
        signals = AdaptiveSignals(is_dangerous="YES")

        assert signals.planning_route == "STOP"

    def test_planning_route_dialectic_for_ambiguous(self) -> None:
        """Ambiguous tasks route to DIALECTIC."""
        signals = AdaptiveSignals(is_ambiguous="YES")

        assert signals.planning_route == "DIALECTIC"

    def test_planning_route_hierarchical_for_epic(self) -> None:
        """Epic tasks route to HIERARCHICAL."""
        signals = AdaptiveSignals(is_epic="YES")

        assert signals.planning_route == "HIERARCHICAL"

    def test_planning_route_single_shot_for_trivial(self) -> None:
        """Trivial tasks with high confidence route to SINGLE_SHOT."""
        signals = AdaptiveSignals(complexity="NO", confidence=0.9)

        assert signals.planning_route == "SINGLE_SHOT"

    def test_planning_route_harmonic_default(self) -> None:
        """Most tasks route to HARMONIC."""
        signals = AdaptiveSignals(complexity="YES", confidence=0.7)

        assert signals.planning_route == "HARMONIC"

    def test_execution_route_clarify_for_low_confidence(self) -> None:
        """Very low confidence routes to CLARIFY."""
        signals = AdaptiveSignals(confidence=0.2)

        assert signals.execution_route == "CLARIFY"

    def test_execution_route_vortex_for_medium_confidence(self) -> None:
        """Medium-low confidence routes to VORTEX."""
        signals = AdaptiveSignals(confidence=0.5)

        assert signals.execution_route == "VORTEX"

    def test_execution_route_interference_for_moderate_confidence(self) -> None:
        """Moderate confidence routes to INTERFERENCE."""
        signals = AdaptiveSignals(confidence=0.7)

        assert signals.execution_route == "INTERFERENCE"

    def test_execution_route_single_shot_for_high_confidence(self) -> None:
        """High confidence routes to SINGLE_SHOT."""
        signals = AdaptiveSignals(confidence=0.9)

        assert signals.execution_route == "SINGLE_SHOT"

    def test_with_memory_boost(self) -> None:
        """with_memory_boost creates new signals with boost."""
        signals = AdaptiveSignals(confidence=0.6)
        boosted = signals.with_memory_boost(n_learnings=4)

        assert boosted.memory_boost > 0
        assert boosted.confidence == 0.6  # Original confidence unchanged
        assert boosted.effective_confidence > 0.6

    def test_with_memory_boost_diminishing_returns(self) -> None:
        """Memory boost has diminishing returns."""
        signals = AdaptiveSignals(confidence=0.5)

        boost_1 = signals.with_memory_boost(1).memory_boost
        boost_4 = signals.with_memory_boost(4).memory_boost
        boost_9 = signals.with_memory_boost(9).memory_boost

        # 4x learnings doesn't give 4x boost
        assert boost_4 < boost_1 * 4
        # Boost increases but with diminishing returns
        assert boost_4 > boost_1
        assert boost_9 > boost_4

    def test_to_dict(self) -> None:
        """to_dict serializes all fields."""
        signals = AdaptiveSignals(
            complexity="YES",
            needs_tools="YES",
            domain="web",
            components=("UserModel", "AuthRoutes"),
        )

        data = signals.to_dict()

        assert data["complexity"] == "YES"
        assert data["needs_tools"] == "YES"
        assert data["domain"] == "web"
        assert data["components"] == ["UserModel", "AuthRoutes"]
        assert "planning_route" in data
        assert "execution_route" in data


class TestParseSignals:
    """Tests for parse_signals function."""

    def test_parse_complete_response(self) -> None:
        """parse_signals extracts all fields."""
        text = """COMPLEXITY: YES
NEEDS_TOOLS: YES
IS_AMBIGUOUS: NO
IS_DANGEROUS: NO
IS_EPIC: NO
CONFIDENCE: 0.85
DOMAIN: web
COMPONENTS: UserModel, AuthService, Routes"""

        signals = parse_signals(text)

        assert signals.complexity == "YES"
        assert signals.needs_tools == "YES"
        assert signals.is_ambiguous == "NO"
        assert signals.is_dangerous == "NO"
        assert signals.confidence == 0.85
        assert signals.domain == "web"
        assert "UserModel" in signals.components

    def test_parse_case_insensitive(self) -> None:
        """parse_signals handles case variations."""
        text = """complexity: yes
needs_tools: no
confidence: 0.7"""

        signals = parse_signals(text)

        assert signals.complexity == "YES"
        assert signals.needs_tools == "NO"

    def test_parse_with_extra_text(self) -> None:
        """parse_signals handles surrounding prose."""
        text = """Here's my analysis:

COMPLEXITY: MAYBE
NEEDS_TOOLS: YES
CONFIDENCE: 0.6

This task requires careful planning."""

        signals = parse_signals(text)

        assert signals.complexity == "MAYBE"
        assert signals.needs_tools == "YES"
        assert signals.confidence == 0.6

    def test_parse_missing_fields_use_defaults(self) -> None:
        """parse_signals uses defaults for missing fields."""
        text = "COMPLEXITY: YES"

        signals = parse_signals(text)

        assert signals.complexity == "YES"
        assert signals.needs_tools == "NO"  # Default
        assert signals.confidence == 0.5  # Default

    def test_parse_invalid_confidence(self) -> None:
        """parse_signals handles invalid confidence values."""
        text = """CONFIDENCE: not_a_number"""

        signals = parse_signals(text)

        assert signals.confidence == 0.5  # Default

    def test_parse_confidence_clamped(self) -> None:
        """parse_signals clamps confidence to 0-1."""
        text = """CONFIDENCE: 1.5"""

        signals = parse_signals(text)

        assert signals.confidence == 1.0

    def test_parse_epic_field(self) -> None:
        """parse_signals handles IS_EPIC field."""
        text = """IS_EPIC: YES
COMPLEXITY: YES"""

        signals = parse_signals(text)

        assert signals.is_epic == "YES"


class TestTaskSignals:
    """Tests for TaskSignals dataclass."""

    def test_task_signals_creation(self) -> None:
        """TaskSignals stores task-specific signals."""
        signals = TaskSignals(
            task_id="task-123",
            confidence=0.8,
            is_critical=True,
            error_prone=False,
        )

        assert signals.task_id == "task-123"
        assert signals.confidence == 0.8
        assert signals.is_critical
        assert not signals.error_prone

    def test_execution_route_clarify(self) -> None:
        """Very low confidence routes to CLARIFY."""
        signals = TaskSignals(task_id="t1", confidence=0.2)

        assert signals.execution_route == "CLARIFY"

    def test_execution_route_vortex_for_error_prone(self) -> None:
        """Error-prone tasks route to VORTEX."""
        signals = TaskSignals(task_id="t1", confidence=0.7, error_prone=True)

        assert signals.execution_route == "VORTEX"

    def test_execution_route_interference_for_critical(self) -> None:
        """Critical tasks route to INTERFERENCE."""
        signals = TaskSignals(task_id="t1", confidence=0.9, is_critical=True)

        assert signals.execution_route == "INTERFERENCE"

    def test_execution_route_single_shot_for_simple(self) -> None:
        """Simple high-confidence tasks route to SINGLE_SHOT."""
        signals = TaskSignals(task_id="t1", confidence=0.9)

        assert signals.execution_route == "SINGLE_SHOT"


class TestErrorSignals:
    """Tests for ErrorSignals dataclass."""

    def test_error_signals_creation(self) -> None:
        """ErrorSignals stores error classification."""
        signals = ErrorSignals(
            error_type="syntax",
            severity="HIGH",
            likely_cause="Invalid indentation",
            hotspot_file="app.py",
        )

        assert signals.error_type == "syntax"
        assert signals.severity == "HIGH"
        assert signals.likely_cause == "Invalid indentation"

    def test_fix_route_direct_for_syntax(self) -> None:
        """Syntax errors route to DIRECT fix."""
        signals = ErrorSignals(error_type="syntax", severity="HIGH")

        assert signals.fix_route == "DIRECT"

    def test_fix_route_direct_for_lint(self) -> None:
        """Lint errors route to DIRECT fix."""
        signals = ErrorSignals(error_type="lint", severity="LOW")

        assert signals.fix_route == "DIRECT"

    def test_fix_route_compound_eye_for_type(self) -> None:
        """Type errors route to COMPOUND_EYE."""
        signals = ErrorSignals(error_type="type", severity="MEDIUM")

        assert signals.fix_route == "COMPOUND_EYE"

    def test_fix_route_vortex_for_runtime(self) -> None:
        """Runtime errors route to VORTEX."""
        signals = ErrorSignals(error_type="runtime", severity="MEDIUM")

        assert signals.fix_route == "VORTEX"

    def test_fix_route_escalate_for_high_severity(self) -> None:
        """High severity unknown errors route to ESCALATE."""
        signals = ErrorSignals(error_type="unknown", severity="HIGH")

        assert signals.fix_route == "ESCALATE"


class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_syntax_error(self) -> None:
        """Syntax errors are correctly classified."""
        signals = classify_error("SyntaxError: invalid syntax")

        assert signals.error_type == "syntax"
        assert signals.severity == "HIGH"

    def test_classify_import_error(self) -> None:
        """Import errors are correctly classified."""
        signals = classify_error("ModuleNotFoundError: No module named 'foo'")

        assert signals.error_type == "import"

    def test_classify_type_error(self) -> None:
        """Type errors are correctly classified."""
        signals = classify_error("TypeError: unsupported operand type")

        assert signals.error_type == "type"

    def test_classify_attribute_error(self) -> None:
        """Attribute errors are classified as runtime."""
        signals = classify_error("AttributeError: 'NoneType' has no attribute 'foo'")

        assert signals.error_type == "runtime"

    def test_classify_key_error(self) -> None:
        """Key errors are classified as runtime."""
        signals = classify_error("KeyError: 'missing_key'")

        assert signals.error_type == "runtime"

    def test_classify_sqlite_threading(self) -> None:
        """SQLite threading errors are classified with specific cause."""
        signals = classify_error("SQLite objects created in a thread can only be used in that same thread")

        assert signals.error_type == "runtime"
        assert signals.severity == "HIGH"
        assert "threading" in signals.likely_cause.lower()

    def test_classify_unknown_error(self) -> None:
        """Unknown errors get default classification."""
        signals = classify_error("Something completely unexpected happened")

        assert signals.error_type == "unknown"

    def test_classify_with_file_path(self) -> None:
        """File path is passed through to signals."""
        signals = classify_error("SyntaxError: invalid syntax", file_path="app/main.py")

        assert signals.hotspot_file == "app/main.py"
