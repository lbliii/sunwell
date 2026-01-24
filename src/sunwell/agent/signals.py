"""Signal extraction for adaptive routing (RFC-042, RFC-077).

Signals are cheap (~40 tokens) to extract and drive routing decisions:
- complexity: YES/NO/MAYBE → harmonic vs single-shot planning
- needs_tools: YES/NO → tool preparation
- is_ambiguous: YES/NO/MAYBE → dialectic before execution
- is_dangerous: YES/NO → stop and ask user
- confidence: 0.0-1.0 → vortex vs single-shot execution

The routing table maps signal combinations to techniques.

Two extraction modes:
1. **Batch extraction** (extract_signals): One call, all signals (~1.5s)
2. **Fast individual checks** (FastSignalChecker): Quick yes/no checks (~0.5s each)
   Use when you only need 1-2 specific signals, not full extraction.
"""


import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


@dataclass(frozen=True, slots=True)
class AdaptiveSignals:
    """Signals extracted from goal for adaptive routing.

    These drive automatic technique selection without user flags.
    """

    # Goal-level signals
    complexity: Literal["YES", "NO", "MAYBE"] = "MAYBE"
    """Is this a complex, multi-component task?"""

    needs_tools: Literal["YES", "NO"] = "NO"
    """Does this require file operations, commands, etc?"""

    is_ambiguous: Literal["YES", "NO", "MAYBE"] = "NO"
    """Is the goal ambiguous and needs clarification?"""

    is_dangerous: Literal["YES", "NO"] = "NO"
    """Could this cause data loss, security issues, etc?"""

    # RFC-115: Epic detection for hierarchical decomposition
    is_epic: Literal["YES", "NO", "MAYBE"] = "NO"
    """Is this an ambitious, multi-phase goal requiring hierarchical decomposition?

    Epic indicators:
    - Multiple distinct systems/components
    - Would require 50+ tasks
    - Words like "full", "complete", "entire", "build a"
    - Examples: "build an RTS game", "write a novel", "create a SaaS"
    """

    # Confidence (computed or extracted)
    confidence: float = 0.5
    """Overall confidence in understanding the goal (0.0-1.0)."""

    # Task categorization
    domain: str = "general"
    """Domain category (web, cli, data, ml, etc.)."""

    components: tuple[str, ...] = ()
    """Identified components/modules needed."""

    # Memory boost (set when relevant learnings found)
    memory_boost: float = 0.0
    """Confidence boost from relevant past learnings."""

    @property
    def effective_confidence(self) -> float:
        """Confidence including memory boost."""
        return min(1.0, self.confidence + self.memory_boost)

    @property
    def planning_route(self) -> str:
        """Determine planning route based on signals.

        Returns one of:
        - SINGLE_SHOT: Trivial task (complexity=NO, high confidence)
        - HARMONIC: Default for any non-trivial task (multi-candidate planning)
        - HIERARCHICAL: Ambitious epic needing milestone decomposition (RFC-115)
        - DIALECTIC: Ambiguous, needs clarification first
        - STOP: Dangerous, ask user

        HARMONIC is now the default. SINGLE_SHOT only for truly trivial tasks
        where complexity=NO and we're highly confident.
        """
        if self.is_dangerous == "YES":
            return "STOP"
        if self.is_ambiguous == "YES":
            return "DIALECTIC"
        # RFC-115: Route epics to hierarchical decomposition
        if self.is_epic == "YES":
            return "HIERARCHICAL"
        # Only use SINGLE_SHOT for trivial tasks (explicit NO + high confidence)
        if self.complexity == "NO" and self.confidence >= 0.8:
            return "SINGLE_SHOT"
        # Default to HARMONIC (multi-candidate planning) for everything else
        return "HARMONIC"

    @property
    def execution_route(self) -> str:
        """Determine execution route based on confidence.

        Returns one of:
        - SINGLE_SHOT: confidence > 0.85
        - INTERFERENCE: confidence 0.6-0.85
        - VORTEX: confidence < 0.6
        - CLARIFY: confidence < 0.3
        """
        conf = self.effective_confidence
        if conf < 0.3:
            return "CLARIFY"
        if conf < 0.6:
            return "VORTEX"
        if conf < 0.85:
            return "INTERFERENCE"
        return "SINGLE_SHOT"

    def with_memory_boost(self, n_learnings: int) -> AdaptiveSignals:
        """Return signals with memory boost applied.

        More relevant learnings → higher confidence boost.
        """
        # Diminishing returns: sqrt scaling
        boost = min(0.15, (n_learnings ** 0.5) * 0.05)
        return AdaptiveSignals(
            complexity=self.complexity,
            needs_tools=self.needs_tools,
            is_ambiguous=self.is_ambiguous,
            is_dangerous=self.is_dangerous,
            is_epic=self.is_epic,  # RFC-115
            confidence=self.confidence,
            domain=self.domain,
            components=self.components,
            memory_boost=boost,
        )

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "complexity": self.complexity,
            "needs_tools": self.needs_tools,
            "is_ambiguous": self.is_ambiguous,
            "is_dangerous": self.is_dangerous,
            "is_epic": self.is_epic,  # RFC-115
            "confidence": self.confidence,
            "effective_confidence": self.effective_confidence,
            "domain": self.domain,
            "components": list(self.components),
            "memory_boost": self.memory_boost,
            "planning_route": self.planning_route,
            "execution_route": self.execution_route,
        }


