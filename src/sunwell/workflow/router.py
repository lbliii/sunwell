"""Intent Router — Natural language to workflow selection (RFC-086).

Like DORI's ::auto command, the IntentRouter analyzes user input
and selects the appropriate workflow chain.
"""


import re
from dataclasses import dataclass

from sunwell.workflow.types import (
    WORKFLOW_CHAINS,
    Intent,
    IntentCategory,
    WorkflowChain,
    WorkflowTier,
)

# =============================================================================
# INTENT SIGNALS
# =============================================================================

# Keywords that signal each intent category
INTENT_SIGNALS: dict[IntentCategory, tuple[str, ...]] = {
    IntentCategory.CREATION: (
        "write",
        "create",
        "document",
        "draft",
        "new",
        "generate",
        "add",
    ),
    IntentCategory.VALIDATION: (
        "check",
        "audit",
        "verify",
        "validate",
        "review",
        "lint",
        "test",
    ),
    IntentCategory.TRANSFORMATION: (
        "restructure",
        "split",
        "modularize",
        "fix",
        "refactor",
        "reorganize",
        "migrate",
    ),
    IntentCategory.REFINEMENT: (
        "improve",
        "polish",
        "enhance",
        "tighten",
        "optimize",
        "clean up",
        "simplify",
    ),
    IntentCategory.INFORMATION: (
        "help",
        "what",
        "how",
        "explain",
        "show",
        "list",
        "describe",
    ),
}

# Intent category → default workflow chain
INTENT_WORKFLOWS: dict[IntentCategory, str] = {
    IntentCategory.CREATION: "feature-docs",
    IntentCategory.VALIDATION: "health-check",
    IntentCategory.TRANSFORMATION: "quick-fix",
    IntentCategory.REFINEMENT: "quick-fix",
    IntentCategory.INFORMATION: "health-check",  # Default to showing current state
}

# Special phrases that override normal routing
PHRASE_OVERRIDES: dict[str, tuple[IntentCategory, str]] = {
    "audit and fix": (IntentCategory.VALIDATION, "health-check"),
    "document this": (IntentCategory.CREATION, "feature-docs"),
    "fix the issues": (IntentCategory.TRANSFORMATION, "quick-fix"),
    "update docs": (IntentCategory.TRANSFORMATION, "modernize"),
    "modernize": (IntentCategory.TRANSFORMATION, "modernize"),
    "full audit": (IntentCategory.VALIDATION, "health-check"),
    "deep analysis": (IntentCategory.VALIDATION, "health-check"),
}


@dataclass
class IntentClassification:
    """Result of intent classification."""

    category: IntentCategory
    confidence: float
    signals: list[str]
    workflow_name: str
    tier: WorkflowTier


