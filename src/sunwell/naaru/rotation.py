"""Thought Rotation — Dynamic Cognitive Frame Shifting (RFC-028).

The Prism Principle: Small models contain multiple perspectives (critic, expert,
adversary, etc.) superposed in their weights. The prism (Sunwell) refracts the
beam into component wavelengths, each addressing a different aspect of the task.

Components:
- SpectralComposition: Task-dependent frame weights
- FrameIsolation: Model-size aware frame formatting
- ThoughtLexer: Tiny LLM generates rotation plans
- FrameHeuristicMap: Maps frames to relevant heuristics
- RotationWindowProcessor: Detects frame transitions in streaming

The Naaru emerges at the <synthesize> frame — the recombination point where
wavelengths integrate into meta-cognition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.heuristic import Heuristic
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Frame Types (Wavelengths)
# =============================================================================


class Frame(str, Enum):
    """Cognitive frames — the wavelengths of the prism.

    Each frame activates a different mode of reasoning:
    - THINK: Initial exploration
    - CRITIC: Challenge assumptions, find flaws
    - USER: Align with user intent
    - EXPERT: Apply domain best practices
    - ADVERSARY: Security/edge case perspective
    - SIMPLIFY: Reduce complexity
    - SYNTHESIZE: Recombination — where the Naaru emerges
    """

    THINK = "think"
    CRITIC = "critic"
    USER = "user"
    EXPERT = "expert"
    ADVERSARY = "adversary"
    SIMPLIFY = "simplify"
    SYNTHESIZE = "synthesize"


# Default frame order for different task types
FRAME_ORDERS: dict[str, tuple[Frame, ...]] = {
    "security_review": (
        Frame.THINK,
        Frame.ADVERSARY,
        Frame.CRITIC,
        Frame.EXPERT,
        Frame.USER,
        Frame.SYNTHESIZE,
    ),
    "code_review": (
        Frame.THINK,
        Frame.CRITIC,
        Frame.EXPERT,
        Frame.ADVERSARY,
        Frame.SYNTHESIZE,
    ),
    "documentation": (
        Frame.THINK,
        Frame.USER,
        Frame.EXPERT,
        Frame.SIMPLIFY,
        Frame.SYNTHESIZE,
    ),
    "general": (
        Frame.THINK,
        Frame.CRITIC,
        Frame.EXPERT,
        Frame.SYNTHESIZE,
    ),
}


# =============================================================================
# Spectral Composition
# =============================================================================


@dataclass(frozen=True, slots=True)
class SpectralComposition:
    """Defines the wavelength mix for a task type.

    Like adjusting a prism's angle to emphasize certain colors,
    this controls which frames get more emphasis (tokens/attention).

    Weights > 1.0 = emphasize this frame
    Weights < 1.0 = de-emphasize (keep brief)
    Weights = 0.0 = skip this frame entirely
    """

    weights: dict[Frame, float] = field(default_factory=lambda: {
        Frame.THINK: 1.0,
        Frame.CRITIC: 1.0,
        Frame.USER: 1.0,
        Frame.EXPERT: 1.0,
        Frame.ADVERSARY: 1.0,
        Frame.SIMPLIFY: 1.0,
        Frame.SYNTHESIZE: 1.5,  # Always emphasize synthesis
    })

    @classmethod
    def for_security_review(cls) -> SpectralComposition:
        """Heavy adversary and critic for security tasks."""
        return cls(weights={
            Frame.THINK: 0.8,
            Frame.CRITIC: 1.5,
            Frame.USER: 0.7,
            Frame.EXPERT: 1.2,
            Frame.ADVERSARY: 2.0,  # Think like an attacker
            Frame.SIMPLIFY: 0.5,
            Frame.SYNTHESIZE: 1.5,
        })

    @classmethod
    def for_documentation(cls) -> SpectralComposition:
        """Heavy user and simplify for docs."""
        return cls(weights={
            Frame.THINK: 0.8,
            Frame.CRITIC: 0.7,
            Frame.USER: 2.0,  # What does the reader need?
            Frame.EXPERT: 1.0,
            Frame.ADVERSARY: 0.3,
            Frame.SIMPLIFY: 1.5,  # Keep it clear
            Frame.SYNTHESIZE: 1.5,
        })

    @classmethod
    def for_code_review(cls) -> SpectralComposition:
        """Balanced critic/expert for code review."""
        return cls(weights={
            Frame.THINK: 1.0,
            Frame.CRITIC: 1.5,
            Frame.USER: 0.8,
            Frame.EXPERT: 1.5,
            Frame.ADVERSARY: 1.0,
            Frame.SIMPLIFY: 0.7,
            Frame.SYNTHESIZE: 1.5,
        })

    @classmethod
    def for_task_type(cls, task_type: str) -> SpectralComposition:
        """Factory method for common task types."""
        factories = {
            "security_review": cls.for_security_review,
            "security": cls.for_security_review,
            "code_review": cls.for_code_review,
            "review": cls.for_code_review,
            "documentation": cls.for_documentation,
            "docs": cls.for_documentation,
        }
        factory = factories.get(task_type.lower())
        if factory:
            return factory()
        return cls()  # Default balanced weights

    def get_active_frames(self, threshold: float = 0.3) -> list[Frame]:
        """Get frames with weight above threshold (in order)."""
        return [f for f in Frame if self.weights.get(f, 1.0) >= threshold]

    def get_emphasized_frames(self, threshold: float = 1.2) -> list[Frame]:
        """Get frames with emphasis (weight > threshold)."""
        return [f for f in Frame if self.weights.get(f, 1.0) >= threshold]

    def to_prompt_hint(self) -> str:
        """Generate prompt guidance based on composition."""
        emphasized = self.get_emphasized_frames()
        skipped = [f for f in Frame if self.weights.get(f, 1.0) < 0.3]

        hints = []
        if emphasized:
            frame_names = ", ".join(f"<{f.value}>" for f in emphasized)
            hints.append(f"Emphasize these frames: {frame_names}")
        if skipped:
            frame_names = ", ".join(f"<{f.value}>" for f in skipped)
            hints.append(f"You may skip: {frame_names}")

        return "\n".join(hints) if hints else ""


# =============================================================================
# Frame Isolation (Model-Size Aware)
# =============================================================================


class ModelSize(str, Enum):
    """Model size categories for frame formatting."""

    TINY = "tiny"      # <1B parameters
    SMALL = "small"    # 1-4B parameters
    MEDIUM = "medium"  # 4-13B parameters
    LARGE = "large"    # 13B+ parameters

    @classmethod
    def from_param_count(cls, params_billions: float) -> ModelSize:
        """Infer size category from parameter count."""
        if params_billions < 1.0:
            return cls.TINY
        elif params_billions < 4.0:
            return cls.SMALL
        elif params_billions < 13.0:
            return cls.MEDIUM
        else:
            return cls.LARGE

    @classmethod
    def from_model_name(cls, name: str) -> ModelSize:
        """Infer size from common model name patterns."""
        name_lower = name.lower()

        # Explicit size markers
        if any(x in name_lower for x in ["70b", "72b", "65b", "34b", "32b"]):
            return cls.LARGE
        if any(x in name_lower for x in ["13b", "14b", "8b", "7b"]):
            return cls.MEDIUM
        if any(x in name_lower for x in ["4b", "3b", "2b", "1.5b"]):
            return cls.SMALL
        if any(x in name_lower for x in ["1b", "0.5b", "500m", "270m", "tiny"]):
            return cls.TINY

        # Known small models
        if any(x in name_lower for x in ["tinyllama", "phi-2", "gemma-2b", "functiongemma"]):
            return cls.TINY
        if any(x in name_lower for x in ["phi3:mini", "llama3.2:1b", "qwen2.5:1.5b"]):
            return cls.SMALL

        # Default to medium
        return cls.MEDIUM


@dataclass(frozen=True, slots=True)
class FrameIsolation:
    """Controls frame boundary sharpness based on model capability.

    Smaller models need explicit, crisp frame transitions.
    Larger models can handle softer, more fluid transitions.

    The prism must be calibrated to the light source — too sharp
    for a powerful beam wastes its natural coherence, too soft
    for a dim beam fails to separate the wavelengths.
    """

    model_size: ModelSize

    @property
    def delimiter_style(self) -> str:
        """How explicitly to mark frame boundaries.

        - explicit_xml: <frame>content</frame> with instructions
        - soft_markers: [Frame perspective:] without closing
        - natural: "From a critic's perspective..." conversational
        """
        styles = {
            ModelSize.TINY: "explicit_xml",
            ModelSize.SMALL: "explicit_xml",
            ModelSize.MEDIUM: "soft_markers",
            ModelSize.LARGE: "natural",
        }
        return styles[self.model_size]

    @property
    def min_tokens_per_frame(self) -> int:
        """Minimum tokens before allowing frame switch.

        Smaller models need longer durations to "settle into" a perspective.
        """
        minimums = {
            ModelSize.TINY: 100,
            ModelSize.SMALL: 75,
            ModelSize.MEDIUM: 50,
            ModelSize.LARGE: 25,
        }
        return minimums[self.model_size]

    @property
    def inject_hints_on_switch(self) -> bool:
        """Whether to inject frame-specific hints on each switch.

        Smaller models benefit from re-injection to stay in frame.
        """
        return self.model_size in (ModelSize.TINY, ModelSize.SMALL)

    @property
    def require_explicit_synthesis(self) -> bool:
        """Whether to require explicit <synthesize> usage.

        The synthesis frame is where the Naaru emerges — smaller models
        need explicit prompting to ensure proper recombination.
        """
        return self.model_size in (ModelSize.TINY, ModelSize.SMALL, ModelSize.MEDIUM)

    def format_frame_start(self, frame: Frame, hints: list[str] | None = None) -> str:
        """Format frame start marker based on model size."""
        if self.delimiter_style == "explicit_xml":
            hint_text = ""
            if hints and self.inject_hints_on_switch:
                hint_text = f"\n<!-- Guidance: {'; '.join(hints[:2])} -->"
            return f"\n<{frame.value}>{hint_text}\n"

        elif self.delimiter_style == "soft_markers":
            return f"\n[{frame.value.title()} perspective:]\n"

        else:  # natural
            frame_intros = {
                Frame.THINK: "Let me think about this...",
                Frame.CRITIC: "Looking at this critically,",
                Frame.USER: "From the user's perspective,",
                Frame.EXPERT: "Applying best practices,",
                Frame.ADVERSARY: "If I were an attacker,",
                Frame.SIMPLIFY: "To simplify,",
                Frame.SYNTHESIZE: "Bringing it all together:",
            }
            return f"\n{frame_intros.get(frame, '')}\n"

    def format_frame_end(self, frame: Frame) -> str:
        """Format frame end marker."""
        if self.delimiter_style == "explicit_xml":
            return f"\n</{frame.value}>\n"
        return "\n"


# =============================================================================
# Rotation Plan
# =============================================================================


@dataclass(slots=True)
class RotationPlan:
    """A plan for rotating through cognitive frames.

    Generated by the ThoughtLexer based on task analysis.
    """

    task_type: str
    frames: tuple[Frame, ...]
    composition: SpectralComposition
    isolation: FrameIsolation
    reasoning: str = ""

    def to_system_prompt(self) -> str:
        """Generate a complete system prompt for rotation."""

        # Build frame list
        active_frames = [f for f in self.frames if self.composition.weights.get(f, 1.0) >= 0.3]

        # Base instructions vary by model size
        if self.isolation.delimiter_style == "explicit_xml":
            frame_instructions = self._explicit_xml_instructions(active_frames)
        elif self.isolation.delimiter_style == "soft_markers":
            frame_instructions = self._soft_marker_instructions(active_frames)
        else:
            frame_instructions = self._natural_instructions(active_frames)

        # Add composition hints
        composition_hint = self.composition.to_prompt_hint()

        # Build final prompt
        parts = [
            "## Thought Rotation Protocol",
            "",
            frame_instructions,
        ]

        if composition_hint:
            parts.extend(["", composition_hint])

        # Emphasize synthesis for all sizes
        parts.extend([
            "",
            "The <synthesize> frame is critical — integrate insights from prior frames,",
            "don't just summarize. This is where your analysis comes together.",
        ])

        return "\n".join(parts)

    def _explicit_xml_instructions(self, frames: list[Frame]) -> str:
        """Explicit XML-style instructions for small models."""
        frame_list = "\n".join(f"<{f.value}> ... </{f.value}>" for f in frames)

        return f"""As you reason, use these cognitive frames:

