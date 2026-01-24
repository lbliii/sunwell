"""Tests for the Adaptive Agent module (RFC-042).

Tests the signal extraction, validation gates, learning, and budget systems.
"""

from __future__ import annotations

import pytest

from sunwell.agent import (
    AdaptiveBudget,
    AdaptiveSignals,
    ErrorSignals,
    EventType,
    GateType,
    Learning,
    LearningStore,
    ValidationGate,
)


class TestAdaptiveSignals:
    """Tests for AdaptiveSignals routing logic."""

    def test_high_complexity_routes_to_harmonic(self):
        """High complexity should use Harmonic planning."""
        signals = AdaptiveSignals(complexity="YES", confidence=0.8)
        assert signals.planning_route == "HARMONIC"

    def test_low_confidence_routes_to_harmonic(self):
        """Low confidence with MAYBE complexity should use Harmonic."""
        signals = AdaptiveSignals(complexity="MAYBE", confidence=0.5)
        assert signals.planning_route == "HARMONIC"

    def test_simple_high_confidence_routes_to_single_shot(self):
        """Simple task with high confidence should use single-shot."""
        signals = AdaptiveSignals(complexity="NO", confidence=0.9)
        assert signals.planning_route == "SINGLE_SHOT"

    def test_dangerous_stops(self):
        """Dangerous goal should stop and ask."""
        signals = AdaptiveSignals(is_dangerous="YES", confidence=0.9)
        assert signals.planning_route == "STOP"

    def test_ambiguous_routes_to_dialectic(self):
        """Ambiguous goal should use dialectic first."""
        signals = AdaptiveSignals(is_ambiguous="YES", confidence=0.7)
        assert signals.planning_route == "DIALECTIC"

    def test_execution_routing_high_confidence(self):
        """High confidence execution uses single-shot."""
        signals = AdaptiveSignals(confidence=0.9)
        assert signals.execution_route == "SINGLE_SHOT"

    def test_execution_routing_medium_confidence(self):
        """Medium confidence uses interference."""
        signals = AdaptiveSignals(confidence=0.75)
        assert signals.execution_route == "INTERFERENCE"

    def test_execution_routing_low_confidence(self):
        """Low confidence uses vortex."""
        signals = AdaptiveSignals(confidence=0.5)
        assert signals.execution_route == "VORTEX"

    def test_execution_routing_very_low_clarifies(self):
        """Very low confidence asks for clarification."""
        signals = AdaptiveSignals(confidence=0.2)
        assert signals.execution_route == "CLARIFY"

    def test_memory_boost_increases_confidence(self):
        """Memory boost should increase effective confidence."""
        signals = AdaptiveSignals(confidence=0.7)
        boosted = signals.with_memory_boost(5)
        assert boosted.effective_confidence > signals.effective_confidence
        assert boosted.effective_confidence < 1.0


class TestErrorSignals:
    """Tests for ErrorSignals fix routing."""

    def test_syntax_errors_direct_fix(self):
        """Syntax errors should use direct fix."""
        err = ErrorSignals(error_type="syntax")
        assert err.fix_route == "DIRECT"

    def test_lint_errors_direct_fix(self):
        """Lint errors should use direct fix."""
        err = ErrorSignals(error_type="lint")
        assert err.fix_route == "DIRECT"

    def test_type_errors_compound_eye(self):
        """Type errors should use compound eye to find hotspot."""
        err = ErrorSignals(error_type="type")
        assert err.fix_route == "COMPOUND_EYE"

    def test_runtime_errors_vortex(self):
        """Runtime errors should use vortex for multi-candidate."""
        err = ErrorSignals(error_type="runtime")
        assert err.fix_route == "VORTEX"

    def test_high_severity_escalates(self):
        """High severity unknown errors should escalate."""
        err = ErrorSignals(error_type="unknown", severity="HIGH")
        assert err.fix_route == "ESCALATE"


class TestAdaptiveBudget:
    """Tests for budget-aware technique selection."""

    def test_initial_remaining(self):
        """Initial remaining should equal total."""
        budget = AdaptiveBudget(total_budget=50_000)
        assert budget.remaining == 50_000

    def test_spending_reduces_remaining(self):
        """Spending should reduce remaining."""
        budget = AdaptiveBudget(total_budget=50_000)
        budget.record_spend(10_000)
        assert budget.remaining == 40_000

    def test_can_afford_within_budget(self):
        """Should afford technique within budget."""
        budget = AdaptiveBudget(total_budget=50_000)
        assert budget.can_afford("vortex", 1000)  # 1000 * 15 = 15_000

    def test_cannot_afford_over_budget(self):
        """Should not afford technique over budget."""
        budget = AdaptiveBudget(total_budget=5_000)
        assert not budget.can_afford("vortex", 1000)  # 1000 * 15 = 15_000

    def test_route_downgrade_when_tight(self):
        """Should downgrade technique when budget tight."""
        budget = AdaptiveBudget(total_budget=5_000)
        route = budget.route_for_budget("vortex", 1000)
        assert route != "vortex"  # Should downgrade
        assert route in ("interference", "single_shot")

    def test_is_low_threshold(self):
        """Budget is_low at 30% remaining."""
        budget = AdaptiveBudget(total_budget=50_000)
        budget.record_spend(40_000)
        assert budget.is_low

    def test_is_critical_threshold(self):
        """Budget is_critical at 10% remaining."""
        budget = AdaptiveBudget(total_budget=50_000)
        budget.record_spend(46_000)
        assert budget.is_critical