# =============================================================================
# Signal Extraction Prompt
# =============================================================================

SIGNAL_EXTRACTION_PROMPT = """Analyze this goal and extract signals for execution routing.

GOAL: {goal}

Output ONLY in this format (no prose):
COMPLEXITY: YES|NO|MAYBE
NEEDS_TOOLS: YES|NO
IS_AMBIGUOUS: YES|NO|MAYBE
IS_DANGEROUS: YES|NO
IS_EPIC: YES|NO|MAYBE
CONFIDENCE: 0.0-1.0
DOMAIN: web|cli|data|ml|api|general
COMPONENTS: comma-separated list

Rules:
- COMPLEXITY=YES if multi-file, multi-component, or requires planning
- NEEDS_TOOLS=YES if requires file operations, commands, or external tools
- IS_AMBIGUOUS=YES if goal is unclear or could mean multiple things
- IS_DANGEROUS=YES if could cause data loss, security issues, or system changes
- IS_EPIC=YES if ambitious multi-phase goal (50+ tasks, multiple systems, "build a game/app/novel")
- IS_EPIC=NO for single features, fixes, or bounded scope tasks
- CONFIDENCE: your confidence in understanding what's needed (0.0-1.0)
- DOMAIN: primary domain category
- COMPONENTS: list major artifacts/modules needed (e.g., "UserModel, PostModel, Routes")"""