{frame_list}

IMPORTANT: Use the exact frame markers shown above. Each frame should contain
substantial reasoning (at least a few sentences). Always end with <synthesize>
to integrate your insights.

Example structure:
<think>
[Initial observations about the problem]
</think>

<critic>
[Challenge assumptions, identify issues]
</critic>

<expert>
[Apply domain knowledge and best practices]
</expert>

<synthesize>
[Integrate all perspectives into coherent response]
</synthesize>"""

    def _soft_marker_instructions(self, frames: list[Frame]) -> str:
        """Soft marker instructions for medium models."""
        frame_list = ", ".join(f"[{f.value.title()}]" for f in frames)

        return f"""Rotate through these perspectives as you reason: {frame_list}

Mark each perspective shift with [Perspective:] headers. Ensure your
response ends with [Synthesize:] to integrate your analysis."""

    def _natural_instructions(self, frames: list[Frame]) -> str:
        """Natural language instructions for large models."""
        frame_names = ", ".join(f.value for f in frames)

        return f"""Consider this problem from multiple angles: {frame_names}.

Let each perspective inform the others naturally, and synthesize
your insights into a coherent response."""


# =============================================================================
# Thought Lexer
# =============================================================================


@dataclass
class ThoughtLexer:
    """Analyzes tasks to generate rotation plans.

    Uses a tiny LLM (FunctionGemma, gemma3:1b) to:
    1. Classify task type
    2. Suggest appropriate frames
    3. Determine spectral composition

    If no tiny_model is provided, falls back to keyword classification.
    """

    tiny_model: ModelProtocol | None = None
    default_model_size: ModelSize = ModelSize.SMALL

    async def lex(
        self,
        task: str,
        model_size: ModelSize | None = None,
    ) -> RotationPlan:
        """Generate a rotation plan for the task.

        Args:
            task: The task/prompt to analyze
            model_size: Target model size (affects frame formatting)

        Returns:
            RotationPlan with frames, composition, and isolation settings
        """
        from sunwell.models.protocol import Message

        size = model_size or self.default_model_size

        prompt = f"""Analyze this task and suggest cognitive frames for reasoning.

