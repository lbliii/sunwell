"""Tests for IntentRouter (RFC-086)."""

import pytest

from sunwell.features.workflow import IntentRouter, Intent, IntentCategory, WorkflowTier
from sunwell.features.workflow.types import WORKFLOW_CHAINS


class TestIntentRouter:
    """Test IntentRouter classification."""

    @pytest.fixture
    def router(self) -> IntentRouter:
        """Create a test router."""
        return IntentRouter()

    def test_classify_creation_intent(self, router: IntentRouter) -> None:
        """Test classifying creation intents."""
        intent = router.classify("Write documentation for the API")

        assert intent.category == IntentCategory.CREATION
        assert intent.confidence > 0.5
        assert "write" in intent.signals or "document" in intent.signals

    def test_classify_validation_intent(self, router: IntentRouter) -> None:
        """Test classifying validation intents."""
        intent = router.classify("Audit this documentation")

        assert intent.category == IntentCategory.VALIDATION
        assert intent.confidence > 0.5
        assert "audit" in intent.signals

    def test_classify_transformation_intent(self, router: IntentRouter) -> None:
        """Test classifying transformation intents."""
        intent = router.classify("Fix the issues in this doc")

        assert intent.category == IntentCategory.TRANSFORMATION
        assert intent.confidence > 0.5

    def test_classify_refinement_intent(self, router: IntentRouter) -> None:
        """Test classifying refinement intents."""
        intent = router.classify("Improve the clarity")

        assert intent.category == IntentCategory.REFINEMENT
        assert intent.confidence > 0.5

    def test_classify_unknown_intent(self, router: IntentRouter) -> None:
        """Test classifying unknown intents."""
        intent = router.classify("xyz abc 123")

        assert intent.category == IntentCategory.INFORMATION
        assert intent.confidence < 0.5

    def test_phrase_override_audit_and_fix(self, router: IntentRouter) -> None:
        """Test phrase override for 'audit and fix'."""
        intent = router.classify("Audit and fix this doc")

        assert intent.category == IntentCategory.VALIDATION
        assert intent.confidence >= 0.95
        assert "audit and fix" in intent.signals

    def test_phrase_override_document_this(self, router: IntentRouter) -> None:
        """Test phrase override for 'document this'."""
        intent = router.classify("Document this feature")

        assert intent.category == IntentCategory.CREATION
        assert intent.confidence >= 0.95
        assert "document this" in intent.signals

    def test_phrase_override_modernize(self, router: IntentRouter) -> None:
        """Test phrase override for 'modernize'."""
        intent = router.classify("Modernize the docs")

        assert intent.category == IntentCategory.TRANSFORMATION
        assert intent.suggested_workflow == "modernize"

    def test_tier_detection_fast(self, router: IntentRouter) -> None:
        """Test detecting fast tier from input."""
        intent = router.classify("Quick fix this doc")

        assert intent.tier == WorkflowTier.FAST

    def test_tier_detection_full(self, router: IntentRouter) -> None:
        """Test detecting full tier from input."""
        intent = router.classify("Comprehensive audit of all docs")

        assert intent.tier == WorkflowTier.FULL

    def test_tier_detection_light(self, router: IntentRouter) -> None:
        """Test detecting light tier (default) from input."""
        intent = router.classify("Check this doc")

        assert intent.tier == WorkflowTier.LIGHT


class TestWorkflowSelection:
    """Test workflow selection from intents."""

    @pytest.fixture
    def router(self) -> IntentRouter:
        """Create a test router."""
        return IntentRouter()

    def test_select_feature_docs_workflow(self, router: IntentRouter) -> None:
        """Test selecting feature-docs workflow."""
        intent, workflow = router.classify_and_select("Write documentation for the batch API")

        assert workflow is not None
        assert workflow.name == "feature-docs"

    def test_select_health_check_workflow(self, router: IntentRouter) -> None:
        """Test selecting health-check workflow."""
        intent, workflow = router.classify_and_select("Audit this documentation")

        assert workflow is not None
        assert workflow.name == "health-check"

    def test_select_quick_fix_workflow(self, router: IntentRouter) -> None:
        """Test selecting quick-fix workflow."""
        intent, workflow = router.classify_and_select("Fix the issues")

        assert workflow is not None
        assert workflow.name == "quick-fix"

    def test_select_modernize_workflow(self, router: IntentRouter) -> None:
        """Test selecting modernize workflow."""
        intent, workflow = router.classify_and_select("Modernize the docs")

        assert workflow is not None
        assert workflow.name == "modernize"

    def test_unknown_intent_no_workflow(self, router: IntentRouter) -> None:
        """Test that unknown intents may not select a workflow."""
        intent, workflow = router.classify_and_select("xyz abc 123")

        # Even unknown intents might get a default workflow
        assert intent.category == IntentCategory.INFORMATION


class TestExplainRouting:
    """Test routing explanation."""

    def test_explain_routing_format(self) -> None:
        """Test that explanation is well-formatted."""
        router = IntentRouter()
        explanation = router.explain_routing("Write documentation for the API")

        assert "Intent Analysis" in explanation
        assert "Category:" in explanation
        assert "Confidence:" in explanation
        assert "Selected Workflow:" in explanation

    def test_explain_routing_shows_steps(self) -> None:
        """Test that explanation shows workflow steps."""
        router = IntentRouter()
        explanation = router.explain_routing("Audit this doc")

        assert "Steps:" in explanation


class TestCustomSignals:
    """Test custom signals configuration."""

    def test_custom_signals_extend_defaults(self) -> None:
        """Test that custom signals extend defaults."""
        custom = {
            IntentCategory.CREATION: ("craft", "compose"),
        }
        router = IntentRouter(custom_signals=custom)

        intent = router.classify("Craft a new document")
        assert intent.category == IntentCategory.CREATION

    def test_custom_workflows_override_defaults(self) -> None:
        """Test that custom workflows override defaults."""
        custom = {
            IntentCategory.VALIDATION: "custom-audit",
        }
        router = IntentRouter(custom_workflows=custom)

        intent = router.classify("Check this doc")
        assert intent.suggested_workflow == "custom-audit"
