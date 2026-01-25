"""Response Generator — Step 2 of Two-Step Pipeline.

Generates user-facing responses based on classified routing decisions.
This separation ensures responses cannot contradict routing decisions.

The responder KNOWS what route was decided, so it can:
1. Accurately describe what the UI will do ("Opening your workspace...")
2. Ask relevant follow-up questions for the decided route
3. Use appropriate tone for the interaction type

See: RFC-075 (original), this refactor improves on it.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

# =============================================================================
# PRE-COMPILED PATTERNS — Avoid re-compilation per call
# =============================================================================

_PROJECT_NAME_PATTERN = re.compile(
    r"\b(?:build|create|make|develop)\s+(?:a|an|the|me|us)?\s*(.+?)"
    r"(?:\s+app|\s+game|\s+site|\s+project)?$",
    re.IGNORECASE,
)
_PROJECT_SUFFIX_PATTERN = re.compile(r"\s+(app|game|site|website|project|system)$")

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

from sunwell.interface.generative.classifier import ClassificationResult

# =============================================================================
# RESPONSE TEMPLATES — Consistent, route-appropriate language
# =============================================================================

_TEMPLATES: dict[str, list[str]] = {
    "workspace_code": [
        "Let's build {project}! Opening your workspace now.",
        "Great idea! I'm setting up a coding workspace for {project}.",
        "Opening a workspace to build {project}. Let's get started!",
    ],
    "workspace_write": [
        "Opening your writing workspace for {project}.",
        "Let's work on {project}. I've set up a writing environment.",
    ],
    "workspace_plan": [
        "Let's plan {project}. Opening your planning workspace.",
        "I'm setting up a planning workspace for {project}.",
    ],
    "view": [
        "Here's {view_type} you requested.",
        "Showing {view_type} now.",
    ],
    "action_success": [
        "Done! {action_description}",
        "Got it — {action_description}",
    ],
    "action_failed": [
        "I couldn't complete that action. {reason}",
    ],
    "conversation_clarify": [
        "I'd like to help with that. Could you tell me more about {aspect}?",
        "Interesting! To help you best, can you clarify {aspect}?",
    ],
    "conversation_explain": [
        "{explanation}",
    ],
    "conversation_empathetic": [
        "{response}",
    ],
}

# =============================================================================
# RESPONSE GENERATION PROMPT — Constrained by route decision
# =============================================================================

_RESPONDER_PROMPT = '''Generate a response for this user interaction.

## User Goal
"{goal}"

## Decided Route
Type: {route}
{route_details}

## Conversation History
{history}

## Instructions
Generate a natural, helpful response that:
1. Acknowledges the user's goal
2. Accurately describes what will happen (based on the decided route)
3. Offers relevant next steps or asks clarifying questions if needed

CRITICAL RULES:
- For WORKSPACE route: Say you're "opening a workspace" or "setting up" the environment
- For VIEW route: Say you're "showing" or "here's" the requested information
- For ACTION route: Confirm what action was taken
- For CONVERSATION route: Engage naturally, ask clarifying questions if the route has low confidence

DO NOT say you're opening tools/workspaces if the route is CONVERSATION.
DO NOT ask clarifying questions if the route is WORKSPACE with high confidence.

## Tone
- Professional but warm
- Concise (1-3 sentences)
- Action-oriented

Respond with ONLY the user-facing message (no JSON, no metadata):'''


@dataclass(slots=True)
class ResponseGenerator:
    """Generates user-facing responses based on classification results.

    Can use templates for consistency or LLM for more natural responses.

    Example:
        >>> responder = ResponseGenerator(model=model)
        >>> response = await responder.generate(
        ...     goal="build a chat app",
        ...     classification=ClassificationResult(route="workspace", ...)
        ... )
        >>> response
        "Let's build your chat app! Opening your workspace now."
    """

    model: ModelProtocol | None = None
    """Optional model for dynamic response generation."""

    use_templates: bool = True
    """Whether to prefer templates over LLM generation."""

    async def generate(
        self,
        goal: str,
        classification: ClassificationResult,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Generate a user-facing response for the classification.

        Args:
            goal: Original user goal
            classification: Result from IntentClassifier
            history: Conversation history for context

        Returns:
            User-facing response string
        """
        # Try templates first for consistency
        if self.use_templates:
            template_response = self._template_response(goal, classification)
            if template_response:
                return template_response

        # Fall back to LLM generation
        if self.model:
            return await self._llm_response(goal, classification, history)

        # Last resort: simple template
        return self._fallback_response(goal, classification)

    def _template_response(
        self,
        goal: str,
        classification: ClassificationResult,
    ) -> str | None:
        """Generate response from templates."""
        import random

        route = classification.route

        if route == "workspace":
            # Determine workspace type
            primary = classification.workspace.primary if classification.workspace else "CodeEditor"
            if primary in ("CodeEditor", "Terminal"):
                templates = _TEMPLATES["workspace_code"]
            elif primary in ("ProseEditor", "Outline"):
                templates = _TEMPLATES["workspace_write"]
            else:
                templates = _TEMPLATES["workspace_plan"]

            project = self._extract_project_name(goal)
            return random.choice(templates).format(project=project)

        if route == "view":
            view_type = classification.view.type if classification.view else "information"
            templates = _TEMPLATES["view"]
            return random.choice(templates).format(view_type=view_type)

        if route == "action":
            action_type = classification.action.type if classification.action else "action"
            templates = _TEMPLATES["action_success"]
            return random.choice(templates).format(action_description=f"completed {action_type}")

        # Conversation needs more nuance — use LLM if available
        return None

    async def _llm_response(
        self,
        goal: str,
        classification: ClassificationResult,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Generate response using LLM."""
        if not self.model:
            return self._fallback_response(goal, classification)

        # Format route details
        route_details = self._format_route_details(classification)

        # Format history
        history_str = "None"
        if history:
            history_lines = []
            for msg in history[-4:]:
                role = msg.get("role", "user").title()
                content = msg.get("content", "")[:200]
                history_lines.append(f"{role}: {content}")
            history_str = "\n".join(history_lines)

        prompt = _RESPONDER_PROMPT.format(
            goal=goal,
            route=classification.route,
            route_details=route_details,
            history=history_str,
        )

        from sunwell.models import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.7,  # Higher for natural responses
                max_tokens=200,
            ),
        )

        response = (result.content or "").strip()

        # Clean up any accidental JSON or metadata
        if response.startswith("{") or response.startswith("```"):
            return self._fallback_response(goal, classification)

        return response if response else self._fallback_response(goal, classification)

    def _format_route_details(self, classification: ClassificationResult) -> str:
        """Format route-specific details for the prompt."""
        lines = [f"Confidence: {classification.confidence:.0%}"]

        if classification.route == "workspace" and classification.workspace:
            ws = classification.workspace
            lines.append(f"Workspace: {ws.primary} + {', '.join(ws.secondary)}")

        if classification.route == "view" and classification.view:
            lines.append(f"View: {classification.view.type}")

        if classification.route == "action" and classification.action:
            lines.append(f"Action: {classification.action.type}")

        if classification.route == "conversation":
            mode = classification.conversation_mode or "informational"
            lines.append(f"Mode: {mode}")
            if classification.confidence < 0.6:
                lines.append("Note: Low confidence — consider asking for clarification")

        if classification.auxiliary_panels:
            panel_types = [p.get("panel_type", "?") for p in classification.auxiliary_panels]
            lines.append(f"Panels: {', '.join(panel_types)}")

        return "\n".join(lines)

    def _fallback_response(self, goal: str, classification: ClassificationResult) -> str:
        """Generate minimal fallback response."""
        route = classification.route

        if route == "workspace":
            project = self._extract_project_name(goal)
            return f"Opening your workspace to build {project}."

        if route == "view":
            return "Here's what you requested."

        if route == "action":
            return "Done!"

        if route == "hybrid":
            return "Done! Here's the result."

        # Conversation
        if classification.confidence < 0.5:
            return (
                "I'd like to help with that. "
                "Could you tell me a bit more about what you're looking for?"
            )

        return "I'm here to help. What would you like to do?"

    def _extract_project_name(self, goal: str) -> str:
        """Extract project name from goal for templates."""
        # Try to extract "build a X" pattern (pre-compiled)
        match = _PROJECT_NAME_PATTERN.search(goal.lower())
        if match:
            name = match.group(1).strip()
            # Clean up common suffixes that got captured (pre-compiled)
            name = _PROJECT_SUFFIX_PATTERN.sub("", name)
            if name:
                return f"your {name}"

        # Fallback: use the whole goal
        return "your project"
