"""Team Intelligence Types - RFC-052.

Core data types for team-shared knowledge. These types mirror the personal
intelligence types (RFC-045) but with team-specific fields for attribution,
endorsements, and sharing metadata.

Key distinction:
- RFC-045 Decision → personal decisions stored in .sunwell/intelligence/
- RFC-052 TeamDecision → team decisions stored in .sunwell/team/
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

# Re-export RejectedOption from intelligence for compatibility
from sunwell.intelligence.decisions import RejectedOption

__all__ = [
    "KnowledgeScope",
    "RejectedOption",
    "TeamDecision",
    "TeamFailure",
    "TeamPatterns",
    "TeamOwnership",
    "TeamKnowledgeContext",
    "TeamKnowledgeUpdate",
]


class KnowledgeScope(Enum):
    """Where knowledge is stored and shared."""

    PERSONAL = "personal"  # Local only, gitignored
    TEAM = "team"  # Git-tracked, shared
    PROJECT = "project"  # Git-tracked, auto-generated


@dataclass(frozen=True, slots=True)
class TeamDecision:
    """An architectural decision shared across the team.

    Related to RFC-045 Decision but with team-specific fields.
    Can be promoted from personal Decision via KnowledgePropagator.
    """

    id: str
    """Unique identifier (hash of context + choice)."""

    category: str
    """Category: 'database', 'auth', 'framework', 'pattern', etc."""

    question: str
    """What decision was being made."""

    choice: str
    """What was chosen."""

    rejected: tuple[RejectedOption, ...]
    """Options that were considered but rejected."""

    rationale: str
    """Why this choice was made."""

    confidence: float
    """How confident the team is this is the right choice (0.0-1.0)."""

    # === Team Metadata ===

    author: str
    """Who made this decision (git username or email)."""

    timestamp: datetime
    """When decision was made."""

    supersedes: str | None = None
    """ID of decision this replaces (if changed)."""

    endorsements: tuple[str, ...] = ()
    """Team members who endorsed this decision."""

    applies_until: datetime | None = None
    """Expiration date for temporary decisions."""

    tags: tuple[str, ...] = ()
    """Tags for categorization and search."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        result: dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "choice": self.choice,
            "rejected": [
                {
                    "option": r.option,
                    "reason": r.reason,
                    "might_reconsider_when": r.might_reconsider_when,
                }
                for r in self.rejected
            ],
            "rationale": self.rationale,
            "confidence": self.confidence,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "supersedes": self.supersedes,
            "endorsements": list(self.endorsements),
            "tags": list(self.tags),
        }
        if self.applies_until:
            result["applies_until"] = self.applies_until.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamDecision:
        """Deserialize from dictionary."""
        applies_until = None
        if data.get("applies_until"):
            applies_until = datetime.fromisoformat(data["applies_until"])

        return cls(
            id=data["id"],
            category=data["category"],
            question=data["question"],
            choice=data["choice"],
            rejected=tuple(
                RejectedOption(
                    option=r["option"],
                    reason=r["reason"],
                    might_reconsider_when=r.get("might_reconsider_when"),
                )
                for r in data.get("rejected", [])
            ),
            rationale=data["rationale"],
            confidence=data.get("confidence", 0.8),
            author=data["author"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            supersedes=data.get("supersedes"),
            endorsements=tuple(data.get("endorsements", [])),
            applies_until=applies_until,
            tags=tuple(data.get("tags", [])),
        )

    def to_text(self) -> str:
        """Convert to text for embedding/search."""
        parts = [
            f"Category: {self.category}",
            f"Question: {self.question}",
            f"Choice: {self.choice}",
            f"Rationale: {self.rationale}",
            f"Author: {self.author}",
        ]
        if self.rejected:
            parts.append("Rejected options:")
            for r in self.rejected:
                parts.append(f"  - {r.option}: {r.reason}")
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class TeamFailure:
    """A failure pattern shared across the team."""

    id: str
    """Unique identifier."""

    description: str
    """What approach failed."""

    error_type: str
    """Type of failure."""

    root_cause: str
    """Why it failed."""

    prevention: str
    """How to avoid this in the future."""

    # === Team Metadata ===

    author: str
    """Who discovered this failure."""

    timestamp: datetime
    """When failure was recorded."""

    occurrences: int = 1
    """How many times this has been hit across team."""

    affected_files: tuple[str, ...] = ()
    """Files/modules where this failure applies."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "description": self.description,
            "error_type": self.error_type,
            "root_cause": self.root_cause,
            "prevention": self.prevention,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "occurrences": self.occurrences,
            "affected_files": list(self.affected_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamFailure:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            error_type=data["error_type"],
            root_cause=data["root_cause"],
            prevention=data["prevention"],
            author=data["author"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            occurrences=data.get("occurrences", 1),
            affected_files=tuple(data.get("affected_files", [])),
        )

    def to_text(self) -> str:
        """Convert to text for embedding/search."""
        parts = [
            f"Description: {self.description}",
            f"Error: {self.error_type}",
            f"Root cause: {self.root_cause}",
            f"Prevention: {self.prevention}",
        ]
        if self.affected_files:
            parts.append(f"Affected files: {', '.join(self.affected_files)}")
        return "\n".join(parts)


@dataclass
class TeamPatterns:
    """Enforced code patterns for the team."""

    naming_conventions: dict[str, str] = field(default_factory=dict)
    """{'function': 'snake_case', 'class': 'PascalCase'}"""

    import_style: Literal["absolute", "relative", "mixed"] = "absolute"
    """Enforced import style."""

    type_annotation_level: Literal["none", "public", "all"] = "public"
    """Required type annotation level."""

    docstring_style: Literal["google", "numpy", "sphinx", "none"] = "google"
    """Enforced docstring format."""

    test_requirements: dict[str, str] = field(default_factory=dict)
    """{'new_functions': 'required', 'bug_fixes': 'required'}"""

    # === Enforcement ===

    enforcement_level: Literal["suggest", "warn", "enforce"] = "suggest"
    """How strictly to apply patterns."""

    exceptions: dict[str, str] = field(default_factory=dict)
    """Paths exempt from specific patterns."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for YAML storage."""
        return {
            "naming_conventions": self.naming_conventions,
            "import_style": self.import_style,
            "type_annotation_level": self.type_annotation_level,
            "docstring_style": self.docstring_style,
            "test_requirements": self.test_requirements,
            "enforcement_level": self.enforcement_level,
            "exceptions": self.exceptions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamPatterns:
        """Deserialize from dictionary."""
        return cls(
            naming_conventions=data.get("naming_conventions", {}),
            import_style=data.get("import_style", "absolute"),
            type_annotation_level=data.get("type_annotation_level", "public"),
            docstring_style=data.get("docstring_style", "google"),
            test_requirements=data.get("test_requirements", {}),
            enforcement_level=data.get("enforcement_level", "suggest"),
            exceptions=data.get("exceptions", {}),
        )


@dataclass
class TeamOwnership:
    """Ownership mapping for files and modules."""

    # path_pattern → owner(s)
    owners: dict[str, list[str]] = field(default_factory=dict)
    """{'src/billing/*': ['alice', 'bob'], 'src/auth/*': ['carol']}"""

    # owner → areas of expertise
    expertise: dict[str, list[str]] = field(default_factory=dict)
    """{'alice': ['payments', 'billing'], 'bob': ['auth', 'security']}"""

    # Required reviewers for paths
    required_reviewers: dict[str, list[str]] = field(default_factory=dict)
    """{'src/billing/*': ['alice']}"""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for YAML storage."""
        return {
            "owners": self.owners,
            "expertise": self.expertise,
            "required_reviewers": self.required_reviewers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamOwnership:
        """Deserialize from dictionary."""
        return cls(
            owners=data.get("owners", {}),
            expertise=data.get("expertise", {}),
            required_reviewers=data.get("required_reviewers", {}),
        )


@dataclass(frozen=True, slots=True)
class TeamKnowledgeUpdate:
    """Notification of new team knowledge."""

    type: Literal["decision", "failure", "pattern", "ownership"]
    summary: str
    author: str
    detail: str


@dataclass
class TeamKnowledgeContext:
    """Team knowledge relevant to current context."""

    decisions: list[TeamDecision] = field(default_factory=list)
    failures: list[TeamFailure] = field(default_factory=list)
    patterns: TeamPatterns | None = None

    def format_for_prompt(self) -> str:
        """Format team knowledge for inclusion in LLM prompt."""
        parts = []

        if self.decisions:
            parts.append("## Team Decisions\n")
            for d in self.decisions:
                parts.append(f"- **{d.question}**: {d.choice} (by {d.author})")
                if d.rationale:
                    parts.append(f"  Rationale: {d.rationale}")

        if self.failures:
            parts.append("\n## Team Failure Patterns\n")
            for f in self.failures:
                parts.append(f"- ⚠️ **{f.description}** (hit {f.occurrences}x)")
                parts.append(f"  Prevention: {f.prevention}")

        if self.patterns and self.patterns.enforcement_level != "none":
            parts.append("\n## Team Patterns\n")
            parts.append(f"- Naming: {self.patterns.naming_conventions}")
            parts.append(f"- Docstrings: {self.patterns.docstring_style}")

        return "\n".join(parts)
