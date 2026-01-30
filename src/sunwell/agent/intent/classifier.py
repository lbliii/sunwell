"""DAG-based Intent Classifier.

Classifies user input into a path through the Conversational DAG.
Uses heuristics for clear cases and LLM for ambiguous ones.

The classifier answers: "How deep into the action tree should we go?"
instead of binary "chat vs task".
"""

import logging
import re
from typing import TYPE_CHECKING

from sunwell.agent.intent.dag import (
    PATH_AUDIT,
    PATH_CLARIFY,
    PATH_CREATE,
    PATH_DECOMPOSE,
    PATH_DELETE,
    PATH_DESIGN,
    PATH_EXPLAIN,
    PATH_MODIFY,
    PATH_READ,
    PATH_REVIEW,
    IntentClassification,
    IntentNode,
    IntentPath,
    build_path_to,
)

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Heuristic Patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Imperative verbs that signal action intent
_ACTION_VERBS: frozenset[str] = frozenset({
    # Creation
    "add", "create", "build", "implement", "make", "write", "generate",
    "setup", "configure", "install", "initialize", "init",
    
    # Modification
    "fix", "refactor", "update", "modify", "change", "edit", "patch",
    "improve", "optimize", "enhance", "upgrade", "convert", "migrate",
    
    # Deletion
    "delete", "remove", "drop", "clear", "clean", "purge",
    
    # Execution
    "run", "execute", "deploy", "test", "start", "stop",
})

# Verbs that signal read-only action
_READ_VERBS: frozenset[str] = frozenset({
    "show", "list", "get", "find", "search", "grep", "look",
    "check", "verify", "inspect", "view", "display", "print",
})

# Verbs that signal analysis/review
_ANALYSIS_VERBS: frozenset[str] = frozenset({
    "review", "audit", "analyze", "examine", "investigate",
    "debug", "trace", "profile", "diagnose", "assess",
})

# Verbs that signal planning
_PLANNING_VERBS: frozenset[str] = frozenset({
    "plan", "design", "architect", "outline", "draft",
    "propose", "suggest", "recommend", "consider",
})

# Question patterns that are purely conversational (no tools)
_EXPLAIN_PATTERNS: tuple[str, ...] = (
    "what is a", "what are", "what's the difference",
    "how does", "how do", "why does", "why is", "why are",
    "can you explain", "tell me about", "describe", "explain",
    "what do you think", "what would you",
)

# Question patterns that require tools to answer
_TOOL_REQUIRING_PATTERNS: tuple[str, ...] = (
    # Git operations
    "who wrote", "who changed", "who modified", "who committed",
    "what changed", "what's changed", "what files changed",
    # File operations
    "what files", "what's in", "what is in",
    "where is", "where are", "where does",
    "which files", "which modules", "which functions",
    # Status checks
    "what is the status", "what's the status",
)

