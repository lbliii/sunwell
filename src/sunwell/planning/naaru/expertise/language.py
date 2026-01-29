"""Language Detection for Expertise-Aware Planning.

Fast, local classification of programming language from:
1. Goal keywords (e.g., "svelte", "react", "rust")
2. Project markers (e.g., pyproject.toml, package.json)

Uses weighted signals - no LLM required.

Example:
    >>> from pathlib import Path
    >>> result = detect_language("build a todo app in svelte", Path("/my/project"))
    >>> result.language
    Language.TYPESCRIPT
    >>> result.confidence
    0.95
    >>> result.signals
    ('svelte',)
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Language(Enum):
    """Recognized programming languages."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    RUST = "rust"
    GO = "go"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LanguageClassification:
    """Result of language classification."""

    language: Language
    confidence: float  # 0.0 to 1.0
    signals: tuple[str, ...]  # Keywords/markers that triggered classification
    source: str  # "goal", "project", "combined"

    @property
    def is_confident(self) -> bool:
        """Whether classification confidence is high enough for lens selection."""
        return self.confidence >= 0.5


# Goal keyword signals (detect from user request)
# Higher weight = stronger signal
LANGUAGE_GOAL_SIGNALS: dict[Language, dict[str, float]] = {
    Language.TYPESCRIPT: {
        # Frameworks that imply TypeScript/JavaScript
        "svelte": 1.0,
        "sveltekit": 1.0,
        "react": 1.0,
        "nextjs": 1.0,
        "next.js": 1.0,
        "vue": 1.0,
        "nuxt": 1.0,
        "angular": 1.0,
        "remix": 1.0,
        "astro": 1.0,
        "solid": 0.8,
        "solidjs": 1.0,
        "qwik": 1.0,
        # Explicit language mentions
        "typescript": 1.0,
        "tsx": 1.0,
        "ts": 0.7,
        # Package managers / tools
        "npm": 0.7,
        "pnpm": 0.7,
        "yarn": 0.7,
        "bun": 0.7,
        "vite": 0.8,
        "webpack": 0.7,
        "esbuild": 0.7,
        # Runtime
        "node": 0.6,
        "nodejs": 0.7,
        "deno": 0.8,
    },
    Language.JAVASCRIPT: {
        "javascript": 1.0,
        "js": 0.7,
        "jsx": 0.9,
        "express": 0.8,
        "koa": 0.8,
        "fastify": 0.8,
        "hapi": 0.8,
    },
    Language.PYTHON: {
        # Explicit
        "python": 1.0,
        "py": 0.7,
        # Frameworks
        "django": 0.95,
        "flask": 0.95,
        "fastapi": 0.95,
        "starlette": 0.9,
        "tornado": 0.9,
        "pyramid": 0.9,
        "bottle": 0.9,
        "sanic": 0.9,
        "aiohttp": 0.8,
        # Tools
        "pytest": 0.8,
        "unittest": 0.8,
        "pip": 0.6,
        "poetry": 0.7,
        "uv": 0.6,
        "ruff": 0.7,
        "mypy": 0.7,
        # Libraries
        "pandas": 0.8,
        "numpy": 0.8,
        "tensorflow": 0.8,
        "pytorch": 0.8,
        "scikit": 0.8,
        "sklearn": 0.8,
    },
    Language.RUST: {
        "rust": 1.0,
        "cargo": 0.9,
        "rustc": 0.9,
        "tokio": 0.85,
        "actix": 0.85,
        "axum": 0.85,
        "warp": 0.8,
        "rocket": 0.85,
        "serde": 0.7,
        "tauri": 0.8,
    },
    Language.GO: {
        "go": 0.9,  # Slightly lower because "go" is a common word
        "golang": 1.0,
        "gin": 0.8,
        "echo": 0.7,
        "fiber": 0.7,
        "gorilla": 0.7,
        "gorm": 0.7,
    },
}

