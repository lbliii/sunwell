"""Shared schema type definitions — enums and simple dataclasses.

These types were originally in core.types.types but belong in foundation
since they are used by the lens schema model and loader.

Only the types needed by foundation are here. Types that are NOT needed
by foundation (e.g., Confidence, IntentCategory, error types) remain
in core.types.types.
"""


import re
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """Validation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Tier(Enum):
    """Router execution tiers."""

    FAST_PATH = 0  # No retrieval, no validation
    STANDARD = 1  # Retrieval + basic validation
    DEEP_LENS = 2  # Full retrieval + personas + refinement


class ValidationMethod(Enum):
    """Heuristic validation methods."""

    TRIANGULATION = "triangulation"
    PATTERN_MATCH = "pattern_match"
    CHECKLIST = "checklist"


@dataclass(frozen=True, slots=True)
class SemanticVersion:
    """Semantic version for lens versioning."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version

    def __lt__(self, other: SemanticVersion) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: SemanticVersion) -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    @classmethod
    def parse(cls, version_str: str) -> SemanticVersion:
        """Parse a semver string like '1.2.3' or '1.2.3-beta'."""
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$"
        match = re.match(pattern, version_str)
        if not match:
            raise ValueError(f"Invalid semver: {version_str}")
        major, minor, patch, prerelease = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
        )


@dataclass(frozen=True, slots=True)
class LensReference:
    """Reference to a lens (local path or fount reference)."""

    source: str  # e.g., "sunwell/tech-writer", "./my.lens"
    version: str | None = None  # e.g., "^1.0", "2.0.0"
    priority: int = 1  # For composition ordering

    @property
    def is_local(self) -> bool:
        return self.source.startswith("./") or self.source.startswith("/")

    @property
    def is_fount(self) -> bool:
        return not self.is_local