def parse_signals(text: str) -> AdaptiveSignals:
    """Parse signal extraction response."""

    def extract(pattern: str, default: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else default

    def extract_list(pattern: str) -> tuple[str, ...]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            items = [s.strip() for s in match.group(1).split(",") if s.strip()]
            return tuple(items)
        return ()

    complexity_raw = extract(r"COMPLEXITY:\s*(YES|NO|MAYBE)", "MAYBE")
    needs_tools_raw = extract(r"NEEDS_TOOLS:\s*(YES|NO)", "NO")
    is_ambiguous_raw = extract(r"IS_AMBIGUOUS:\s*(YES|NO|MAYBE)", "NO")
    is_dangerous_raw = extract(r"IS_DANGEROUS:\s*(YES|NO)", "NO")
    is_epic_raw = extract(r"IS_EPIC:\s*(YES|NO|MAYBE)", "NO")  # RFC-115

    # Parse confidence
    conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", text, re.IGNORECASE)
    try:
        confidence = float(conf_match.group(1)) if conf_match else 0.5
        confidence = min(1.0, max(0.0, confidence))
    except ValueError:
        confidence = 0.5

    domain = extract(r"DOMAIN:\s*(\w+)", "general")
    components = extract_list(r"COMPONENTS:\s*(.+?)(?:\n|$)")

    return AdaptiveSignals(
        complexity=complexity_raw.upper(),  # type: ignore
        needs_tools=needs_tools_raw.upper(),  # type: ignore
        is_ambiguous=is_ambiguous_raw.upper(),  # type: ignore
        is_dangerous=is_dangerous_raw.upper(),  # type: ignore
        is_epic=is_epic_raw.upper(),  # type: ignore  # RFC-115
        confidence=confidence,
        domain=domain.lower(),
        components=components,
    )


async def extract_signals(
    goal: str,
    model: ModelProtocol,
    context: str | None = None,
) -> AdaptiveSignals:
    """Extract adaptive signals from a goal.

    This is cheap (~40 tokens) and runs once per goal.
    Signals drive all subsequent routing decisions.

    Args:
        goal: The user's goal/request
        model: Model for signal extraction
        context: Optional context (cwd, files, etc.)

    Returns:
        AdaptiveSignals for routing decisions
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = SIGNAL_EXTRACTION_PROMPT.format(goal=goal)
    if context:
        prompt += f"\n\nCONTEXT:\n{context}"

    try:
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=200),
        )
        return parse_signals(result.text)
    except Exception:
        # Default to conservative signals on error
        return AdaptiveSignals(
            complexity="YES",
            needs_tools="YES",
            is_ambiguous="MAYBE",
            is_dangerous="NO",
            confidence=0.5,
        )


# =============================================================================
# Per-Task Signal Extraction
# =============================================================================


@dataclass(frozen=True, slots=True)
class TaskSignals:
    """Signals for a specific task within a plan.

    These are cheaper (~20 tokens) and extracted per-task.
    """

    task_id: str
    """The task this signal is for."""

    confidence: float = 0.5
    """Confidence in generating this task (0.0-1.0)."""

    is_critical: bool = False
    """Is this a critical path task?"""

    error_prone: bool = False
    """Is this type of task historically error-prone?"""

    @property
    def execution_route(self) -> str:
        """Determine execution route for this task."""
        if self.confidence < 0.3:
            return "CLARIFY"
        if self.confidence < 0.6 or self.error_prone:
            return "VORTEX"
        if self.confidence < 0.85 or self.is_critical:
            return "INTERFERENCE"
        return "SINGLE_SHOT"


TASK_SIGNAL_PROMPT = """Rate your confidence in generating this task.

TASK: {task_description}
CONTEXT: {context}

Output ONLY:
CONFIDENCE: 0.0-1.0
IS_CRITICAL: YES|NO
ERROR_PRONE: YES|NO"""


async def extract_task_signals(
    task_id: str,
    task_description: str,
    model: ModelProtocol,
    context: str = "",
) -> TaskSignals:
    """Extract signals for a specific task.

    Args:
        task_id: Task identifier
        task_description: What the task does
        model: Model for signal extraction
        context: Task context

    Returns:
        TaskSignals for execution routing
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = TASK_SIGNAL_PROMPT.format(
        task_description=task_description,
        context=context or "None",
    )

    try:
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=50),
        )

        text = result.text

        # Parse confidence
        conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", text, re.IGNORECASE)
        try:
            confidence = float(conf_match.group(1)) if conf_match else 0.5
            confidence = min(1.0, max(0.0, confidence))
        except ValueError:
            confidence = 0.5

        # Parse booleans
        is_critical = bool(re.search(r"IS_CRITICAL:\s*YES", text, re.IGNORECASE))
        error_prone = bool(re.search(r"ERROR_PRONE:\s*YES", text, re.IGNORECASE))

        return TaskSignals(
            task_id=task_id,
            confidence=confidence,
            is_critical=is_critical,
            error_prone=error_prone,
        )

    except Exception:
        return TaskSignals(task_id=task_id, confidence=0.5)