# Project marker signals (detect from filesystem)
# Tuple of (filename, confidence)
PROJECT_MARKERS: dict[Language, tuple[tuple[str, float], ...]] = {
    Language.PYTHON: (
        ("pyproject.toml", 1.0),
        ("setup.py", 0.95),
        ("setup.cfg", 0.9),
        ("requirements.txt", 0.8),
        ("Pipfile", 0.85),
        ("poetry.lock", 0.9),
        ("uv.lock", 0.9),
    ),
    Language.TYPESCRIPT: (
        ("tsconfig.json", 1.0),
        ("tsconfig.node.json", 0.95),
        ("tsconfig.app.json", 0.95),
    ),
    Language.JAVASCRIPT: (
        ("package.json", 0.7),  # Lower because package.json is used by TS too
        ("jsconfig.json", 0.9),
    ),
    Language.RUST: (
        ("Cargo.toml", 1.0),
        ("Cargo.lock", 0.95),
    ),
    Language.GO: (
        ("go.mod", 1.0),
        ("go.sum", 0.95),
    ),
}

# Map languages to their expert lens names
LANGUAGE_LENSES: dict[Language, str] = {
    Language.PYTHON: "python-expert-v2",
    Language.TYPESCRIPT: "typescript-expert-v2",
    Language.JAVASCRIPT: "typescript-expert-v2",  # JS uses TS lens (superset)
    Language.RUST: "rust-expert-v2",
    Language.GO: "go-expert-v2",
}


class LanguageClassifier:
    """Classify programming language from goal text and/or project markers.

    Uses weighted keyword matching for fast, deterministic classification.
    No LLM required.

    Example:
        >>> classifier = LanguageClassifier()
        >>> result = classifier.classify_goal("build a todo app in svelte")
        >>> result.language
        Language.TYPESCRIPT
    """

    def __init__(self, threshold: float = 0.5) -> None:
        """Initialize classifier.

        Args:
            threshold: Minimum confidence for classification (default 0.5)
        """
        self.threshold = threshold

    def classify_goal(self, goal: str) -> LanguageClassification:
        """Classify language from goal text only.

        Args:
            goal: User's goal/task description

        Returns:
            LanguageClassification with language, confidence, and matched signals
        """
        lower_goal = goal.lower()
        words = set(lower_goal.split())

        # Score each language
        scores: dict[Language, tuple[float, list[str]]] = {}

        for language, signals in LANGUAGE_GOAL_SIGNALS.items():
            total_weight = 0.0
            matched: list[str] = []

            for keyword, weight in signals.items():
                # Check for exact word match or substring
                if keyword in words or keyword in lower_goal:
                    total_weight += weight
                    matched.append(keyword)

            if matched:
                # Normalize: max confidence is 1.0
                scores[language] = (min(total_weight, 1.0), matched)

        if not scores:
            return LanguageClassification(
                language=Language.UNKNOWN,
                confidence=0.0,
                signals=(),
                source="goal",
            )

        # Find best match
        best_lang = max(scores, key=lambda k: scores[k][0])
        confidence, signals = scores[best_lang]

        return LanguageClassification(
            language=best_lang,
            confidence=confidence,
            signals=tuple(signals),
            source="goal",
        )

    def classify_project(self, project_path: Path) -> LanguageClassification:
        """Classify language from project directory markers.

        Args:
            project_path: Path to project directory

        Returns:
            LanguageClassification with language, confidence, and matched markers
        """
        if not project_path.exists():
            return LanguageClassification(
                language=Language.UNKNOWN,
                confidence=0.0,
                signals=(),
                source="project",
            )

        # Score each language based on marker files
        scores: dict[Language, tuple[float, list[str]]] = {}

        for language, markers in PROJECT_MARKERS.items():
            total_weight = 0.0
            matched: list[str] = []

            for marker_file, weight in markers:
                if (project_path / marker_file).exists():
                    total_weight += weight
                    matched.append(marker_file)

            if matched:
                # Normalize: max confidence is 1.0
                scores[language] = (min(total_weight, 1.0), matched)

        if not scores:
            return LanguageClassification(
                language=Language.UNKNOWN,
                confidence=0.0,
                signals=(),
                source="project",
            )

        # Handle TypeScript vs JavaScript disambiguation
        # If tsconfig.json exists, prefer TypeScript over JavaScript
        if Language.TYPESCRIPT in scores and Language.JAVASCRIPT in scores:
            ts_conf, _ = scores[Language.TYPESCRIPT]
            js_conf, _ = scores[Language.JAVASCRIPT]
            if ts_conf >= js_conf:
                del scores[Language.JAVASCRIPT]

        # Find best match
        best_lang = max(scores, key=lambda k: scores[k][0])
        confidence, signals = scores[best_lang]

        return LanguageClassification(
            language=best_lang,
            confidence=confidence,
            signals=tuple(signals),
            source="project",
        )

    def classify(
        self,
        goal: str,
        project_path: Path | None = None,
    ) -> LanguageClassification:
        """Classify language from goal text and/or project markers.

        Priority:
        1. Goal keywords with high confidence (>= 0.8) - user intent is clear
        2. Combined goal + project signals
        3. Project markers alone

        Args:
            goal: User's goal/task description
            project_path: Optional path to project directory

        Returns:
            LanguageClassification with language, confidence, and signals
        """
        goal_result = self.classify_goal(goal)

        # If goal has high confidence, trust it (user intent is explicit)
        if goal_result.confidence >= 0.8:
            return goal_result

        # If no project path, return goal result
        if project_path is None:
            return goal_result

        project_result = self.classify_project(project_path)

        # If goal found nothing, use project
        if goal_result.language == Language.UNKNOWN:
            return project_result

        # If project found nothing, use goal
        if project_result.language == Language.UNKNOWN:
            return goal_result

        # Both have results - combine
        if goal_result.language == project_result.language:
            # Agreement boosts confidence
            combined_confidence = min(
                goal_result.confidence + project_result.confidence * 0.5, 1.0
            )
            combined_signals = goal_result.signals + project_result.signals
            return LanguageClassification(
                language=goal_result.language,
                confidence=combined_confidence,
                signals=combined_signals,
                source="combined",
            )

        # Disagreement - prefer goal if it's reasonably confident
        if goal_result.confidence >= 0.6:
            return goal_result

        # Otherwise prefer project markers
        return project_result


