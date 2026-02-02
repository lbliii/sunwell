"""Turn - The atomic unit of conversation.

Each turn is content-addressable (hash-based identity) enabling:
- O(1) deduplication
- Immutable history
- DAG construction
- Compression without loss

RFC-122: Extended with template and heuristic learning categories
for compound learning and knowledge retrieval.
"""


import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from typing import Self


class TurnType(Enum):
    """Types of conversation turns."""

    USER = "user"
    """User message."""

    ASSISTANT = "assistant"
    """Assistant response."""

    SYSTEM = "system"
    """System context/instructions."""

    TOOL_CALL = "tool_call"
    """Tool invocation."""

    TOOL_RESULT = "tool_result"
    """Tool execution result."""

    SUMMARY = "summary"
    """Compressed summary of multiple turns."""

    LEARNING = "learning"
    """Extracted insight/fact."""

    CHECKPOINT = "checkpoint"
    """Saved state marker."""


@dataclass(frozen=True, slots=True)
class Turn:
    """A single turn in a conversation.

    Immutable and content-addressable - the hash uniquely identifies
    the content, enabling deduplication and DAG construction.
    """

    content: str
    """The actual message content."""

    turn_type: TurnType
    """Type of this turn."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this turn occurred."""

    # Provenance
    parent_ids: tuple[str, ...] = ()
    """IDs of parent turns (enables DAG structure)."""

    source: str | None = None
    """Where this content came from (file, tool, model, etc)."""

    # Metadata
    token_count: int = 0
    """Estimated tokens in this turn."""

    model: str | None = None
    """Model that generated this (for assistant turns)."""

    confidence: float | None = None
    """Confidence score (for learnings)."""

    tags: tuple[str, ...] = ()
    """Semantic tags for retrieval."""

    # Computed (cached)
    _hash: str | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        """Estimate tokens if not provided."""
        if self.token_count == 0 and self.content:
            object.__setattr__(self, "token_count", self.estimate_tokens(self.content))

    @property
    def id(self) -> str:
        """Content-addressable ID (blake2b hash).

        Same content = same ID, enabling O(1) deduplication.
        """
        if self._hash:
            return self._hash

        # Hash content + type + parents for uniqueness
        data = f"{self.turn_type.value}:{self.content}:{','.join(self.parent_ids)}"
        return hashlib.blake2b(data.encode(), digest_size=16).hexdigest()

    @property
    def is_compressible(self) -> bool:
        """Can this turn be compressed/summarized?"""
        return self.turn_type in {
            TurnType.USER,
            TurnType.ASSISTANT,
            TurnType.TOOL_RESULT,
        }

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Turn):
            return self.id == other.id
        return False

    def to_message(self) -> dict:
        """Convert to LLM message format."""
        role_map = {
            TurnType.USER: "user",
            TurnType.ASSISTANT: "assistant",
            TurnType.SYSTEM: "system",
            TurnType.TOOL_CALL: "assistant",
            TurnType.TOOL_RESULT: "tool",
            TurnType.SUMMARY: "system",
            TurnType.LEARNING: "system",
            TurnType.CHECKPOINT: "system",
        }

        return {
            "role": role_map.get(self.turn_type, "user"),
            "content": self.content,
        }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Roughly estimate token count (words * 1.3)."""
        if not text:
            return 0
        word_count = len(text.split())
        return max(1, int(word_count * 1.3))

    def compress(self, summary: str) -> Turn:
        """Create a compressed version of this turn."""
        return Turn(
            content=summary,
            turn_type=TurnType.SUMMARY,
            parent_ids=(self.id,),
            source=f"compressed:{self.id}",
            tags=self.tags,
        )


# =============================================================================
# RFC-122: Template Learning Support
# =============================================================================


@dataclass(frozen=True, slots=True)
class TemplateVariable:
    """A variable extractable from goal text (RFC-122).

    Used by TemplateData to parameterize task patterns.

    Example:
        >>> var = TemplateVariable(
        ...     name="entity",
        ...     description="Model name (User, Post, Product)",
        ...     var_type="string",
        ...     extraction_hints=("for {{entity}}", "{{entity}} API"),
        ... )
    """

    name: str
    """Variable name used in template patterns."""

    description: str
    """Human-readable description of what this variable represents."""

    var_type: Literal["string", "file", "choice"]
    """Type of variable for validation."""

    extraction_hints: tuple[str, ...]
    """Patterns that help extract this variable from goal text."""

    default: str | None = None
    """Default value if not extractable."""


@dataclass(frozen=True, slots=True)
class TemplateData:
    """Structural data for template-type learnings (RFC-122).

    Captures reusable task patterns that can be applied to similar goals.
    Integrates with RFC-067's produces/requires for dependency modeling.

    Example:
        >>> template = TemplateData(
        ...     name="CRUD Endpoint",
        ...     match_patterns=("CRUD", "REST", "endpoint"),
        ...     variables=(TemplateVariable(name="entity", ...),),
        ...     produces=("{{entity}}Model", "{{entity}}Routes"),
        ...     requires=("Database",),
        ...     expected_artifacts=("models/{{entity_lower}}.py",),
        ...     validation_commands=("pytest tests/test_{{entity_lower}}.py",),
        ... )
    """

    name: str
    """Human-readable name: 'CRUD Endpoint', 'Authentication'."""

    match_patterns: tuple[str, ...]
    """Keywords that suggest this template: ('CRUD', 'REST', 'endpoint')."""

    variables: tuple[TemplateVariable, ...]
    """Extractable variables from goal text."""

    produces: tuple[str, ...]
    """Artifacts this creates: ('{{entity}}Model', '{{entity}}Routes')."""

    requires: tuple[str, ...]
    """Prerequisites: ('Database',)."""

    expected_artifacts: tuple[str, ...]
    """Files that should be created: ('models/{{entity}}.py',)."""

    validation_commands: tuple[str, ...]
    """Commands to verify success: ('pytest tests/test_{{entity}}.py',)."""

    suggested_order: int = 50
    """Execution priority (lower = earlier)."""


# =============================================================================
# Learning (Extended RFC-122)
# =============================================================================


@dataclass(frozen=True, slots=True)
class Learning:
    """An extracted piece of knowledge from the conversation.

    Learnings are first-class citizens that persist even when
    the original conversation is compressed away.

    RFC-122: Extended with template and heuristic categories for
    compound learning. Templates capture structural task patterns,
    heuristics capture ordering/strategy hints.

    The `id` property remains based on `category:fact` for identity.
    New fields (template_data, embedding, use_count) are metadata
    that don't affect identity — same fact in same category = same learning.
    """

    fact: str
    """The actual learning/insight."""

    source_turns: tuple[str, ...]
    """Turn IDs this was extracted from."""

    confidence: float
    """How confident we are in this learning (0-1)."""

    category: Literal[
        "fact",        # "Uses FastAPI"
        "preference",  # "Prefers pytest"
        "constraint",  # "Tests required"
        "pattern",     # "Uses factory pattern"
        "dead_end",    # "Sync DB doesn't work"
        "template",    # RFC-122: Structural task patterns
        "heuristic",   # RFC-122: Ordering/strategy hints
    ]
    """Type of learning."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    superseded_by: str | None = None
    """If this learning was updated, pointer to newer version."""

    # RFC-122: Template-specific data (for category="template")
    template_data: TemplateData | None = None
    """Structural data for template-type learnings."""

    # RFC-122: Embedding for semantic retrieval (computed lazily)
    embedding: tuple[float, ...] | None = None
    """Pre-computed embedding for fast retrieval."""

    # RFC-122: Usage tracking
    use_count: int = 0
    """How many times this learning has been used."""

    last_used: str | None = None
    """Timestamp of last usage."""

    # Graph scoring fields (inspired by MIRA)
    mention_count: int = 0
    """Explicit agent references to this learning (strongest signal)."""

    activity_day_created: int = 0
    """Activity day when created (vacation-proof decay)."""

    activity_day_accessed: int = 0
    """Activity day of last access."""

    happens_at: str | None = None
    """ISO timestamp for time-sensitive content (deadlines)."""

    expires_at: str | None = None
    """ISO timestamp for expiring content."""

    @property
    def id(self) -> str:
        """Content-addressable ID.

        Based on category:fact only — metadata fields don't affect identity.
        """
        data = f"{self.category}:{self.fact}"
        return hashlib.blake2b(data.encode(), digest_size=12).hexdigest()

    def to_turn(self) -> Turn:
        """Convert to a Turn for context injection.

        Uses first-person voice to reduce epistemic distance.
        """
        prefix = self._first_person_prefix()
        return Turn(
            content=f"{prefix} {self.fact}",
            turn_type=TurnType.LEARNING,
            parent_ids=self.source_turns,
            confidence=self.confidence,
        )

    def _first_person_prefix(self) -> str:
        """Map category to first-person framing.

        First-person voice helps the agent treat learnings as its own
        memories rather than logs about someone else.
        """
        prefixes = {
            "fact": "I know:",
            "preference": "I prefer:",
            "constraint": "I must:",
            "pattern": "I use:",
            "dead_end": "I tried and it failed:",
            "template": "I follow this pattern:",
            "heuristic": "I've found:",
        }
        return prefixes.get(self.category, "I learned:")

    def with_usage(self, success: bool) -> Self:
        """Create a new Learning with updated usage stats (RFC-122).

        Args:
            success: Whether the task using this learning succeeded

        Returns:
            New Learning with updated use_count and confidence
        """
        new_confidence = self.confidence
        if success:
            new_confidence = min(1.0, self.confidence + 0.05)
        else:
            new_confidence = max(0.1, self.confidence - 0.1)

        return Learning(
            fact=self.fact,
            source_turns=self.source_turns,
            confidence=new_confidence,
            category=self.category,
            timestamp=self.timestamp,
            superseded_by=self.superseded_by,
            template_data=self.template_data,
            embedding=self.embedding,
            use_count=self.use_count + 1,
            last_used=datetime.now().isoformat(),
            mention_count=self.mention_count,
            activity_day_created=self.activity_day_created,
            activity_day_accessed=self.activity_day_accessed,
            happens_at=self.happens_at,
            expires_at=self.expires_at,
        )

    def with_embedding(self, embedding: tuple[float, ...]) -> Self:
        """Create a new Learning with computed embedding (RFC-122).

        Args:
            embedding: Pre-computed embedding vector

        Returns:
            New Learning with embedding set
        """
        return Learning(
            fact=self.fact,
            source_turns=self.source_turns,
            confidence=self.confidence,
            category=self.category,
            timestamp=self.timestamp,
            superseded_by=self.superseded_by,
            template_data=self.template_data,
            embedding=embedding,
            use_count=self.use_count,
            last_used=self.last_used,
            mention_count=self.mention_count,
            activity_day_created=self.activity_day_created,
            activity_day_accessed=self.activity_day_accessed,
            happens_at=self.happens_at,
            expires_at=self.expires_at,
        )

    def with_mention(self) -> Self:
        """Create a new Learning with incremented mention count.

        Mentions are explicit agent references - the strongest signal
        of memory importance. Call this when the agent explicitly
        references this learning in its output.

        Returns:
            New Learning with mention_count incremented
        """
        return Learning(
            fact=self.fact,
            source_turns=self.source_turns,
            confidence=self.confidence,
            category=self.category,
            timestamp=self.timestamp,
            superseded_by=self.superseded_by,
            template_data=self.template_data,
            embedding=self.embedding,
            use_count=self.use_count,
            last_used=self.last_used,
            mention_count=self.mention_count + 1,
            activity_day_created=self.activity_day_created,
            activity_day_accessed=self.activity_day_accessed,
            happens_at=self.happens_at,
            expires_at=self.expires_at,
        )

    def with_access(self, activity_day: int) -> Self:
        """Create a new Learning with updated access tracking.

        Call this when a learning is retrieved and used. Updates
        the access count, timestamp, and activity day for proper
        decay calculations.

        Args:
            activity_day: Current cumulative activity day

        Returns:
            New Learning with updated access tracking
        """
        return Learning(
            fact=self.fact,
            source_turns=self.source_turns,
            confidence=self.confidence,
            category=self.category,
            timestamp=self.timestamp,
            superseded_by=self.superseded_by,
            template_data=self.template_data,
            embedding=self.embedding,
            use_count=self.use_count + 1,
            last_used=datetime.now().isoformat(),
            mention_count=self.mention_count,
            activity_day_created=self.activity_day_created,
            activity_day_accessed=activity_day,
            happens_at=self.happens_at,
            expires_at=self.expires_at,
        )

    def with_activity_day_created(self, activity_day: int) -> Self:
        """Create a new Learning with activity day stamp.

        Call this when first creating a learning to stamp the
        activity day for proper newness boost calculations.

        Args:
            activity_day: Current cumulative activity day

        Returns:
            New Learning with activity_day_created set
        """
        return Learning(
            fact=self.fact,
            source_turns=self.source_turns,
            confidence=self.confidence,
            category=self.category,
            timestamp=self.timestamp,
            superseded_by=self.superseded_by,
            template_data=self.template_data,
            embedding=self.embedding,
            use_count=self.use_count,
            last_used=self.last_used,
            mention_count=self.mention_count,
            activity_day_created=activity_day,
            activity_day_accessed=self.activity_day_accessed,
            happens_at=self.happens_at,
            expires_at=self.expires_at,
        )