# =============================================================================
# Error Signal Extraction
# =============================================================================


@dataclass(frozen=True, slots=True)
class ErrorSignals:
    """Signals extracted from an error for fix routing."""

    error_type: str
    """Category: syntax, import, type, runtime, test, unknown."""

    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    """How severe is this error?"""

    likely_cause: str = ""
    """Best guess at the cause."""

    hotspot_file: str | None = None
    """File most likely to contain the issue."""

    hotspot_lines: tuple[int, int] | None = None
    """Line range most likely to contain the issue."""

    @property
    def fix_route(self) -> str:
        """Determine fix route based on error signals.

        Returns one of:
        - DIRECT: Simple fix (syntax, lint auto-fix)
        - COMPOUND_EYE: Need to find hotspot first
        - VORTEX: Need multiple fix candidates
        - ESCALATE: Too complex, ask user
        """
        if self.error_type == "syntax":
            return "DIRECT"
        if self.error_type == "lint":
            return "DIRECT"
        if self.error_type == "type":
            return "COMPOUND_EYE"
        if self.error_type == "import":
            return "COMPOUND_EYE"
        if self.error_type == "runtime":
            return "VORTEX"
        if self.severity == "HIGH":
            return "ESCALATE"
        return "COMPOUND_EYE"


def classify_error(
    error_message: str,
    file_path: str | None = None,
) -> ErrorSignals:
    """Classify an error based on its message.

    This is deterministic (no LLM needed) for common error patterns.
    """
    message_lower = error_message.lower()

    # Syntax errors
    if "syntaxerror" in message_lower or "invalid syntax" in message_lower:
        return ErrorSignals(
            error_type="syntax",
            severity="HIGH",
            likely_cause="Invalid Python syntax",
            hotspot_file=file_path,
        )

    # Import errors
    if "modulenotfounderror" in message_lower or "importerror" in message_lower:
        return ErrorSignals(
            error_type="import",
            severity="MEDIUM",
            likely_cause="Missing or incorrect import",
            hotspot_file=file_path,
        )

    # Type errors
    if "typeerror" in message_lower:
        return ErrorSignals(
            error_type="type",
            severity="MEDIUM",
            likely_cause="Type mismatch or wrong argument type",
            hotspot_file=file_path,
        )

    # Attribute errors
    if "attributeerror" in message_lower:
        return ErrorSignals(
            error_type="runtime",
            severity="MEDIUM",
            likely_cause="Missing attribute or method",
            hotspot_file=file_path,
        )

    # Key errors
    if "keyerror" in message_lower:
        return ErrorSignals(
            error_type="runtime",
            severity="MEDIUM",
            likely_cause="Missing dictionary key",
            hotspot_file=file_path,
        )

    # SQLite threading
    if "sqlite" in message_lower and "thread" in message_lower:
        return ErrorSignals(
            error_type="runtime",
            severity="HIGH",
            likely_cause="SQLite threading issue - need per-request connections",
            hotspot_file=file_path,
        )

    # General runtime
    if "error" in message_lower:
        return ErrorSignals(
            error_type="runtime",
            severity="MEDIUM",
            likely_cause="Runtime error",
            hotspot_file=file_path,
        )

    return ErrorSignals(
        error_type="unknown",
        severity="MEDIUM",
        likely_cause="Unknown error type",
        hotspot_file=file_path,
    )


# =============================================================================
# Fast Signal Checker (RFC-077)
# =============================================================================