def detect_language(
    goal: str,
    project_path: Path | None = None,
    threshold: float = 0.5,
) -> LanguageClassification:
    """Detect programming language from goal and/or project.

    Convenience function using default LanguageClassifier.

    Args:
        goal: User's goal/task description
        project_path: Optional path to project directory
        threshold: Minimum confidence for classification

    Returns:
        LanguageClassification with language, confidence, and signals

    Example:
        >>> result = detect_language("build a todo app in svelte")
        >>> result.language
        Language.TYPESCRIPT
        >>> result.confidence
        0.95
    """
    classifier = LanguageClassifier(threshold=threshold)
    return classifier.classify(goal, project_path)


def get_language_lens(language: Language) -> str | None:
    """Get the expert lens name for a language.

    Args:
        language: The detected language

    Returns:
        Lens name (e.g., "typescript-expert-v2") or None if no lens available

    Example:
        >>> get_language_lens(Language.TYPESCRIPT)
        'typescript-expert-v2'
    """
    return LANGUAGE_LENSES.get(language)


def language_from_extension(extension: str) -> Language:
    """Get language from file extension.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        Language enum value

    Example:
        >>> language_from_extension(".ts")
        Language.TYPESCRIPT
    """
    ext = extension.lower().lstrip(".")

    extension_map: dict[str, Language] = {
        # Python
        "py": Language.PYTHON,
        "pyi": Language.PYTHON,
        "pyx": Language.PYTHON,
        # TypeScript
        "ts": Language.TYPESCRIPT,
        "tsx": Language.TYPESCRIPT,
        "mts": Language.TYPESCRIPT,
        "cts": Language.TYPESCRIPT,
        # JavaScript
        "js": Language.JAVASCRIPT,
        "jsx": Language.JAVASCRIPT,
        "mjs": Language.JAVASCRIPT,
        "cjs": Language.JAVASCRIPT,
        # Svelte, Vue, etc. (use TypeScript tooling)
        "svelte": Language.TYPESCRIPT,
        "vue": Language.TYPESCRIPT,
        # Rust
        "rs": Language.RUST,
        # Go
        "go": Language.GO,
    }

    return extension_map.get(ext, Language.UNKNOWN)