TASK:
{task[:1000]}

OUTPUT (JSON only, no explanation):
{{
    "task_type": "security_review|code_review|documentation|analysis|general",
    "reasoning": "brief explanation of why these frames"
}}"""

        # If no tiny model, fall back to keyword classification
        if self.tiny_model is None:
            task_type = self._classify_by_keywords(task)
            reasoning = "Keyword classification (no tiny model configured)"
        else:
            try:
                result = await self.tiny_model.generate(
                    (Message(role="user", content=prompt),)
                )

                # Parse response
                import json
                import re

                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', result.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    task_type = data.get("task_type", "general")
                    reasoning = data.get("reasoning", "")
                    # Validate task_type is a known type
                    if task_type not in FRAME_ORDERS:
                        task_type = self._classify_by_keywords(task)
                        reasoning = "Unknown task_type from LLM, using keyword fallback"
                else:
                    # No JSON found - fall back to reliable keyword classification
                    task_type = self._classify_by_keywords(task)
                    reasoning = "Could not parse LLM JSON, using keyword fallback"

            except Exception as e:
                # Fall back to keyword matching
                task_type = self._classify_by_keywords(task)
                reasoning = f"Keyword classification (LLM error: {e})"

        # Build the plan
        frames = FRAME_ORDERS.get(task_type, FRAME_ORDERS["general"])
        composition = SpectralComposition.for_task_type(task_type)
        isolation = FrameIsolation(model_size=size)

        return RotationPlan(
            task_type=task_type,
            frames=frames,
            composition=composition,
            isolation=isolation,
            reasoning=reasoning,
        )

    def _classify_by_keywords(self, task: str) -> str:
        """Fallback classification using keywords."""
        task_lower = task.lower()

        # Security keywords - check first (most specific)
        if any(kw in task_lower for kw in [
            "security", "vulnerability", "vulnerabilities", "attack", "exploit",
            "injection", "csrf", "xss", "authentication", "password", "malicious"
        ]):
            return "security_review"

        # Analysis keywords
        if any(kw in task_lower for kw in [
            "analyze", "analysis", "architecture", "design", "investigate", "understand"
        ]):
            return "analysis"

        # Code review
        if any(kw in task_lower for kw in [
            "review", "code review", "check this", "audit", "quality", "improve",
            "refactor", "clean up", "lint", "best practice"
        ]):
            return "code_review"

        # Documentation
        if any(kw in task_lower for kw in [
            "document", "docs", "readme", "explain", "tutorial", "docstring", "api reference"
        ]):
            return "documentation"

        return "general"


# =============================================================================
# Frame Heuristic Map
# =============================================================================


@dataclass
class FrameHeuristicMap:
    """Maps cognitive frames to relevant heuristic categories.

    When the model enters a frame, we can inject heuristics that
    are particularly relevant to that perspective.
    """

    mappings: dict[Frame, tuple[str, ...]] = field(default_factory=lambda: {
        Frame.THINK: ("general", "domain", "context"),
        Frame.CRITIC: ("anti-patterns", "common-mistakes", "edge-cases", "code-smells"),
        Frame.USER: ("user-goals", "communication", "clarity", "accessibility"),
        Frame.EXPERT: ("best-practices", "patterns", "architecture", "idioms"),
        Frame.ADVERSARY: ("security", "vulnerabilities", "attack-vectors", "failure-modes"),
        Frame.SIMPLIFY: ("brevity", "clarity", "progressive-disclosure", "readability"),
        Frame.SYNTHESIZE: ("conclusions", "action-items", "recommendations", "integration"),
    })

    def get_categories_for_frame(self, frame: Frame) -> tuple[str, ...]:
        """Get heuristic categories relevant to a frame."""
        return self.mappings.get(frame, ("general",))

    def get_heuristics_for_frame(
        self,
        frame: Frame,
        lens: Lens,
        top_k: int = 3,
    ) -> list[Heuristic]:
        """Retrieve heuristics relevant to a cognitive frame.

        Args:
            frame: The cognitive frame
            lens: The loaded lens with heuristics
            top_k: Maximum heuristics to return

        Returns:
            List of relevant heuristics
        """
        categories = self.get_categories_for_frame(frame)

        relevant = []
        for h in lens.heuristics:
            # Check if heuristic category matches any frame category
            h_cats = getattr(h, "categories", []) or []
            if isinstance(h_cats, str):
                h_cats = [h_cats]

            # Also check heuristic name for keywords
            h_name_lower = h.name.lower()

            for cat in categories:
                if cat in h_cats or cat in h_name_lower:
                    relevant.append(h)
                    break

        return relevant[:top_k]

    def get_hints_for_frame(
        self,
        frame: Frame,
        lens: Lens,
        top_k: int = 2,
    ) -> list[str]:
        """Get brief hints from relevant heuristics.

        Returns just the rule text, not full heuristic details.
        """
        heuristics = self.get_heuristics_for_frame(frame, lens, top_k)
        return [h.rule for h in heuristics if h.rule]


# =============================================================================
# Rotation Window Processor (Streaming)
# =============================================================================


# Keywords that suggest natural frame transitions
FRAME_TRIGGERS: dict[Frame, tuple[str, ...]] = {
    Frame.CRITIC: (
        "but", "however", "although", "wait", "issue", "problem",
        "flaw", "mistake", "wrong", "incorrect", "missing", "concern",
    ),
    Frame.USER: (
        "they want", "the user", "goal is", "trying to", "needs",
        "expects", "asking for", "developer needs", "reader needs",
    ),
    Frame.EXPERT: (
        "best practice", "pattern", "architecture", "should be",
        "standard", "convention", "idiom", "recommended",
    ),
    Frame.ADVERSARY: (
        "attack", "vulnerability", "exploit", "injection", "security",
        "malicious", "untrusted", "edge case", "if an attacker",
    ),
    Frame.SIMPLIFY: (
        "in short", "simply", "basically", "to summarize", "key point",
        "bottom line", "tldr", "essentially",
    ),
    Frame.SYNTHESIZE: (
        "bringing it together", "in conclusion", "overall", "to summarize",
        "combining these", "taking all this", "my recommendation",
    ),
}


@dataclass
class RotationWindowProcessor:
    """Process streaming output with frame-aware context injection.

    Detects frame transitions in the token stream and can inject
    relevant heuristics when the model enters a new frame.
    """

    plan: RotationPlan
    frame_map: FrameHeuristicMap
    lens: Lens | None = None

    # State
    current_frame: Frame = field(default=Frame.THINK)
    frame_history: list[Frame] = field(default_factory=list)
    tokens_in_frame: int = field(default=0)
    token_buffer: list[str] = field(default_factory=list)

    def process_token(self, token: str) -> tuple[str, str | None]:
        """Process a token, potentially returning additional context to inject.

        Args:
            token: The token being streamed

        Returns:
            (token, optional_injection) - injection is hints to add
        """
        self.token_buffer.append(token)
        self.tokens_in_frame += 1

        # Keep buffer manageable
        if len(self.token_buffer) > 20:
            self.token_buffer = self.token_buffer[-20:]

        # Detect explicit frame markers
        explicit_frame = self._detect_explicit_frame(token)
        if explicit_frame and explicit_frame != self.current_frame:
            return self._handle_frame_switch(explicit_frame)

        # Detect natural frame transitions (only if enough tokens have passed)
        if self.tokens_in_frame >= self.plan.isolation.min_tokens_per_frame:
            natural_frame = self._detect_natural_frame()
            if natural_frame and natural_frame != self.current_frame:
                return self._handle_frame_switch(natural_frame)

        return token, None

    def _detect_explicit_frame(self, token: str) -> Frame | None:
        """Detect if token contains an explicit frame marker."""
        token_lower = token.lower()
        for frame in Frame:
            if f"<{frame.value}>" in token_lower:
                return frame
        return None

    def _detect_natural_frame(self) -> Frame | None:
        """Detect if recent tokens suggest a natural frame shift."""
        recent = " ".join(self.token_buffer).lower()

        for frame, triggers in FRAME_TRIGGERS.items():
            if any(trigger in recent for trigger in triggers):
                return frame

        return None

    def _handle_frame_switch(self, new_frame: Frame) -> tuple[str, str | None]:
        """Handle switching to a new frame."""
        self.frame_history.append(self.current_frame)
        self.current_frame = new_frame
        self.tokens_in_frame = 0

        # Get hints for new frame if we should inject them
        injection = None
        if self.plan.isolation.inject_hints_on_switch and self.lens:
            hints = self.frame_map.get_hints_for_frame(new_frame, self.lens)
            if hints:
                injection = f"\n<!-- {new_frame.value} guidance: {'; '.join(hints)} -->\n"

        return "", injection

    def get_frame_stats(self) -> dict[str, int]:
        """Get statistics on frame usage."""
        from collections import Counter
        counts = Counter(self.frame_history)
        counts[self.current_frame] = counts.get(self.current_frame, 0) + 1
        return dict(counts)


# =============================================================================
# Convenience Functions
# =============================================================================


def create_rotation_prompt(
    task_type: str = "general",
    model_size: ModelSize = ModelSize.SMALL,
) -> str:
    """Create a rotation system prompt without using ThoughtLexer.

    Quick way to get a rotation prompt for testing.
    """
    frames = FRAME_ORDERS.get(task_type, FRAME_ORDERS["general"])
    composition = SpectralComposition.for_task_type(task_type)
    isolation = FrameIsolation(model_size=model_size)

    plan = RotationPlan(
        task_type=task_type,
        frames=frames,
        composition=composition,
        isolation=isolation,
    )

    return plan.to_system_prompt()


async def generate_with_rotation(
    model: ModelProtocol,
    task: str,
    task_type: str = "general",
    model_size: ModelSize | None = None,
) -> str:
    """Generate a response using thought rotation.

    Convenience function that:
    1. Creates a rotation plan
    2. Injects the rotation system prompt
    3. Returns the model's response
    """
    from sunwell.models.protocol import Message

    # Infer model size if not provided
    if model_size is None:
        model_name = getattr(model, "model", "") or getattr(model, "_model", "")
        model_size = ModelSize.from_model_name(model_name)

    # Create rotation prompt
    rotation_prompt = create_rotation_prompt(task_type, model_size)

    # Generate
    result = await model.generate((
        Message(role="system", content=rotation_prompt),
        Message(role="user", content=task),
    ))

    return result.content
