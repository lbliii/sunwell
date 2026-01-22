"""Pattern Learning - RFC-045 Phase 3 + RFC-050 Bootstrap Extensions.

Learn user preferences through implicit feedback from edits and acceptances.

RFC-050 adds:
- bootstrap() classmethod to create profile from bootstrap analysis
- line_length, formatter, linter fields from config scanning
- Methods to handle bootstrap pattern overrides from user edits
"""


import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.bootstrap.types import BootstrapPatterns


@dataclass
class PatternProfile:
    """Learned patterns for a user/project.

    Storage: `.sunwell/intelligence/patterns.json`
    """

    # === Code Style ===

    naming_conventions: dict[str, str] = field(default_factory=dict)
    """{'function': 'snake_case', 'class': 'PascalCase', 'constant': 'UPPER_SNAKE'}"""

    import_style: Literal["absolute", "relative", "mixed"] = "absolute"
    """Preferred import style."""

    type_annotation_level: Literal["none", "public", "all"] = "public"
    """How much type annotation to use."""

    docstring_style: Literal["google", "numpy", "sphinx", "none"] = "google"
    """Docstring format preference."""

    # === RFC-050: Config-derived patterns ===

    line_length: int = 100
    """Configured line length (from pyproject.toml or similar)."""

    formatter: str | None = None
    """Detected formatter: 'ruff', 'black', 'yapf', 'autopep8', or None."""

    linter: str | None = None
    """Detected linter: 'ruff', 'flake8', 'pylint', or None."""

    type_checker: str | None = None
    """Detected type checker: 'mypy', 'pyright', 'ty', or None."""

    # === Architecture Preferences ===

    abstraction_level: float = 0.5
    """0.0 = concrete/simple, 1.0 = abstract/enterprise. Learned from feedback."""

    test_preference: Literal["tdd", "after", "minimal", "none"] = "after"
    """When/how much to write tests."""

    error_handling: Literal["exceptions", "result_types", "mixed"] = "exceptions"
    """Error handling style."""

    # === Communication Preferences ===

    explanation_verbosity: float = 0.5
    """0.0 = terse, 1.0 = detailed. Learned from "too much"/"not enough" feedback."""

    code_comment_level: float = 0.5
    """0.0 = no comments, 1.0 = heavily commented."""

    prefers_questions: bool = False
    """Does user prefer being asked, or just getting answers?"""

    # === Learning Source ===

    confidence: dict[str, float] = field(default_factory=dict)
    """Confidence in each learned pattern (0.0-1.0)."""

    evidence: dict[str, list[str]] = field(default_factory=dict)
    """Evidence for each pattern (session IDs where learned)."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "naming_conventions": self.naming_conventions,
            "import_style": self.import_style,
            "type_annotation_level": self.type_annotation_level,
            "docstring_style": self.docstring_style,
            # RFC-050: Config-derived patterns
            "line_length": self.line_length,
            "formatter": self.formatter,
            "linter": self.linter,
            "type_checker": self.type_checker,
            # Architecture preferences
            "abstraction_level": self.abstraction_level,
            "test_preference": self.test_preference,
            "error_handling": self.error_handling,
            "explanation_verbosity": self.explanation_verbosity,
            "code_comment_level": self.code_comment_level,
            "prefers_questions": self.prefers_questions,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PatternProfile:
        """Deserialize from dictionary."""
        return cls(
            naming_conventions=data.get("naming_conventions", {}),
            import_style=data.get("import_style", "absolute"),
            type_annotation_level=data.get("type_annotation_level", "public"),
            docstring_style=data.get("docstring_style", "google"),
            # RFC-050: Config-derived patterns
            line_length=data.get("line_length", 100),
            formatter=data.get("formatter"),
            linter=data.get("linter"),
            type_checker=data.get("type_checker"),
            # Architecture preferences
            abstraction_level=data.get("abstraction_level", 0.5),
            test_preference=data.get("test_preference", "after"),
            error_handling=data.get("error_handling", "exceptions"),
            explanation_verbosity=data.get("explanation_verbosity", 0.5),
            code_comment_level=data.get("code_comment_level", 0.5),
            prefers_questions=data.get("prefers_questions", False),
            confidence=data.get("confidence", {}),
            evidence=data.get("evidence", {}),
        )

    @classmethod
    def bootstrap(cls, patterns: BootstrapPatterns) -> PatternProfile:
        """Create profile from bootstrap analysis (RFC-050).

        All patterns marked with:
        - confidence < 0.8 (can be overridden by edits)
        - evidence from "bootstrap:*" sources

        Args:
            patterns: Bootstrap patterns from code/config analysis

        Returns:
            PatternProfile pre-populated from bootstrap
        """
        # Build confidence dict (bootstrap patterns have lower confidence)
        confidence = {
            "naming_conventions": 0.75,
            "import_style": 0.70,
            "type_annotation_level": 0.80,
            "docstring_style": patterns.docstring_consistency,  # Use actual consistency
            "line_length": 0.90,  # Config is reliable
            "formatter": 0.90,
            "linter": 0.90,
            "type_checker": 0.90,
        }

        # Build evidence dict
        evidence = {
            "naming_conventions": ["bootstrap:code_analysis"],
            "import_style": ["bootstrap:code_analysis"],
            "type_annotation_level": ["bootstrap:code_analysis"],
            "docstring_style": ["bootstrap:code_analysis"],
            "line_length": ["bootstrap:config_scan"],
            "formatter": ["bootstrap:config_scan"],
            "linter": ["bootstrap:config_scan"],
            "type_checker": ["bootstrap:config_scan"],
        }

        return cls(
            naming_conventions=patterns.naming_conventions,
            import_style=patterns.import_style,
            type_annotation_level=patterns.type_annotation_level,
            docstring_style=patterns.docstring_style,
            line_length=patterns.line_length,
            formatter=patterns.formatter,
            linter=patterns.linter,
            type_checker=patterns.type_checker,
            confidence=confidence,
            evidence=evidence,
        )

    @classmethod
    def load(cls, base_path: Path) -> PatternProfile:
        """Load pattern profile from disk."""
        patterns_path = base_path / "patterns.json"
        if patterns_path.exists():
            try:
                with open(patterns_path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, OSError):
                pass
        return cls()

    def save(self, base_path: Path) -> None:
        """Save pattern profile to disk."""
        patterns_path = base_path / "patterns.json"
        base_path.mkdir(parents=True, exist_ok=True)
        with open(patterns_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


class PatternLearner:
    """Learns patterns from implicit user feedback."""

    def learn_from_edit(
        self,
        original: str,
        edited: str,
        profile: PatternProfile,
        session_id: str = "",
    ) -> PatternProfile:
        """User edited AI output → learn what they changed.

        If edit contradicts a bootstrap pattern:
        - Override bootstrap pattern
        - Upgrade confidence to 0.85 (user-confirmed)

        Args:
            original: Original code from AI
            edited: User's edited version
            profile: Current pattern profile
            session_id: Session identifier for evidence tracking

        Returns:
            Updated pattern profile
        """
        # Detect naming convention changes
        self._learn_naming(original, edited, profile, session_id)

        # Detect type annotation changes
        self._learn_type_annotations(original, edited, profile, session_id)

        # Detect comment changes
        self._learn_comments(original, edited, profile, session_id)

        # Detect docstring style
        self._learn_docstring_style(edited, profile, session_id)

        return profile

    def _upgrade_from_bootstrap(
        self,
        profile: PatternProfile,
        field: str,
        session_id: str,
    ) -> None:
        """Upgrade a bootstrap pattern to user-confirmed confidence.

        Called when user edit confirms or overrides a bootstrap pattern.
        """
        if field in profile.evidence:
            evidence_list = profile.evidence[field]
            if any("bootstrap:" in e for e in evidence_list):
                # This was a bootstrap pattern, upgrade to user-confirmed
                profile.evidence[field] = [session_id] if session_id else ["user_edit"]
                profile.confidence[field] = 0.85

    def _learn_naming(
        self,
        original: str,
        edited: str,
        profile: PatternProfile,
        session_id: str,
    ) -> None:
        """Learn naming conventions from edits."""
        # Extract function names
        original_funcs = self._extract_function_names(original)
        edited_funcs = self._extract_function_names(edited)

        # Compare naming styles
        for orig_name, edit_name in zip(original_funcs, edited_funcs, strict=False):
            if orig_name != edit_name:
                # Detect style change
                orig_style = self._detect_naming_style(orig_name)
                edit_style = self._detect_naming_style(edit_name)

                if orig_style != edit_style:
                    profile.naming_conventions["function"] = edit_style
                    profile.confidence["naming_function"] = min(
                        profile.confidence.get("naming_function", 0.6) + 0.1,
                        1.0,
                    )
                    if session_id:
                        profile.evidence.setdefault("naming_function", []).append(
                            session_id
                        )

    def _learn_type_annotations(
        self,
        original: str,
        edited: str,
        profile: PatternProfile,
        session_id: str,
    ) -> None:
        """Learn type annotation preferences."""
        orig_has_types = ":" in original and "->" in original
        edit_has_types = ":" in edited and "->" in edited

        if not orig_has_types and edit_has_types:
            # User added type annotations
            profile.type_annotation_level = "all"
            profile.confidence["type_annotations"] = min(
                profile.confidence.get("type_annotations", 0.6) + 0.1,
                1.0,
            )
            if session_id:
                profile.evidence.setdefault("type_annotations", []).append(session_id)
        elif orig_has_types and not edit_has_types:
            # User removed type annotations
            profile.type_annotation_level = "none"
            profile.confidence["type_annotations"] = min(
                profile.confidence.get("type_annotations", 0.6) + 0.1,
                1.0,
            )
            if session_id:
                profile.evidence.setdefault("type_annotations", []).append(session_id)

    def _learn_comments(
        self,
        original: str,
        edited: str,
        profile: PatternProfile,
        session_id: str,
    ) -> None:
        """Learn comment preferences."""
        orig_comments = original.count("#") + original.count('"""') + original.count("'''")
        edit_comments = edited.count("#") + edited.count('"""') + edited.count("'''")

        if edit_comments < orig_comments:
            # User removed comments
            profile.code_comment_level = max(0.0, profile.code_comment_level - 0.1)
        elif edit_comments > orig_comments:
            # User added comments
            profile.code_comment_level = min(1.0, profile.code_comment_level + 0.1)

    def _learn_docstring_style(
        self,
        code: str,
        profile: PatternProfile,
        session_id: str,
    ) -> None:
        """Detect docstring style from code."""
        # Look for docstrings
        docstring_match = re.search(r'"""(.*?)"""', code, re.DOTALL)
        if not docstring_match:
            return

        docstring = docstring_match.group(1)

        # Detect style
        if "Args:" in docstring and "Returns:" in docstring:
            style = "google"
        elif "Parameters" in docstring and "Returns" in docstring:
            style = "numpy"
        elif ":param" in docstring or ":return:" in docstring:
            style = "sphinx"
        else:
            style = "none"

        if style != "none":
            profile.docstring_style = style
            profile.confidence["docstring_style"] = min(
                profile.confidence.get("docstring_style", 0.7) + 0.1,
                1.0,
            )
            if session_id:
                profile.evidence.setdefault("docstring_style", []).append(session_id)

    def _extract_function_names(self, code: str) -> list[str]:
        """Extract function names from code."""
        try:
            tree = ast.parse(code)
            return [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]
        except SyntaxError:
            return []

    def _detect_naming_style(self, name: str) -> str:
        """Detect naming convention style."""
        if "_" in name:
            return "snake_case"
        elif name[0].isupper() if name else False:
            return "PascalCase"
        elif name.isupper():
            return "UPPER_SNAKE"
        else:
            return "camelCase"

    def learn_from_rejection(
        self,
        rejected_output: str,
        reason: str | None,
        profile: PatternProfile,
        session_id: str = "",
    ) -> PatternProfile:
        """User rejected output → learn what was wrong.

        Args:
            rejected_output: Code that was rejected
            reason: Optional reason for rejection
            profile: Current pattern profile
            session_id: Session identifier

        Returns:
            Updated pattern profile
        """
        # If reason mentions "too verbose", reduce verbosity
        if reason and "verbose" in reason.lower():
            profile.explanation_verbosity = max(0.0, profile.explanation_verbosity - 0.1)

        # If reason mentions "not enough detail", increase verbosity
        if reason and ("detail" in reason.lower() or "explain" in reason.lower()):
            profile.explanation_verbosity = min(1.0, profile.explanation_verbosity + 0.1)

        return profile

    def learn_from_acceptance(
        self,
        accepted_output: str,
        profile: PatternProfile,
        session_id: str = "",
    ) -> PatternProfile:
        """User accepted output without edits → reinforce patterns.

        Args:
            accepted_output: Code that was accepted
            profile: Current pattern profile
            session_id: Session identifier

        Returns:
            Updated pattern profile (reinforced confidence)
        """
        # Reinforce existing patterns
        for key in profile.confidence:
            profile.confidence[key] = min(profile.confidence[key] + 0.05, 1.0)

        return profile
