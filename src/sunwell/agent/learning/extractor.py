"""Learning extraction from code and fix attempts."""

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.agent.learning.dead_end import DeadEnd
from sunwell.agent.learning.learning import Learning

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.turn import Learning as SimLearning
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.types import Task

# Pre-compiled regex patterns for learning extraction (avoid recompiling per call)
_RE_API_ROUTE = re.compile(
    r"@(?:app|router|bp)\.(?:route|get|post|put|delete)\(['\"]([^'\"]+)['\"]"
)
_RE_FUNC_DEF = re.compile(r"def\s+(\w+)")
_RE_IMPORT_FROM = re.compile(r"^from\s+(\S+)\s+import", re.MULTILINE)
_RE_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_RE_CLASS_DEF = re.compile(r"class\s+(\w+)(?:\(([^)]+)\))?:")
_RE_FOREIGN_KEY = re.compile(r"(\w+)\s*=\s*(?:Column\()?ForeignKey\(['\"]([^'\"]+)['\"]")
_RE_DATACLASS_FIELD = re.compile(r"^\s+(\w+):\s*(\S+)", re.MULTILINE)
_RE_SQLA_COLUMN = re.compile(r"^\s+(\w+)\s*=\s*Column\(", re.MULTILINE)


@dataclass(slots=True)
class LearningExtractor:
    """Extracts learnings from generated code and fix attempts.

    Uses both pattern-based extraction (fast, no LLM) and
    optional LLM extraction (deeper insights, more expensive).
    """

    use_llm: bool = False
    """Whether to use LLM for deeper extraction."""

    model: ModelProtocol | None = None
    """Model for LLM extraction."""

    def extract_from_code(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[Learning]:
        """Extract learnings from generated code.

        Uses pattern matching for:
        - Type/class definitions
        - Foreign key relationships
        - API endpoints
        - Configuration patterns

        Args:
            content: Code content
            file_path: Path to the file

        Returns:
            List of extracted learnings
        """
        learnings: list[Learning] = []

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

    def extract_from_fix(
        self,
        error_type: str,
        error_message: str,
        fix_description: str,
        success: bool,
    ) -> Learning | DeadEnd:
        """Extract learning from a fix attempt.

        Args:
            error_type: Type of error (syntax, type, runtime)
            error_message: The error message
            fix_description: What was done to fix
            success: Whether the fix worked

        Returns:
            Learning if successful, DeadEnd if not
        """
        if success:
            return Learning(
                fact=f"Fixed '{error_type}' by: {fix_description}",
                category="fix",
                confidence=0.85,
            )
        else:
            return DeadEnd(
                approach=fix_description,
                reason=error_message,
                context=f"Error type: {error_type}",
            )

    async def extract_with_llm(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[Learning]:
        """Extract deeper learnings using LLM.

        More expensive but catches patterns that regex misses.

        Args:
            content: Code content
            file_path: Path to the file

        Returns:
            List of extracted learnings
        """
        if not self.model:
            return []

        from sunwell.models import GenerateOptions

        prompt = f"""Extract key facts from this code that would help generating similar code.

CODE:
```python
{content[:2000]}  # Truncate for token budget
```

Output ONLY facts in this format (one per line):
TYPE: [fact about types, fields, relationships]
API: [fact about endpoints, routes]
PATTERN: [fact about code patterns, conventions]

Examples:
TYPE: User.id is Integer primary key
TYPE: Post has user_id ForeignKey to users.id
API: POST /users creates new user
PATTERN: Using Flask-SQLAlchemy with create_app pattern"""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=500),
            )

            learnings = []
            for line in result.text.split("\n"):
                line = line.strip()
                if ":" in line:
                    category, fact = line.split(":", 1)
                    category = category.strip().lower()
                    fact = fact.strip()
                    if category in ("type", "api", "pattern") and fact:
                        learnings.append(
                            Learning(
                                fact=fact,
                                category=category,
                                confidence=0.75,
                                source_file=file_path,
                            )
                        )

            return learnings

        except Exception as e:
            logger.debug("LLM extraction failed: %s", e)
            return []

    # =========================================================================
    # RFC-122: Template and Heuristic Extraction
    # =========================================================================

    async def extract_template(
        self,
        goal: str,
        files_changed: list[str],
        artifacts_created: list[str],
        tasks: list[Task],
    ) -> SimLearning | None:
        """Extract a reusable template from successful novel task (RFC-122).

        Criteria for extraction:
        - Multiple artifacts created (structured output)
        - Consistent file naming pattern
        - Clean success (no retries)

        Args:
            goal: The completed goal description
            files_changed: List of file paths that were modified
            artifacts_created: List of artifact names created
            tasks: Tasks that were executed

        Returns:
            Template Learning if extractable, None otherwise
        """
        from sunwell.memory.simulacrum.core.turn import (
            Learning as SimLearning,
        )
        from sunwell.memory.simulacrum.core.turn import (
            TemplateData,
            TemplateVariable,
        )

        # Check if this is extractable
        if len(artifacts_created) < 2:
            return None
        if len(files_changed) < 2:
            return None

        if not self.model:
            return None

        from sunwell.models import GenerateOptions

        # Use LLM to analyze pattern
        prompt = f"""Analyze this successful task for repeatable patterns.

Goal: {goal}

Files created/modified:
{chr(10).join(f'- {f}' for f in files_changed)}

Artifacts produced:
{chr(10).join(f'- {a}' for a in artifacts_created)}

Tasks executed:
{chr(10).join(f'- {t.description}' for t in tasks[:10])}

Is this a repeatable pattern? If yes, extract:
1. Pattern name (e.g., "CRUD Endpoint", "Service Module")
2. Variables that could be parameterized (e.g., "entity" extracted from "User")
3. Expected artifacts for the pattern (with {{{{variable}}}} placeholders)
4. Prerequisites (what must exist before this pattern)
5. Validation commands

Return JSON with:
{{"is_pattern": true/false, "name": "...", "match_patterns": [...], "variables": [...],
"produces": [...], "requires": [...], "expected_artifacts": [...], "validation": [...]}}

For variables, use format:
{{"name": "entity", "description": "Model name", "type": "string",
"hints": ["for {{{{entity}}}}", "{{{{entity}}}} API"]}}"""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=1000),
            )

            # Parse JSON from response
            json_match = _RE_JSON_OBJECT.search(result.text)
            if not json_match:
                return None

            data = json.loads(json_match.group())
            if not data.get("is_pattern"):
                return None

            template_data = TemplateData(
                name=data["name"],
                match_patterns=tuple(data.get("match_patterns", [])),
                variables=tuple(
                    TemplateVariable(
                        name=v["name"],
                        description=v.get("description", ""),
                        var_type=v.get("type", "string"),
                        extraction_hints=tuple(v.get("hints", [])),
                    )
                    for v in data.get("variables", [])
                ),
                produces=tuple(data.get("produces", [])),
                requires=tuple(data.get("requires", [])),
                expected_artifacts=tuple(data.get("expected_artifacts", [])),
                validation_commands=tuple(data.get("validation", [])),
            )

            return SimLearning(
                fact=f"Task pattern: {template_data.name}",
                source_turns=(),
                confidence=0.7,  # Start moderate, boost with reuse
                category="template",
                template_data=template_data,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("Template extraction failed: %s", e)
            return None

    def extract_heuristic(
        self,
        goal: str,
        tasks: list[Task],
    ) -> SimLearning | None:
        """Extract ordering/strategy heuristic from successful task (RFC-122).

        Analyzes task ordering for patterns like "models before routes before tests".
        No LLM needed - uses pattern matching.

        Args:
            goal: The completed goal
            tasks: Tasks that were executed

        Returns:
            Heuristic Learning if extractable, None otherwise
        """
        from sunwell.memory.simulacrum.core.turn import Learning as SimLearning

        if len(tasks) < 3:
            return None

        # Analyze task ordering for patterns
        task_types: list[str] = []
        for task in tasks:
            desc_lower = task.description.lower()
            if "model" in desc_lower or "schema" in desc_lower:
                task_types.append("model")
            elif "route" in desc_lower or "endpoint" in desc_lower or "api" in desc_lower:
                task_types.append("routes")
            elif "test" in desc_lower:
                task_types.append("tests")
            elif "config" in desc_lower or "setup" in desc_lower:
                task_types.append("config")

        # Check for common patterns
        if task_types:
            # Model before routes before tests
            if "model" in task_types and "tests" in task_types:
                model_idx = task_types.index("model")
                tests_idx = len(task_types) - 1 - task_types[::-1].index("tests")
                if model_idx < tests_idx:
                    return SimLearning(
                        fact="Create models before writing tests",
                        source_turns=(),
                        confidence=0.6,
                        category="heuristic",
                    )

            # Config before models
            if "config" in task_types and "model" in task_types:
                config_idx = task_types.index("config")
                model_idx = task_types.index("model")
                if config_idx < model_idx:
                    return SimLearning(
                        fact="Setup configuration before creating models",
                        source_turns=(),
                        confidence=0.6,
                        category="heuristic",
                    )

            # Routes after models
            if "model" in task_types and "routes" in task_types:
                model_idx = task_types.index("model")
                routes_idx = task_types.index("routes")
                if model_idx < routes_idx:
                    return SimLearning(
                        fact="Create models before defining API routes",
                        source_turns=(),
                        confidence=0.65,
                        category="heuristic",
                    )

        return None