class TestValidationGate:
    """Tests for validation gates."""

    def test_gate_creation(self):
        """Can create a validation gate."""
        gate = ValidationGate(
            id="gate_test",
            gate_type=GateType.IMPORT,
            depends_on=("task_1",),
            validation="from app import main",
        )
        assert gate.id == "gate_test"
        assert gate.gate_type == GateType.IMPORT
        assert gate.is_runnable_milestone

    def test_gate_types(self):
        """All gate types should be accessible."""
        types = list(GateType)
        assert GateType.SYNTAX in types
        assert GateType.LINT in types
        assert GateType.TYPE in types
        assert GateType.IMPORT in types
        assert GateType.SERVE in types


class TestLearningStore:
    """Tests for learning storage and retrieval."""

    def test_add_learning(self):
        """Can add learnings."""
        store = LearningStore()
        lrn = Learning(fact="User.id is primary key", category="type")
        store.add_learning(lrn)
        assert len(store.learnings) == 1

    def test_deduplication(self):
        """Duplicate learnings are skipped."""
        store = LearningStore()
        lrn = Learning(fact="User.id is primary key", category="type")
        store.add_learning(lrn)
        store.add_learning(lrn)  # Same learning
        assert len(store.learnings) == 1

    def test_get_relevant(self):
        """Can retrieve relevant learnings."""
        store = LearningStore()
        store.add_learning(Learning(fact="User model has id field", category="type"))
        store.add_learning(Learning(fact="POST /auth creates token", category="api"))

        relevant = store.get_relevant("User model")
        assert len(relevant) >= 1
        assert "User" in relevant[0].fact

    def test_format_for_prompt(self):
        """Can format learnings for prompt injection."""
        store = LearningStore()
        store.add_learning(Learning(fact="Use Flask factory pattern", category="pattern"))
        formatted = store.format_for_prompt()
        assert "Flask factory pattern" in formatted

    def test_to_dict(self):
        """Can serialize to dict."""
        store = LearningStore()
        store.add_learning(Learning(fact="Test fact", category="pattern"))
        d = store.to_dict()
        assert "learnings" in d
        assert len(d["learnings"]) == 1


class TestEventType:
    """Tests for event type enumeration."""

    def test_all_event_types_exist(self):
        """All expected event types should exist."""
        types = list(EventType)
        assert EventType.SIGNAL in types
        assert EventType.PLAN_START in types
        assert EventType.TASK_START in types
        assert EventType.GATE_START in types
        assert EventType.VALIDATE_ERROR in types
        assert EventType.FIX_START in types
        assert EventType.MEMORY_LEARNING in types
        assert EventType.COMPLETE in types


@pytest.mark.asyncio
async def test_imports_successful():
    """All public exports should be importable."""
    from sunwell.agent import (
        Agent,
        AgentEvent,
        GateDetector,
        GateResult,
        LearningExtractor,
        RendererConfig,
        RichRenderer,
        TaskGraph,
        create_renderer,
        extract_signals,
    )

    # Verify all imports work by checking they're not None
    assert all([
        Agent, AgentEvent, GateDetector, GateResult,
        LearningExtractor, RendererConfig, RichRenderer,
        TaskGraph, create_renderer, extract_signals,
    ])


class TestRendererConfig:
    """Tests for RendererConfig dataclass.

    This broke when main.py used non-existent fields (show_signals, show_gates, show_learning).
    These tests ensure the actual fields are documented and used correctly.
    """

    def test_renderer_config_defaults(self) -> None:
        """RendererConfig has sensible defaults."""
        from sunwell.agent import RendererConfig

        config = RendererConfig()

        assert config.mode == "interactive"
        assert config.refresh_rate == 10
        assert config.show_learnings is True
        assert config.verbose is False

    def test_renderer_config_custom_values(self) -> None:
        """RendererConfig accepts custom values."""
        from sunwell.agent import RendererConfig

        config = RendererConfig(
            mode="quiet",
            refresh_rate=5,
            show_learnings=False,
            verbose=True,
        )

        assert config.mode == "quiet"
        assert config.refresh_rate == 5
        assert config.show_learnings is False
        assert config.verbose is True

    def test_renderer_config_valid_modes(self) -> None:
        """RendererConfig accepts expected mode values."""
        from sunwell.agent import RendererConfig

        # These should not raise
        RendererConfig(mode="interactive")
        RendererConfig(mode="quiet")
        RendererConfig(mode="json")

    def test_renderer_config_signature_stability(self) -> None:
        """RendererConfig signature matches what CLI expects.

        This test exists because main.py broke using non-existent fields.
        If this test fails, update both this test AND the CLI.
        """
        import inspect
        from sunwell.agent import RendererConfig

        # Get actual fields from the dataclass
        sig = inspect.signature(RendererConfig)
        param_names = set(sig.parameters.keys())

        # These are the fields that SHOULD exist
        expected = {"mode", "refresh_rate", "show_learnings", "verbose"}
        assert expected == param_names, (
            f"RendererConfig signature changed! "
            f"Expected {expected}, got {param_names}. "
            f"Update cli/main.py if fields were renamed."
        )

        # These fields should NOT exist (old/removed)
        forbidden = {"show_signals", "show_gates", "show_learning"}
        assert forbidden.isdisjoint(param_names), (
            f"RendererConfig has deprecated fields: {forbidden & param_names}"
        )

    def test_create_renderer_with_config(self) -> None:
        """create_renderer accepts RendererConfig."""
        from sunwell.agent import RendererConfig, create_renderer

        config = RendererConfig(mode="interactive", verbose=True)
        renderer = create_renderer(config)

        assert renderer is not None
        # Renderer should exist and be configured
        assert hasattr(renderer, "config")