class IntentRouter:
    """Routes natural language requests to workflow chains.

    Example:
        >>> router = IntentRouter()
        >>> intent = router.classify("Audit and fix this doc")
        >>> intent.category
        IntentCategory.VALIDATION
        >>> intent.suggested_workflow
        'health-check'
    """

    def __init__(
        self,
        custom_signals: dict[IntentCategory, tuple[str, ...]] | None = None,
        custom_workflows: dict[IntentCategory, str] | None = None,
    ):
        """Initialize the router.

        Args:
            custom_signals: Additional intent signals to merge
            custom_workflows: Custom category → workflow mappings
        """
        self.signals = dict(INTENT_SIGNALS)
        self.workflows = dict(INTENT_WORKFLOWS)

        if custom_signals:
            for cat, sigs in custom_signals.items():
                existing = self.signals.get(cat, ())
                self.signals[cat] = existing + sigs

        if custom_workflows:
            self.workflows.update(custom_workflows)

    def classify(self, user_input: str) -> Intent:
        """Classify user intent from natural language.

        Args:
            user_input: Natural language request

        Returns:
            Classified intent with workflow suggestion
        """
        input_lower = user_input.lower()

        # Check phrase overrides first
        for phrase, (category, workflow) in PHRASE_OVERRIDES.items():
            if phrase in input_lower:
                return Intent(
                    category=category,
                    confidence=0.95,
                    signals=(phrase,),
                    suggested_workflow=workflow,
                    tier=self._determine_tier(input_lower),
                )

        # Score each category
        scores: dict[IntentCategory, float] = {}
        found_signals: dict[IntentCategory, list[str]] = {}

        for category, signals in self.signals.items():
            score = 0.0
            matches: list[str] = []

            for signal in signals:
                # Check for word boundary match
                pattern = rf"\b{re.escape(signal)}\b"
                if re.search(pattern, input_lower):
                    score += 1.0
                    matches.append(signal)

            scores[category] = score
            found_signals[category] = matches

        # Find best category
        if not any(scores.values()):
            # No signals found, default to information
            return Intent(
                category=IntentCategory.INFORMATION,
                confidence=0.3,
                signals=(),
                suggested_workflow=None,
                tier=WorkflowTier.LIGHT,
            )

        best_category = max(scores, key=lambda c: scores[c])
        total_score = sum(scores.values())
        confidence = scores[best_category] / total_score if total_score > 0 else 0.0

        return Intent(
            category=best_category,
            confidence=min(0.95, confidence),
            signals=tuple(found_signals[best_category]),
            suggested_workflow=self.workflows.get(best_category),
            tier=self._determine_tier(input_lower),
        )

    def select_workflow(self, intent: Intent) -> WorkflowChain | None:
        """Select a workflow chain for an intent.

        Args:
            intent: Classified intent

        Returns:
            WorkflowChain or None if no suitable workflow
        """
        if intent.suggested_workflow:
            return WORKFLOW_CHAINS.get(intent.suggested_workflow)

        # Fall back to category default
        workflow_name = self.workflows.get(intent.category)
        if workflow_name:
            return WORKFLOW_CHAINS.get(workflow_name)

        return None

    def classify_and_select(self, user_input: str) -> tuple[Intent, WorkflowChain | None]:
        """Classify intent and select workflow in one call.

        Args:
            user_input: Natural language request

        Returns:
            Tuple of (Intent, WorkflowChain or None)
        """
        intent = self.classify(user_input)
        workflow = self.select_workflow(intent)
        return intent, workflow

    def _determine_tier(self, input_lower: str) -> WorkflowTier:
        """Determine execution tier from input.

        Args:
            input_lower: Lowercased user input

        Returns:
            Appropriate WorkflowTier
        """
        # Fast tier signals
        if any(word in input_lower for word in ("quick", "fast", "just", "simply")):
            return WorkflowTier.FAST

        # Full tier signals
        if any(word in input_lower for word in ("comprehensive", "full", "deep", "complete")):
            return WorkflowTier.FULL

        # Default to light
        return WorkflowTier.LIGHT

    def explain_routing(self, user_input: str) -> str:
        """Generate human-readable explanation of routing decision.

        Args:
            user_input: Natural language request

        Returns:
            Explanation string
        """
        intent, workflow = self.classify_and_select(user_input)

        lines = [
            "🎯 Intent Analysis",
            "",
            f"Category: {intent.category.value.upper()}",
            f"Confidence: {intent.confidence:.0%}",
            f"Signals: {', '.join(intent.signals) if intent.signals else 'none detected'}",
            f"Tier: {intent.tier.value}",
            "",
        ]

        if workflow:
            lines.extend([
                f"📋 Selected Workflow: {workflow.name}",
                f"Description: {workflow.description}",
                "",
                "Steps:",
            ])
            for i, step in enumerate(workflow.steps, 1):
                checkpoint = " [checkpoint]" if i - 1 in workflow.checkpoint_after else ""
                lines.append(f"  {i}. {step.skill} — {step.purpose}{checkpoint}")
        else:
            lines.append("⚠️ No workflow selected — manual execution recommended")

        return "\n".join(lines)