@dataclass
class FastSignalChecker:
    """Quick individual signal checks using FastClassifier (RFC-077).

    Use when you only need 1-2 specific signals, not full extraction.
    Each check is ~0.5-1s with a small model (llama3.2:3b).

    Example:
        checker = FastSignalChecker(model)

        # Quick danger check before execution
        if await checker.is_dangerous("Delete all user data"):
            raise UserConfirmationRequired("This action could cause data loss")

        # Quick complexity check for routing
        if await checker.is_complex("Refactor the auth system"):
            return "HARMONIC"  # Use multi-candidate planning
    """

    model: ModelProtocol
    """Small model for fast checks (llama3.2:3b recommended)."""

    _classifier: Any = field(default=None, repr=False)

    async def _get_classifier(self) -> Any:
        """Lazy-load FastClassifier."""
        if self._classifier is None:
            from sunwell.reasoning import FastClassifier

            self._classifier = FastClassifier(model=self.model)
        return self._classifier

    async def is_dangerous(self, goal: str) -> bool:
        """Check if goal could cause data loss, security issues, etc.

        Use before executing any autonomous action.
        """
        classifier = await self._get_classifier()
        return await classifier.yes_no(
            f"Could this action cause data loss, security issues, or system damage: '{goal}'",
            context="Be conservative - flag anything risky.",
        )

    async def is_complex(self, goal: str) -> bool:
        """Check if goal requires multi-step planning.

        Use for routing decisions (single-shot vs harmonic).
        """
        classifier = await self._get_classifier()
        result = await classifier.complexity(goal)
        return result in ("complex", "standard")

    async def needs_clarification(self, goal: str) -> bool:
        """Check if goal is ambiguous and needs user clarification.

        Use before starting execution on unclear requests.
        """
        classifier = await self._get_classifier()
        return await classifier.yes_no(
            f"Is this request ambiguous or unclear: '{goal}'",
            context="Flag if the request could mean multiple things.",
        )

    async def needs_tools(self, goal: str) -> bool:
        """Check if goal requires file/terminal access.

        Use for tool preparation decisions.
        """
        classifier = await self._get_classifier()
        return await classifier.yes_no(
            f"Does this require file operations, terminal commands, or external tools: '{goal}'"
        )

    async def severity(self, signal_type: str, content: str, file_path: str) -> str:
        """Classify severity of a code signal.

        Use for backlog prioritization.
        """
        classifier = await self._get_classifier()
        return await classifier.severity(signal_type, content, file_path)

    async def is_epic_goal(self, goal: str) -> bool:
        """Check if goal is an ambitious epic requiring hierarchical decomposition.

        RFC-115: Use for routing to HIERARCHICAL planning.
        """
        classifier = await self._get_classifier()
        return await classifier.yes_no(
            f"Is this an ambitious multi-phase goal that would need 50+ tasks: '{goal}'",
            context="Examples: 'build an RTS game', 'write a novel', 'create a SaaS platform'",
        )

    async def quick_signals(self, goal: str) -> AdaptiveSignals:
        """Extract signals using FastClassifier (parallel calls).

        Alternative to extract_signals() when you want JSON-based extraction.
        Slightly faster for simple goals, more reliable parsing.
        """
        import asyncio

        classifier = await self._get_classifier()

        # Run checks in parallel (including epic check for RFC-115)
        dangerous, complex_check, ambiguous, tools, epic = await asyncio.gather(
            self.is_dangerous(goal),
            classifier.complexity(goal),
            self.needs_clarification(goal),
            self.needs_tools(goal),
            self.is_epic_goal(goal),
        )

        # Map to AdaptiveSignals format
        complexity = "YES" if complex_check == "complex" else (
            "MAYBE" if complex_check == "standard" else "NO"
        )

        return AdaptiveSignals(
            complexity=complexity,  # type: ignore
            needs_tools="YES" if tools else "NO",  # type: ignore
            is_ambiguous="YES" if ambiguous else "NO",  # type: ignore
            is_dangerous="YES" if dangerous else "NO",  # type: ignore
            is_epic="YES" if epic else "NO",  # type: ignore  # RFC-115
            confidence=0.7,  # FastClassifier provides moderate confidence
        )
