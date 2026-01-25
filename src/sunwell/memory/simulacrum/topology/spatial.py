# src/sunwell/simulacrum/spatial.py
"""Spatial memory - tracks WHERE content exists.

Spatial context answers: "Where is this information located?"
- Documents: file path, line range, section path, heading level
- Code: module path, class/function name, scope depth
- External: URL, anchor

Part of RFC-014: Multi-Topology Memory.
"""


import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Future type imports


class PositionType(Enum):
    """Type of positional context."""

    DOCUMENT = "document"     # Markdown, RST, etc.
    CODE = "code"             # Source code
    CONVERSATION = "conversation"  # Chat turn
    EXTERNAL = "external"     # URL, API response, etc.


@dataclass(frozen=True, slots=True)
class SpatialContext:
    """Position metadata for spatial-aware retrieval.

    Answers: "Where is this information located?"
    """

    position_type: PositionType

    # === Document Position ===
    file_path: str | None = None
    """Relative path to source file."""

    line_range: tuple[int, int] = (0, 0)
    """Line numbers (1-indexed, inclusive)."""

    char_range: tuple[int, int] = (0, 0)
    """Character offsets within file."""

    # === Hierarchical Position ===
    section_path: tuple[str, ...] = ()
    """Path through document headings: ("Architecture", "Data Flow", "Caching")."""

    heading_level: int = 0
    """Heading depth: H1=1, H2=2, etc. 0 = not under a heading."""

    # === Code Position ===
    module_path: str | None = None
    """Python module path: sunwell.simulacrum.spatial"""

    class_name: str | None = None
    """Containing class name."""

    function_name: str | None = None
    """Containing function/method name."""

    scope_depth: int = 0
    """Nesting level (0 = module level, 1 = class level, etc.)."""

    # === External Position ===
    url: str | None = None
    """Source URL for external content."""

    anchor: str | None = None
    """URL fragment/anchor."""

    def __str__(self) -> str:
        """Human-readable position string."""
        if self.position_type == PositionType.DOCUMENT:
            path = " > ".join(self.section_path) if self.section_path else ""
            return f"{self.file_path}:{self.line_range[0]} [{path}]"
        elif self.position_type == PositionType.CODE:
            parts = [self.module_path, self.class_name, self.function_name]
            return ".".join(p for p in parts if p)
        elif self.position_type == PositionType.EXTERNAL:
            return f"{self.url}#{self.anchor}" if self.anchor else self.url or ""
        return f"turn:{self.line_range[0]}"


@dataclass(frozen=True, slots=True)
class SpatialQuery:
    """Query constraints for spatial retrieval."""

    # File constraints
    file_pattern: str | None = None
    """Glob pattern for file paths: "docs/*.md", "src/sunwell/**"."""

    # Section constraints
    section_contains: str | None = None
    """Section path must contain this string: "Limitations"."""

    heading_level_max: int | None = None
    """Only content under headings at this level or deeper."""

    # Code constraints
    module_prefix: str | None = None
    """Module must start with: "sunwell.simulacrum"."""

    in_class: str | None = None
    """Must be within this class."""

    in_function: str | None = None
    """Must be within this function."""

    # Line constraints
    line_range: tuple[int, int] | None = None
    """Restrict to line range."""


def spatial_match(context: SpatialContext, query: SpatialQuery) -> float:
    """Score how well a spatial context matches a query.

    Returns: 0.0 (no match) to 1.0 (perfect match).

    Complexity: O(1) per node — constant-time field comparisons.
    """
    if not query:
        return 1.0  # No constraints = everything matches

    score = 1.0
    checks = 0

    # File pattern — O(m) where m is path length
    if query.file_pattern and context.file_path:
        if fnmatch.fnmatch(context.file_path, query.file_pattern):
            checks += 1
        else:
            return 0.0  # Hard filter

    # Section contains
    if query.section_contains and context.section_path:
        section_str = " > ".join(context.section_path).lower()
        if query.section_contains.lower() in section_str:
            checks += 1
        else:
            return 0.0  # Hard filter

    # Heading level
    if query.heading_level_max is not None:
        if context.heading_level > 0 and context.heading_level <= query.heading_level_max:
            checks += 1
        elif context.heading_level == 0:
            pass  # No penalty for unheaded content
        else:
            score *= 0.5  # Soft penalty

    # Module prefix
    if query.module_prefix and context.module_path:
        if context.module_path.startswith(query.module_prefix):
            checks += 1
        else:
            return 0.0  # Hard filter

    # Class constraint
    if query.in_class:
        if context.class_name == query.in_class:
            checks += 1
        else:
            return 0.0

    # Function constraint
    if query.in_function:
        if context.function_name == query.in_function:
            checks += 1
        else:
            return 0.0

    return score
