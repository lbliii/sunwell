"""Function classifier for semantic pattern detection.

Classifies functions by naming patterns (language-agnostic).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto

from sunwell.research.types import CodeFragment


class FunctionCategory(Enum):
    """Categories of function purposes based on naming conventions."""

    CRUD = auto()  # create*, add*, delete*, remove*, update*, save*
    HANDLER = auto()  # on*, handle*, *Handler, *Listener
    PREDICATE = auto()  # is*, has*, can*, should*, *Filter
    GETTER = auto()  # get*, fetch*, load*, find*, retrieve*
    TRANSFORM = auto()  # filter*, map*, sort*, to*, convert*, parse*
    LIFECYCLE = auto()  # init*, setup*, destroy*, cleanup*, mount*, unmount*
    RENDER = auto()  # render*, draw*, display*, show*
    OTHER = auto()  # Uncategorized


@dataclass(frozen=True, slots=True)
class ClassifiedFragment:
    """A code fragment with its semantic category."""

    fragment: CodeFragment
    category: FunctionCategory


class FunctionClassifier:
    """Classify functions by naming patterns (language-agnostic).

    Uses prefix/suffix matching on function names to determine their
    likely purpose. This works across languages because developers
    use similar naming conventions everywhere.
    """

    # Prefixes that indicate each category (checked with startswith)
    PREFIXES: dict[FunctionCategory, tuple[str, ...]] = {
        FunctionCategory.CRUD: (
            "create",
            "add",
            "delete",
            "remove",
            "update",
            "save",
            "insert",
            "edit",
            "set",
            "put",
            "post",
            "patch",
            "clear",
            "toggle",
        ),
        FunctionCategory.HANDLER: (
            "on",
            "handle",
            "emit",
            "dispatch",
            "trigger",
            "fire",
            "click",
            "submit",
            "change",
            "input",
            "focus",
            "blur",
            "key",
            "mouse",
            "touch",
            "drag",
            "drop",
            "scroll",
        ),
        FunctionCategory.PREDICATE: (
            "is",
            "has",
            "can",
            "should",
            "will",
            "did",
            "was",
            "check",
            "validate",
            "verify",
            "test",
            "match",
            "equals",
            "contains",
        ),
        FunctionCategory.GETTER: (
            "get",
            "fetch",
            "load",
            "find",
            "retrieve",
            "read",
            "query",
            "select",
            "lookup",
            "resolve",
        ),
        FunctionCategory.TRANSFORM: (
            "filter",
            "map",
            "reduce",
            "sort",
            "to",
            "convert",
            "parse",
            "format",
            "serialize",
            "deserialize",
            "encode",
            "decode",
            "transform",
            "normalize",
            "denormalize",
            "extract",
            "merge",
            "split",
            "join",
            "concat",
        ),
        FunctionCategory.LIFECYCLE: (
            "init",
            "setup",
            "start",
            "stop",
            "destroy",
            "cleanup",
            "dispose",
            "mount",
            "unmount",
            "connect",
            "disconnect",
            "open",
            "close",
            "begin",
            "end",
            "reset",
            "configure",
            "bootstrap",
        ),
        FunctionCategory.RENDER: (
            "render",
            "draw",
            "display",
            "show",
            "hide",
            "paint",
            "print",
            "output",
            "view",
            "present",
        ),
    }

    # Suffixes that indicate each category (checked with endswith)
    SUFFIXES: dict[FunctionCategory, tuple[str, ...]] = {
        FunctionCategory.HANDLER: (
            "handler",
            "listener",
            "callback",
            "subscriber",
        ),
        FunctionCategory.PREDICATE: (
            "filter",
            "predicate",
            "validator",
            "checker",
        ),
        FunctionCategory.GETTER: (
            "getter",
            "loader",
            "fetcher",
            "finder",
        ),
        FunctionCategory.TRANSFORM: (
            "transformer",
            "converter",
            "parser",
            "formatter",
            "serializer",
            "mapper",
            "reducer",
        ),
    }

    def __init__(self) -> None:
        """Initialize classifier with compiled patterns."""
        # Build regex patterns for faster matching
        self._prefix_patterns: dict[FunctionCategory, re.Pattern[str]] = {}
        self._suffix_patterns: dict[FunctionCategory, re.Pattern[str]] = {}

        for category, prefixes in self.PREFIXES.items():
            # Match prefixes at start of name (case-insensitive)
            pattern = rf"^({'|'.join(re.escape(p) for p in prefixes)})"
            self._prefix_patterns[category] = re.compile(pattern, re.IGNORECASE)

        for category, suffixes in self.SUFFIXES.items():
            # Match suffixes at end of name (case-insensitive)
            pattern = rf"({'|'.join(re.escape(s) for s in suffixes)})$"
            self._suffix_patterns[category] = re.compile(pattern, re.IGNORECASE)

    def classify(self, name: str) -> FunctionCategory:
        """Classify a function name into a category.

        Args:
            name: The function name to classify.

        Returns:
            The most likely category for this function.
        """
        if not name:
            return FunctionCategory.OTHER

        # Normalize: remove leading underscore(s) for private methods
        normalized = name.lstrip("_")
        if not normalized:
            return FunctionCategory.OTHER

        # Check prefixes first (more reliable)
        for category, pattern in self._prefix_patterns.items():
            if pattern.match(normalized):
                return category

        # Then check suffixes
        for category, pattern in self._suffix_patterns.items():
            if pattern.search(normalized):
                return category

        return FunctionCategory.OTHER

    def classify_fragment(self, fragment: CodeFragment) -> ClassifiedFragment:
        """Classify a code fragment.

        Args:
            fragment: The code fragment to classify.

        Returns:
            ClassifiedFragment with the fragment and its category.
        """
        category = self.classify(fragment.name) if fragment.name else FunctionCategory.OTHER
        return ClassifiedFragment(fragment=fragment, category=category)

    def classify_fragments(
        self,
        fragments: Sequence[CodeFragment],
    ) -> dict[FunctionCategory, list[CodeFragment]]:
        """Group fragments by category.

        Args:
            fragments: Sequence of code fragments to classify.

        Returns:
            Dict mapping categories to lists of fragments in that category.
        """
        result: dict[FunctionCategory, list[CodeFragment]] = {
            category: [] for category in FunctionCategory
        }

        for fragment in fragments:
            # Skip fragments without names (imports, exports, etc.)
            if not fragment.name:
                continue

            category = self.classify(fragment.name)
            result[category].append(fragment)

        return result

    def get_category_summary(
        self,
        fragments: Sequence[CodeFragment],
    ) -> dict[FunctionCategory, list[str]]:
        """Get a summary of function names by category.

        Args:
            fragments: Sequence of code fragments to classify.

        Returns:
            Dict mapping categories to lists of function names.
        """
        classified = self.classify_fragments(fragments)
        return {
            category: [f.name for f in frags if f.name]
            for category, frags in classified.items()
            if frags
        }