# Node override prefixes (e.g., "@explain how does X work?")
_NODE_PREFIXES: dict[str, IntentNode] = {
    "@explain": IntentNode.EXPLAIN,
    "@clarify": IntentNode.CLARIFY,
    "@review": IntentNode.REVIEW,
    "@audit": IntentNode.AUDIT,
    "@design": IntentNode.DESIGN,
    "@plan": IntentNode.PLAN,
    "@read": IntentNode.READ,
    "@create": IntentNode.CREATE,
    "@modify": IntentNode.MODIFY,
    "@delete": IntentNode.DELETE,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Classifier
# ═══════════════════════════════════════════════════════════════════════════════

class DAGClassifier:
    """Classify user input into a path through the Conversational DAG.
    
    Uses fast heuristics for clear cases, LLM for ambiguous ones.
    
    Example:
        >>> classifier = DAGClassifier(model=model)
        >>> result = await classifier.classify("Add input validation")
        >>> print(result.path)
        (CONVERSATION, ACT, WRITE, MODIFY)
    """
    
    def __init__(
        self,
        model: "ModelProtocol | None" = None,
        confidence_threshold: float = 0.7,
    ) -> None:
        """Initialize the classifier.
        
        Args:
            model: Optional LLM for ambiguous cases
            confidence_threshold: Minimum confidence for heuristic classification
        """
        self.model = model
        self.confidence_threshold = confidence_threshold
    
    async def classify(
        self,
        user_input: str,
        context: str | None = None,
    ) -> IntentClassification:
        """Classify user input into a DAG path.
        
        Args:
            user_input: Raw user input text
            context: Optional conversation context
            
        Returns:
            IntentClassification with path and confidence
        """
        logger.debug("Classifying: %r", user_input[:50])
        
        stripped = user_input.strip()
        
        # Check for explicit node override prefix
        override = self._check_node_override(stripped)
        if override:
            node, remaining = override
            return IntentClassification(
                path=build_path_to(node),
                confidence=1.0,
                reasoning=f"Explicit @{node.value} prefix",
                task_description=remaining if remaining else None,
            )
        
        # Try heuristic classification
        result = self._classify_heuristic(stripped)
        
        if result.confidence >= self.confidence_threshold:
            logger.debug("Heuristic classification: %s (%.2f)", result.path, result.confidence)
            return result
        
        # Escalate to LLM for ambiguous cases
        if self.model:
            logger.debug("Escalating to LLM (confidence %.2f < %.2f)", 
                        result.confidence, self.confidence_threshold)
            return await self._classify_with_llm(stripped, context, result)
        
        # No LLM available, return best guess
        logger.debug("No LLM, returning heuristic best guess")
        return result
    
    def _check_node_override(self, text: str) -> tuple[IntentNode, str] | None:
        """Check for explicit @node prefix override.
        
        Args:
            text: User input text
            
        Returns:
            Tuple of (node, remaining_text) if prefix found, else None
        """
        lower = text.lower()
        
        for prefix, node in _NODE_PREFIXES.items():
            if lower.startswith(prefix):
                remaining = text[len(prefix):].strip()
                return (node, remaining)
        
        return None
    
    def _classify_heuristic(self, text: str) -> IntentClassification:
        """Classify using heuristics.
        
        Args:
            text: User input text
            
        Returns:
            IntentClassification with best-guess path
        """
        lower = text.lower().strip()
        words = lower.split()
        
        if not words:
            return IntentClassification(
                path=(IntentNode.CONVERSATION,),
                confidence=0.0,
                reasoning="Empty input",
            )
        
        first_word = words[0]
        is_question = lower.endswith("?")
        
        # Check for deletion verbs (highest priority - most dangerous)
        if first_word in {"delete", "remove", "drop", "purge", "clear"}:
            return IntentClassification(
                path=PATH_DELETE,
                confidence=0.9,
                reasoning="Delete verb detected",
                task_description=text,
            )
        
        # Check for creation verbs
        if first_word in {"create", "add", "make", "generate", "new", "init", "initialize"}:
            return IntentClassification(
                path=PATH_CREATE,
                confidence=0.85,
                reasoning="Create verb detected",
                task_description=text,
            )
        
        # Check for modification verbs
        if first_word in _ACTION_VERBS - {"delete", "remove", "drop", "purge", "clear", 
                                          "create", "add", "make", "generate", "new"}:
            return IntentClassification(
                path=PATH_MODIFY,
                confidence=0.85,
                reasoning="Modify verb detected",
                task_description=text,
            )
        
        # Check for read verbs
        if first_word in _READ_VERBS:
            return IntentClassification(
                path=PATH_READ,
                confidence=0.8,
                reasoning="Read verb detected",
                task_description=text,
            )
        
        # Check for analysis verbs
        if first_word in _ANALYSIS_VERBS:
            if first_word == "review":
                return IntentClassification(
                    path=PATH_REVIEW,
                    confidence=0.85,
                    reasoning="Review verb detected",
                    task_description=text,
                )
            return IntentClassification(
                path=PATH_AUDIT,
                confidence=0.8,
                reasoning="Analysis verb detected",
                task_description=text,
            )
        
        # Check for planning verbs
        if first_word in _PLANNING_VERBS:
            if first_word == "design":
                return IntentClassification(
                    path=PATH_DESIGN,
                    confidence=0.8,
                    reasoning="Design verb detected",
                    task_description=text,
                )
            return IntentClassification(
                path=PATH_DECOMPOSE,
                confidence=0.75,
                reasoning="Planning verb detected",
                task_description=text,
            )
        
        # Check for tool-requiring question patterns
        if any(lower.startswith(p) for p in _TOOL_REQUIRING_PATTERNS):
            return IntentClassification(
                path=PATH_READ,
                confidence=0.8,
                reasoning="Tool-requiring question pattern",
                task_description=text,
            )
        
        # Check for pure explanation patterns
        if any(lower.startswith(p) for p in _EXPLAIN_PATTERNS):
            return IntentClassification(
                path=PATH_EXPLAIN,
                confidence=0.8,
                reasoning="Explanation question pattern",
            )
        
        # Questions default to explain (conservative)
        if is_question:
            return IntentClassification(
                path=PATH_EXPLAIN,
                confidence=0.6,
                reasoning="Question mark detected (defaulting to explain)",
            )
        
        # No clear signals - low confidence
        # Default to CONVERSATION root for safety
        return IntentClassification(
            path=(IntentNode.CONVERSATION,),
            confidence=0.3,
            reasoning="No clear intent signals",
        )
    
    async def _classify_with_llm(
        self,
        text: str,
        context: str | None,
        heuristic_result: IntentClassification,
    ) -> IntentClassification:
        """Use LLM for ambiguous classification.
        
        Args:
            text: User input text
            context: Optional conversation context
            heuristic_result: Result from heuristic classification
            
        Returns:
            LLM-enhanced classification
        """
        from sunwell.models.core.protocol import Message
        
        if not self.model:
            return heuristic_result
        
        prompt = f"""Classify this user input into ONE of these intent categories:

EXPLAIN - User wants something explained, a concept described, a question answered
REVIEW - User wants code reviewed, feedback given, analysis of existing code
AUDIT - User wants investigation, debugging, tracing of issues
DESIGN - User wants architecture discussion, design decisions
READ - User wants to find/search/list files or code (needs file access)
CREATE - User wants new files or code created
MODIFY - User wants existing files or code changed
DELETE - User wants files or code removed

{f"Recent context:{chr(10)}{context}{chr(10)}" if context else ""}
User input: "{text}"

Respond with ONLY the category name (e.g., EXPLAIN or MODIFY):"""

        try:
            result = await self.model.generate(
                (Message(role="user", content=prompt),),
            )
            
            response = (result.text or "").strip().upper()
            logger.debug("LLM classification response: %r", response)
            
            # Map response to path
            path_map: dict[str, IntentPath] = {
                "EXPLAIN": PATH_EXPLAIN,
                "CLARIFY": PATH_CLARIFY,
                "REVIEW": PATH_REVIEW,
                "AUDIT": PATH_AUDIT,
                "DESIGN": PATH_DESIGN,
                "PLAN": PATH_DECOMPOSE,
                "READ": PATH_READ,
                "CREATE": PATH_CREATE,
                "MODIFY": PATH_MODIFY,
                "DELETE": PATH_DELETE,
            }
            
            for key, path in path_map.items():
                if key in response:
                    return IntentClassification(
                        path=path,
                        confidence=0.85,
                        reasoning=f"LLM classification: {key}",
                        task_description=text if key in ("CREATE", "MODIFY", "DELETE", "READ") else None,
                    )
            
            # LLM response unclear, fall back to heuristic
            logger.warning("LLM returned unclear response: %r", response[:50])
            return IntentClassification(
                path=heuristic_result.path,
                confidence=max(heuristic_result.confidence, 0.5),
                reasoning=f"LLM unclear ({response[:20]}), using heuristic",
                task_description=heuristic_result.task_description,
            )
            
        except Exception as e:
            logger.exception("LLM classification failed")
            return IntentClassification(
                path=heuristic_result.path,
                confidence=heuristic_result.confidence,
                reasoning=f"LLM error: {e}, using heuristic",
                task_description=heuristic_result.task_description,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Function
# ═══════════════════════════════════════════════════════════════════════════════

async def classify_intent(
    user_input: str,
    model: "ModelProtocol | None" = None,
    context: str | None = None,
    confidence_threshold: float = 0.7,
) -> IntentClassification:
    """Convenience function to classify user input.
    
    Args:
        user_input: Raw user input text
        model: Optional LLM for ambiguous cases
        context: Optional conversation context
        confidence_threshold: Minimum confidence for heuristic classification
        
    Returns:
        IntentClassification with path and confidence
    """
    classifier = DAGClassifier(model=model, confidence_threshold=confidence_threshold)
    return await classifier.classify(user_input, context=context)
