"""Code pattern extraction (RFC-DOMAINS).

Extracts learnings from code artifacts:
- Class definitions and inheritance
- Field definitions (dataclass, SQLAlchemy)
- API routes and endpoints
- Import patterns
- Framework detection
"""

import re
from dataclasses import dataclass

from sunwell.agent.learning.learning import Learning

# Pre-compiled regex patterns for code extraction
_RE_API_ROUTE = re.compile(
    r"@(?:app|router|bp)\.(?:route|get|post|put|delete)\(['\"]([^'\"]+)['\"]"
)
_RE_FUNC_DEF = re.compile(r"def\s+(\w+)")
_RE_IMPORT_FROM = re.compile(r"^from\s+(\S+)\s+import", re.MULTILINE)
_RE_CLASS_DEF = re.compile(r"class\s+(\w+)(?:\(([^)]+)\))?:")
_RE_FOREIGN_KEY = re.compile(r"(\w+)\s*=\s*(?:Column\()?ForeignKey\(['\"]([^'\"]+)['\"]")
_RE_DATACLASS_FIELD = re.compile(r"^\s+(\w+):\s*(\S+)", re.MULTILINE)
_RE_SQLA_COLUMN = re.compile(r"^\s+(\w+)\s*=\s*Column\(", re.MULTILINE)

# Language detection patterns
_LANGUAGE_INDICATORS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "javascript": (".js", ".mjs", ".cjs"),
    "typescript": (".ts", ".tsx"),
    "go": (".go",),
    "rust": (".rs",),
    "java": (".java",),
    "ruby": (".rb",),
    "php": (".php",),
    "c#": (".cs",),
    "swift": (".swift",),
    "kotlin": (".kt", ".kts"),
}

# Framework detection patterns
_FRAMEWORK_PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    "Flask": (re.compile(r"from flask import|Flask\(__name__\)"),),
    "FastAPI": (re.compile(r"from fastapi import|FastAPI\(\)"),),
    "Django": (re.compile(r"from django|django\."),),
    "Express": (re.compile(r"require\(['\"]express['\"]\)|from ['\"]express['\"]"),),
    "React": (re.compile(r"import React|from ['\"]react['\"]|useState|useEffect"),),
    "Vue": (re.compile(r"from ['\"]vue['\"]|createApp|defineComponent"),),
    "SQLAlchemy": (re.compile(r"from sqlalchemy|Column\(|relationship\("),),
    "Pydantic": (re.compile(r"from pydantic|BaseModel|Field\("),),
}


@dataclass(slots=True)
class CodePatternExtractor:
    """Extracts learnings from code artifacts.

    Uses pattern-based extraction (fast, no LLM) for:
    - Project language (from file extension)
    - Framework usage (from imports)
    - Type/class definitions
    - Foreign key relationships
    - API endpoints
    """

    def extract(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[Learning]:
        """Extract learnings from code content.

        Args:
            content: Code content
            file_path: Optional path to the file

        Returns:
            List of extracted learnings
        """
        learnings: list[Learning] = []

        # Extract project-level learnings (language, framework)
        learnings.extend(self._extract_project_facts(content, file_path))

        # Extract class definitions
        for match in _RE_CLASS_DEF.finditer(content):
            class_name = match.group(1)
            bases = match.group(2) or ""

            # Find fields in dataclass or model
            class_end = content.find("\nclass ", match.end())
            if class_end == -1:
                class_end = len(content)
            class_body = content[match.end() : class_end]

            # Extract fields
            fields = self._extract_fields(class_body)
            if fields:
                fact = f"{class_name} has fields: {', '.join(fields)}"
                learnings.append(
                    Learning(
                        fact=fact,
                        category="type",
                        confidence=0.9,
                        source_file=file_path,
                    )
                )

            # Check for inheritance
            if bases:
                learnings.append(
                    Learning(
                        fact=f"{class_name} extends {bases}",
                        category="type",
                        confidence=0.9,
                        source_file=file_path,
                    )
                )

        # Extract foreign keys
        for match in _RE_FOREIGN_KEY.finditer(content):
            field_name = match.group(1)
            target = match.group(2)
            learnings.append(
                Learning(
                    fact=f"{field_name} is ForeignKey to {target}",
                    category="type",
                    confidence=0.9,
                    source_file=file_path,
                )
            )

        # Extract API routes
        for match in _RE_API_ROUTE.finditer(content):
            route = match.group(1)
            # Find function name
            func_match = _RE_FUNC_DEF.search(
                content[match.end() : match.end() + 100],
            )
            func_name = func_match.group(1) if func_match else "unknown"
            learnings.append(
                Learning(
                    fact=f"Endpoint {route} handled by {func_name}",
                    category="api",
                    confidence=0.85,
                    source_file=file_path,
                )
            )

        # Extract imports pattern
        imports = _RE_IMPORT_FROM.findall(content)
        if imports:
            # Get unique import sources
            sources = list(set(imports))[:5]  # Limit to 5
            if sources:
                learnings.append(
                    Learning(
                        fact=f"Uses imports from: {', '.join(sources)}",
                        category="pattern",
                        confidence=0.7,
                        source_file=file_path,
                    )
                )

        return learnings

    def _extract_fields(self, class_body: str) -> list[str]:
        """Extract field names from class body."""
        fields: list[str] = []

        # Dataclass fields: field_name: Type
        for match in _RE_DATACLASS_FIELD.finditer(class_body):
            if not match.group(1).startswith("_"):
                fields.append(match.group(1))

        # SQLAlchemy columns: field_name = Column(...)
        for match in _RE_SQLA_COLUMN.finditer(class_body):
            fields.append(match.group(1))

        return fields[:10]  # Limit to 10 fields

    def _extract_project_facts(
        self,
        content: str,
        file_path: str | None,
    ) -> list[Learning]:
        """Extract project-level facts (language, framework).

        These are high-confidence learnings that help maintain
        consistency across the project.

        Args:
            content: Code content
            file_path: Path to the file

        Returns:
            List of project-level learnings
        """
        learnings: list[Learning] = []

        if not file_path:
            return learnings

        # Detect language from file extension
        for language, extensions in _LANGUAGE_INDICATORS.items():
            if any(file_path.endswith(ext) for ext in extensions):
                learnings.append(
                    Learning(
                        fact=f"Project uses {language}",
                        category="project",
                        confidence=0.95,  # High confidence - file extension is definitive
                        source_file=file_path,
                    )
                )
                break

        # Detect frameworks from content
        for framework, patterns in _FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(content):
                    learnings.append(
                        Learning(
                            fact=f"Project uses {framework}",
                            category="project",
                            confidence=0.9,
                            source_file=file_path,
                        )
                    )
                    break

        return learnings
