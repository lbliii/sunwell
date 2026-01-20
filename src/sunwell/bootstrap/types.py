"""Bootstrap Types — RFC-050.

All dataclasses for bootstrap evidence, inference, and results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

# =============================================================================
# Git Evidence Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class CommitInfo:
    """Parsed commit information."""

    sha: str
    author: str
    date: datetime
    message: str
    files_changed: tuple[Path, ...]

    # Detected signals
    is_decision: bool
    """Commit message contains decision language."""

    is_fix: bool
    """Commit message indicates fix (fix:, bugfix, etc.)."""

    is_refactor: bool
    """Commit message indicates refactoring."""

    mentioned_files: tuple[str, ...]
    """Files/modules explicitly mentioned in message."""


@dataclass(frozen=True, slots=True)
class BlameRegion:
    """A region of code with authorship information."""

    start_line: int
    end_line: int
    author: str
    date: datetime
    commit_sha: str


@dataclass(frozen=True, slots=True)
class ContributorStats:
    """Statistics for a contributor."""

    author: str
    commits: int
    lines_added: int
    lines_deleted: int
    files_touched: int
    first_commit: datetime
    last_commit: datetime


@dataclass(frozen=True, slots=True)
class BranchPatterns:
    """Branch naming and merge patterns."""

    main_branch: str
    """Name of main branch (main, master, develop)."""

    uses_feature_branches: bool
    """Whether feature branches are used."""

    branch_prefix_pattern: str | None
    """Common prefix pattern (feature/, fix/, etc.)."""


@dataclass(frozen=True, slots=True)
class GitEvidence:
    """Evidence extracted from git history."""

    commits: tuple[CommitInfo, ...]
    """Recent commits with parsed metadata."""

    blame_map: dict[Path, list[BlameRegion]]
    """File → blame regions for ownership."""

    contributor_stats: dict[str, ContributorStats]
    """Author → contribution statistics."""

    change_frequency: dict[Path, float]
    """File → changes per month (churn)."""

    branch_patterns: BranchPatterns
    """Branch naming, merge patterns."""


# =============================================================================
# Code Evidence Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class NamingPatterns:
    """Detected naming conventions with evidence counts."""

    function_style: Literal["snake_case", "camelCase", "mixed"]
    function_samples: int

    class_style: Literal["PascalCase", "camelCase", "mixed"]
    class_samples: int

    constant_style: Literal["UPPER_SNAKE", "lower_snake", "mixed"]
    constant_samples: int

    private_prefix: Literal["_", "__", "none", "mixed"]
    private_samples: int


@dataclass(frozen=True, slots=True)
class ImportPatterns:
    """Import organization style."""

    style: Literal["absolute", "relative", "mixed"]
    """Detected import style."""

    groups_stdlib: bool
    """Whether stdlib imports are grouped."""

    groups_third_party: bool
    """Whether third-party imports are grouped."""

    samples: int
    """Number of files analyzed."""


@dataclass(frozen=True, slots=True)
class TypeHintUsage:
    """Type annotation prevalence analysis."""

    level: Literal["none", "minimal", "public_only", "comprehensive"]
    """Detected level of type hint usage."""

    functions_with_hints: int
    functions_total: int

    uses_modern_syntax: bool
    """Uses list[] vs List[], str | None vs Optional."""


@dataclass(frozen=True, slots=True)
class DocstringStyle:
    """Docstring format analysis."""

    style: Literal["google", "numpy", "sphinx", "none", "mixed"]
    """Detected docstring format."""

    samples: int
    """Number of docstrings analyzed."""

    consistency: float
    """How consistent the style is (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class ModuleStructure:
    """Directory organization patterns."""

    has_src_layout: bool
    """Uses src/ layout."""

    has_tests_dir: bool
    """Has tests/ directory."""

    package_name: str | None
    """Detected main package name."""

    modules: tuple[str, ...]
    """List of module names."""

    functions: tuple[str, ...]
    """List of function names (for codebase graph)."""

    classes: tuple[str, ...]
    """List of class names (for codebase graph)."""


@dataclass(frozen=True, slots=True)
class TestPatterns:
    """Testing conventions and patterns."""

    framework: Literal["pytest", "unittest", "nose", "none"]
    """Detected test framework."""

    uses_fixtures: bool
    """Whether pytest fixtures are used."""

    uses_mocks: bool
    """Whether mocking is used."""

    test_count: int
    """Number of test functions found."""


@dataclass(frozen=True, slots=True)
class CodeEvidence:
    """Evidence extracted from code analysis."""

    naming_patterns: NamingPatterns
    """Detected naming conventions."""

    import_patterns: ImportPatterns
    """Import organization style."""

    type_hint_usage: TypeHintUsage
    """Type annotation prevalence."""

    docstring_style: DocstringStyle
    """Docstring format (Google, NumPy, Sphinx, none)."""

    module_structure: ModuleStructure
    """Directory organization patterns."""

    test_patterns: TestPatterns
    """Testing conventions and coverage."""


# =============================================================================
# Documentation Evidence Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArchitectureSection:
    """A section describing architecture or design."""

    source_file: Path
    heading: str
    content: str
    mentions_modules: tuple[str, ...]
    """Module names mentioned in this section."""


@dataclass(frozen=True, slots=True)
class DecisionSection:
    """A section explaining a decision."""

    source_file: Path
    heading: str
    content: str

    # Extracted structure
    question: str | None
    """What was decided? (inferred)"""

    choice: str | None
    """What was chosen?"""

    rationale: str | None
    """Why?"""


@dataclass(frozen=True, slots=True)
class SetupInstructions:
    """Setup instructions from documentation."""

    has_install_section: bool
    has_requirements: bool
    has_dev_setup: bool
    package_manager: Literal["pip", "uv", "poetry", "conda", "unknown"]


@dataclass(frozen=True, slots=True)
class ContributionGuidelines:
    """Contribution guidelines from CONTRIBUTING.md."""

    has_contributing: bool
    has_code_style: bool
    has_pr_template: bool
    has_issue_template: bool


@dataclass(frozen=True, slots=True)
class DocEvidence:
    """Evidence extracted from documentation."""

    project_name: str | None
    """Project name from README title or pyproject.toml."""

    project_description: str | None
    """One-line description."""

    architecture_sections: tuple[ArchitectureSection, ...]
    """Detected architecture/design sections."""

    decision_sections: tuple[DecisionSection, ...]
    """Sections that explain why decisions were made."""

    setup_instructions: SetupInstructions | None
    """How to set up the project."""

    contribution_guidelines: ContributionGuidelines | None
    """From CONTRIBUTING.md."""


# =============================================================================
# Configuration Evidence Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class ConfigEvidence:
    """Evidence from configuration files."""

    python_version: str | None
    """From pyproject.toml or .python-version."""

    formatter: Literal["black", "ruff", "yapf", "autopep8", "none"] | None
    """Detected formatter from config."""

    linter: Literal["ruff", "flake8", "pylint", "none"] | None
    """Detected linter."""

    type_checker: Literal["mypy", "pyright", "ty", "none"] | None
    """Detected type checker."""

    test_framework: Literal["pytest", "unittest", "nose", "none"] | None
    """Detected test framework."""

    line_length: int | None
    """Configured line length."""

    ci_provider: Literal["github", "gitlab", "jenkins", "none"] | None
    """Detected CI/CD provider."""

    ci_checks: tuple[str, ...]
    """Checks run in CI (lint, test, typecheck, etc.)."""


# =============================================================================
# Inference Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class BootstrapDecision:
    """A decision inferred from bootstrap scanning."""

    source: Literal["doc", "commit", "config"]
    """Where this decision was found."""

    source_file: Path | None
    """Source file if from documentation."""

    commit_sha: str | None
    """Source commit if from git history."""

    question: str
    """What decision was being made."""

    choice: str
    """What was chosen."""

    rationale: str | None
    """Why (if available)."""

    confidence: float
    """Confidence in this inference (0.6-0.8)."""

    def infer_category(self) -> str:
        """Infer decision category from content."""
        question_lower = self.question.lower()
        choice_lower = self.choice.lower()

        # Database decisions
        if any(kw in question_lower or kw in choice_lower
               for kw in ["database", "sql", "postgres", "sqlite", "mongo"]):
            return "database"

        # Framework decisions
        if any(kw in question_lower or kw in choice_lower
               for kw in ["framework", "flask", "fastapi", "django", "react"]):
            return "framework"

        # Auth decisions
        if any(kw in question_lower or kw in choice_lower
               for kw in ["auth", "jwt", "oauth", "session", "login"]):
            return "auth"

        # Testing decisions
        if any(kw in question_lower or kw in choice_lower
               for kw in ["test", "pytest", "unittest", "mock"]):
            return "testing"

        # Style decisions
        if any(kw in question_lower or kw in choice_lower
               for kw in ["style", "format", "lint", "black", "ruff"]):
            return "style"

        return "architecture"


@dataclass
class BootstrapPatterns:
    """Patterns inferred from bootstrap for PatternProfile.bootstrap()."""

    naming_conventions: dict[str, str] = field(default_factory=dict)
    """{'function': 'snake_case', 'class': 'PascalCase', ...}"""

    import_style: Literal["absolute", "relative", "mixed"] = "absolute"
    type_annotation_level: Literal["none", "public", "all"] = "public"
    docstring_style: Literal["google", "numpy", "sphinx", "none"] = "google"
    docstring_consistency: float = 0.75
    """How consistent the docstring style is."""

    line_length: int = 100
    formatter: str | None = None
    linter: str | None = None
    type_checker: str | None = None


# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class BootstrapStatus:
    """Status of bootstrap (when run, what was found)."""

    last_run: datetime
    """When bootstrap was last run."""

    last_commit_scanned: str
    """Git commit hash at last bootstrap."""

    decisions_count: int
    """Number of decisions bootstrapped."""

    patterns_count: int
    """Number of patterns detected."""

    ownership_domains: int
    """Number of ownership domains identified."""

    scan_duration: timedelta
    """How long the scan took."""


@dataclass
class BootstrapResult:
    """Result of bootstrap process."""

    duration: timedelta
    """How long the scan took."""

    decisions_inferred: int
    """Decisions added to DecisionMemory."""

    patterns_detected: int
    """Patterns added to PatternProfile."""

    codebase_functions: int
    codebase_classes: int

    ownership_domains: int
    """Distinct ownership areas identified."""

    average_confidence: float
    """Average confidence of bootstrapped data."""

    warnings: tuple[str, ...]
    """Any warnings during bootstrap."""

    # Detailed evidence (for debugging/inspection)
    git_evidence: GitEvidence | None = None
    code_evidence: CodeEvidence | None = None
    doc_evidence: DocEvidence | None = None
    config_evidence: ConfigEvidence | None = None
