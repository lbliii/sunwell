"""Intent Pipeline — Two-Step Classification + Response.

Orchestrates the IntentClassifier and ResponseGenerator to produce
consistent, accurate intent analysis.

Architecture:
    User Input
        │
        ▼
    ┌─────────────────────┐
    │  IntentClassifier   │  Step 1: Structured routing (temp=0.1)
    │  (deterministic)    │  Output: route, workspace spec, etc.
    └─────────────────────┘
        │
        ▼
    ┌─────────────────────┐
    │  ResponseGenerator  │  Step 2: User-facing response (temp=0.7)
    │  (route-aware)      │  Output: natural language response
    └─────────────────────┘
        │
        ▼
    IntentAnalysis

Benefits:
1. Response cannot contradict routing (it's generated knowing the route)
2. Classifier can use tiny model (fast, cheap)
3. Each step is independently testable
4. Templates provide consistency, LLM adds nuance

See: RFC-075 (original), this refactor improves on it.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.interface.classifier import ClassificationResult, IntentClassifier
from sunwell.interface.responder import ResponseGenerator
from sunwell.interface.types import IntentAnalysis


@dataclass(slots=True)
class IntentPipeline:
    """Two-step intent analysis pipeline.

    Example:
        >>> pipeline = IntentPipeline(
        ...     classifier_model=tiny_model,  # Fast, cheap
        ...     responder_model=larger_model,  # Natural responses
        ... )
        >>> analysis = await pipeline.analyze("build a chat app")
        >>> analysis.interaction_type
        'workspace'
        >>> analysis.response
        "Let's build your chat app! Opening your workspace now."
    """

    classifier: IntentClassifier
    """Classifies intent into structured routing decisions."""

    responder: ResponseGenerator
    """Generates user-facing responses based on classification."""

    @classmethod
    def create(
        cls,
        classifier_model: ModelProtocol,
        responder_model: ModelProtocol | None = None,
        use_heuristics: bool = True,
        use_templates: bool = True,
    ) -> IntentPipeline:
        """Factory method to create a pipeline with models.

        Args:
            classifier_model: Model for classification (can be tiny)
            responder_model: Model for response generation (optional, uses templates if None)
            use_heuristics: Whether classifier should try fast heuristics first
            use_templates: Whether responder should prefer templates

        Returns:
            Configured IntentPipeline
        """
        classifier = IntentClassifier(
            model=classifier_model,
            use_heuristics=use_heuristics,
        )
        responder = ResponseGenerator(
            model=responder_model,
            use_templates=use_templates,
        )
        return cls(classifier=classifier, responder=responder)

    async def analyze(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> IntentAnalysis:
        """Analyze user goal through the two-step pipeline.

        Args:
            goal: User's stated goal
            context: Available data context (lists, events, etc.)
            history: Conversation history for multi-turn context

        Returns:
            Complete IntentAnalysis with routing and response
        """
        # Step 1: Classify intent (deterministic)
        classification = await self.classifier.classify(goal, context, history)

        # Step 2: Generate response (route-aware)
        response = await self.responder.generate(goal, classification, history)

        # Combine into IntentAnalysis
        return self._build_analysis(classification, response)

    def _build_analysis(
        self,
        classification: ClassificationResult,
        response: str,
    ) -> IntentAnalysis:
        """Build IntentAnalysis from classification and response."""
        return IntentAnalysis(
            interaction_type=classification.route,
            confidence=classification.confidence,
            action=classification.action,
            view=classification.view,
            workspace=classification.workspace,
            response=response,
            reasoning=classification.reasoning,
            conversation_mode=classification.conversation_mode,
            auxiliary_panels=classification.auxiliary_panels,
            suggested_tools=classification.suggested_tools,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def create_pipeline_from_naaru(naaru: Any) -> IntentPipeline:
    """Create a pipeline using Naaru's models.

    Args:
        naaru: Naaru instance with synthesis_model

    Returns:
        IntentPipeline configured with Naaru's models
    """
    # Use synthesis model for both (or could split for tiny classifier)
    return IntentPipeline.create(
        classifier_model=naaru.synthesis_model,
        responder_model=naaru.synthesis_model,
        use_heuristics=True,
        use_templates=True,
    )


async def analyze_with_pipeline(
    goal: str,
    model: ModelProtocol,
    context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> IntentAnalysis:
    """One-shot analysis using the two-step pipeline.

    Convenience function for simple use cases.

    Args:
        goal: User's stated goal
        model: Model to use for both classification and response
        context: Available data context
        history: Conversation history

    Returns:
        Complete IntentAnalysis
    """
    pipeline = IntentPipeline.create(
        classifier_model=model,
        responder_model=model,
    )
    return await pipeline.analyze(goal, context, history)
